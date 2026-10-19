"""Same-origin front for publisher-hosted games (decision 0022).

The publisher's client bytes and its RGS stay the publisher's. We sit in front
so the money path is ours: the launcher and every asset/RGS request are
forwarded to the publisher, the balance the game shows is replaced with the
player's real saldo, and an injected bridge reports each round's stake and win
to the operator wallet API (`/api/wallet/*`) and blocks the spin when the saldo
is empty.

Serving the game from our own origin is what makes this possible at all: a
cross-origin iframe cannot be scripted, and the publisher RGS refuses a foreign
origin (observed: the Hacksaw RGS rejects the preflight with no ACAO). Through
the proxy every call is same-origin, so there is no CORS wall and the bridge can
sit in front of the game's networking.

Layout:

    /g/<game_id>              the launcher, with the bridge injected
    /g/<game_id>/_abs/<host>/<path>   an absolute publisher URL, rewritten
    /g/<game_id>/<path>       path resolved against the launcher's own host
    /g/bridge.js              the injected bridge

Per-publisher money mapping lives in `ADAPTERS` (URL patterns + JSON paths);
where a publisher is not yet mapped the game still runs and the balance gate
still applies, but the round is not mirrored into the books.
"""

from __future__ import annotations

import os
import re
import threading
import urllib.error
import urllib.request
from urllib.parse import quote, unquote, urljoin, urlparse, urlsplit

from . import pg_proxy
from . import provider_demos

GAME_PREFIX = "/g"
BRIDGE_PATH = "/g/bridge.js"

# Hosts allowed to be proxied: the publisher demo hosts plus their RGS hosts.
EXTRA_HOSTS: frozenset[str] = frozenset({
    "rgs-demo.hacksawgaming.com",
    "turbo.spribegaming.com",
    "app-demo.spribegaming.com",
    "app-demo2.spribegaming.com",
    "static.pgsoft-games.com",
    "m.pgsoft-games.com",
    "games.evolution.com",
})

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
MAX_BODY = 32 * 1024 * 1024

# The client's own headers we are willing to carry to the publisher. Content
# negotiation decides the shape of the answer; the conditional and range
# headers decide whether a body has to travel at all (a publisher bundle is
# tens of megabytes and revalidates in milliseconds).
CONDITIONAL_HEADERS = frozenset({"if-none-match", "if-modified-since"})
FORWARDED_HEADERS = frozenset({
    "content-type", "accept-language", "x-requested-with",
}) | CONDITIONAL_HEADERS | {"range"}

# Query parameters that belong to us and must never reach a publisher: the
# wallet token is a player's session credential, `pg` is our own PG Soft
# session id, and a redirect we rewrite puts it back on the way out
# (`Handler._pass_redirect`). `token` is ours on a direct launch and the
# publisher's on a redirect — an interposed RGS still has to receive it
# (see `publisher_query`).
WALLET_PARAMS = frozenset({"wallet_token", "token", "pg"})

# Path extensions whose body we rewrite before serving (the client patchers,
# the money-URL rewrite, the bridge injection). A rewritten body cannot be
# revalidated against the publisher's validator: the bytes we hand back are
# not the bytes the validator describes.
_SCRIPT_EXTENSIONS = frozenset({
    ".js", ".mjs", ".json", ".css", ".html", ".htm", ".txt", ".map",
})

# Caching headers the publisher's answer carries back to the browser, kept so
# a reload costs a 304 instead of the whole game.
VALIDATOR_HEADERS = ("ETag", "Last-Modified", "Expires",
                     "Content-Range", "Accept-Ranges")

DEFAULT_ASSET_CACHE = "public, max-age=600"

# A publisher's own domains: any subdomain may be proxied (launchers, asset
# hosts, config hosts and game servers are minted per title).
ALLOWED_SUFFIXES: tuple[str, ...] = (
    ".pragmaticplay.net", ".pgsoft-games.com", ".hacksawgaming.com",
    ".playngonetwork.com", ".evolution.com", ".spribegaming.com",
    ".spribe.io", ".pg-demo.com",
)

# Statuses whose Location we hand back to the browser instead of following:
# a launcher redirect mints the session (Spribe's `?user=&token=`), so the
# browser's own URL must end up carrying it.
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

# Publisher hosts that serve the game's config/service data. A browser
# fetching them directly can fail for reasons that have nothing to do with
# us — Spribe's config host answers 403 to browser-like requests and omits
# CORS — so every URL on these hosts is rewritten onto our origin and
# fetched server-side, where it answers 200.
SERVICE_HOSTS: frozenset[str] = frozenset({
    "app-config.spribegaming.com",
})

# Providers whose launcher *redirect* mints the session in the target URL
# (Spribe: demo.spribe.io/launch/x -> <game>-demo.spribegaming.com/?user=&token=).
# For these the redirect must reach the browser, or the game has no session.
# Every other provider keeps its launcher served same-origin, which is what
# puts the wallet bridge in front of it.
REDIRECT_PROVIDERS: frozenset[str] = frozenset({"spribe"})

# Per-provider RGS endpoints. Absolute URLs matching these are
# rewritten to absolute URLs on OUR origin: the game's config
# parser splits URLs on "//" and needs the schema://domain shape
# intact (a root-relative rewrite throws it off), and the RGS
# refuses cross-origin calls (no access-control-allow-origin), so
# the money path must be same-origin — through us. Everything
# else, the asset CDN included, stays on the publisher: its static
# hosts answer with access-control-allow-origin: *, so the game's
# asset XHRs work cross-origin and we only sit in front of the
# money.
MONEY_PATHS: dict[str, tuple[str, ...]] = {
    "pragmatic_play": (
        r"/gs2c/ge/", r"/gs2c/reloadBalance\.do", r"/gs2c/jackpot/reload\.do",
        r"/gs2c/regulation/process\.do", r"/gs2c/closeGame\.do",
        r"/gs2c/saveSettings\.do", r"/gs2c/logout\.do", r"/gs2c/stats\.do",
        r"/gs2c/replayGame\.do", r"/gs2c/replay/",
    ),
    "hacksaw_gaming": (r"/api/play/", r"/api/meta/"),
    # PG Soft money, as measured (decision 0040): the session handshake,
    # the game/wallet proxies and the binary game-api. Classifying them
    # as money means no-store, no 304 pinning and withheld validators —
    # a per-session balance must never be cached or revalidated.
    "pg_soft": (
        r"/web-api/auth/session/v2/verifySession",
        r"/web-api/game-proxy/v2/GameName/Get",
        r"/web-api/game-proxy/v2/Resources/GetByResourcesTypeIds",
        r"/web-api/game-proxy/v2/GameWallet/Get",
        r"/game-api/",
    ),
}


class ProxyError(RuntimeError):
    pass


def _allowed_host(host: str) -> bool:
    """A publisher host we may proxy: an exact catalog host, any subdomain
    of a publisher's own domain, or a host this process minted a session for.

    The exact list cannot cover every launcher a publisher mints per game
    (Spribe serves each game from `<game>-demo.spribegaming.com`), so a
    publisher's own domain is allowed by suffix. The leading dot is required,
    so `evil-spribegaming.com` never matches.

    PG Soft is the third case and the reason this is not a constant: it mints
    its hosts per session (`m.<label>.com`, `api.<label>.com`), so no suffix
    rule covers them and no static list survives a week. Those hosts are
    allowed because *this process* asked PG for them and bound the exact
    strings in the answer, which is the only grant here that is not a
    standing rule about somebody else's domain.
    """
    if host in (provider_demos.DEMO_HOSTS | EXTRA_HOSTS):
        return True
    if host.endswith(ALLOWED_SUFFIXES):
        return True
    return pg_proxy.allowed_host(host)


def allowed_host(host: str) -> bool:
    """Public host allowlist check."""
    return _allowed_host(host)


def game_for(game_id: str) -> dict | None:
    for d in provider_demos.load().get("demos", []):
        if d["game_id"] == game_id:
            return d
    return None


# PG Soft launches live at `/<gi>/…` (game_for_gi): the client builds its
# per-game asset URLs off its own path, so the launch cannot live under
# `/g/`. The dispatcher routes these here; `_serve_game` resolves the
# catalog row (unknown numbers still 404).
PG_GI_PATH = re.compile(r"^/\d+(?:/.*)?$")


def game_for_gi(gi: str) -> dict | None:
    """The catalog row whose launcher names this PG Soft game id.

    A PG launch is served from `/<gi>/` (not `/g/<id>/…`) so the client
    builds its per-game asset URLs exactly like on the publisher
    (`<static>/<gi>/<file>`); the session id rides the query and a
    cookie instead of the path.
    """
    from urllib.parse import parse_qsl, urlsplit
    for d in provider_demos.load().get("demos", []):
        query = dict(parse_qsl(urlsplit(d.get("demo_url") or "").query))
        if query.get("gi") == str(gi):
            return d
    return None


def split_game_path(path: str) -> tuple[str, str] | None:
    """Decode a /g/<game_id>/… request path into (game_id, sub).

    The path is URL-decoded first: the encoded game_id is longer
    than the decoded one (":" is "%3A"), so slicing an encoded path
    mangles the id and every sub-path after it.
    """
    decoded = unquote(path)
    if not decoded.startswith(GAME_PREFIX + "/"):
        return None
    rest = decoded[len(GAME_PREFIX) + 1:]
    game_id, _, sub = rest.partition("/")
    if not game_id:
        return None
    return game_id, sub


def checked_url(url: str) -> str:
    """A publisher URL, or nothing: the one place a target is vetted.

    The mapping is built by joining and substitution, so a sub-path that
    looks like a network-path reference (`//elsewhere/x`) or userinfo
    (`@elsewhere`) can move the URL off the publisher. The scheme and the
    host are checked here, at the end of the mapping, rather than left to
    the caller to remember.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ProxyError(f"only https publisher URLs are proxied: {url[:96]}")
    if not _allowed_host(parsed.hostname or ""):
        raise ProxyError(f"host not allowed: {parsed.hostname}")
    return url


def target_url(game: dict, sub: str, query: str) -> str:
    """Map a /g/<id>/… sub-path onto a publisher URL."""
    if sub.startswith(PG_PREFIX):
        return pg_target(game, sub, query)
    base = game["demo_url"]
    if sub.startswith("_abs/"):
        host, _, tail = sub[len("_abs/"):].partition("/")
        if not _allowed_host(host):
            raise ProxyError(f"host not allowed: {host}")
        url = f"https://{host}/{tail}"
        return checked_url(url + (f"?{query}" if query else ""))
    if sub == "":
        return checked_url(base)
    base_dir = base.rsplit("/", 1)[0] + "/"
    url = urljoin(base_dir, sub.lstrip("/"))
    if query:
        url += ("&" if "?" in url else "?") + query
    return checked_url(url)


# PG Soft sub-path marker: `/g/<id>/pg/<session>/…`. The session id is ours,
# not the publisher's, and it is what makes the per-session hosts resolvable
# without a standing rule about somebody else's domain.
PG_PREFIX = "pg/"


def pg_target(game: dict, sub: str, query: str) -> str:
    """Resolve a PG Soft sub-path through the session we minted for it.

    PG will not boot a page we did not mint: the game document carries an
    operator token issued at mint time and every asset URL is signed. So the
    session id travels in our own path, the minted `game_url` is the root,
    and the client's query — the wallet token among it — is dropped exactly
    as it is for every other publisher. A path naming a session we did not
    mint is refused rather than guessed at.
    """
    rest = sub[len(PG_PREFIX):]
    session_id, _, tail = rest.partition("/")
    session = pg_proxy.session_for(session_id)
    if session is None:
        raise ProxyError("no PG session for this launch; open the game again")
    root = urlsplit(session.game_url)
    path = tail if tail.startswith("/") else f"/{tail}" if tail else ""
    # the document itself carries the minted query (ot/l/btt); a sub-request
    # carries whatever the client sent, signatures included, untouched
    if path in ("", "/"):
        return checked_url(session.game_url)
    host = root.hostname
    if path.startswith(pg_proxy.MONEY_TAILS) and session.api_hosts:
        # the money API lives on the api hosts, not the game host: the
        # game host 404s /web-api/... (measured). Sticky to the first —
        # the publisher's access token is session-scoped, so spreading
        # one session's calls across both hosts would split it in two.
        host = session.api_hosts[0]
    url = f"https://{host}{path}"
    if query:
        url += f"?{query}"
    return checked_url(url)


def pg_document(sub: str) -> bool:
    """Is this sub-path the minted PG document itself (not an asset)?

    `pg/<session>` with nothing after it: the session is the document root,
    so this is the request that must get the `<base>` repair and the bridge.
    """
    if not sub.startswith(PG_PREFIX):
        return False
    session_id, _, tail = sub[len(PG_PREFIX):].partition("/")
    return bool(session_id) and tail.strip("/") == ""


def pg_doc_host(sub: str) -> str:
    """The host a PG document actually came from.

    The catalog says `public.pg-demo.com` — that is the *launcher*, not the
    game. The document is served from the minted session's own host, and the
    cookies that bind the session to that host have to name it, or a
    root-level follow-up would be fetched from the wrong origin.
    """
    if not sub.startswith(PG_PREFIX):
        return ""
    session_id, _, _tail = sub[len(PG_PREFIX):].partition("/")
    session = pg_proxy.session_for(session_id)
    return session.game_host if session else ""


def publisher_query(query: str, keep: tuple[str, ...] = ()) -> str:
    """The client's query string with our own session parameters removed.

    The wallet token rides along on a launcher redirect so the document we
    end up serving stays bound to the player. The publisher has no use for a
    player's credential, and forwarding it would put one in a third party's
    access log.

    `keep` names what has to stay: an interposed RGS reads its token off the
    launcher query (that is the token it hands back to us), so for those
    providers the parameter is the game's own plumbing, not a leak.
    """
    if not query:
        return ""
    drop = WALLET_PARAMS - set(keep)
    kept = [part for part in query.split("&")
            if part.partition("=")[0] not in drop]
    return "&".join(kept)


def rewritable(sub: str) -> bool:
    """Would a body fetched for this sub-path be rewritten before serving?"""
    if not sub:
        return True  # the game document: bridge + base href
    tail = sub.rsplit("?", 1)[0].rsplit("/", 1)[-1]
    if not tail:
        # a sub-path that ends in "/" is a document request, not an asset —
        # and that is exactly the shape every PG launch takes, because the
        # session id lives in our path: `/g/pg:fortune-tiger/pg/<session>/`.
        # Without this the PG document was passed through untouched, so the
        # game booted with no `<base>` repair and no bridge in front of it.
        return True
    if "." not in tail:
        return False
    return tail[tail.rfind("."):].lower() in _SCRIPT_EXTENSIONS


def rewriteable_type(content_type: str) -> bool:
    """Could a body of this content type be rewritten on the way out?

    True for the kinds the money-URL rewrite and the client patchers read.
    It is also the answer to "may a 304 be forwarded for this?": only a body
    no rewrite can touch is safe to leave empty.
    """
    kind = (content_type or "").lower()
    return any(k in kind for k in ("html", "javascript", "css", "json",
                                   "text/plain", "xml"))


def _header(headers: dict, name: str) -> str:
    """A header value, whatever case the publisher sent it in."""
    value = headers.get(name)
    if value is None:
        value = headers.get(name.lower())
    return (value or "").strip() if isinstance(value, str) else ""


def cache_policy(up_headers: dict, *, status: int = 200, rewritten: bool = False,
                 document: bool = False, money: bool = False) -> str:
    """The Cache-Control we serve a proxied body under.

    A balance is never cached, nor is an error (a publisher that answers 450
    from its edge does so for minutes, and a 404 pinned for a week is how a
    game that was fixed stays broken), a document or a body we rewrote is only
    ever revalidated (its bytes are ours, not the publisher's), and an
    untouched asset keeps the publisher's own caching so the bundle is fetched
    once.
    """
    if money or status >= 400:
        return "no-store"
    if document or rewritten:
        return "no-cache"
    return _header(up_headers, "Cache-Control") or DEFAULT_ASSET_CACHE


def validator_headers(up_headers: dict) -> dict:
    """The publisher's validators and range bookkeeping, kept as they are."""
    out: dict[str, str] = {}
    for name in VALIDATOR_HEADERS:
        value = _header(up_headers, name)
        if value:
            out[name] = value
    return out


def rewrite_urls(body: bytes, content_type: str, game_id: str,
                 our_origin: str = "", money: tuple[str, ...] = ()) -> bytes:
    """Point the publisher's MONEY urls at our origin, and nothing else.

    Only the RGS/wallet endpoints are rewritten (the provider's money
    patterns). Every other URL — the game client, its bundles, its art —
    keeps pointing at the publisher's CDN, which serves it directly to the
    browser (those hosts send `access-control-allow-origin: *`, so the
    game's asset XHRs work cross-origin).

    Proxying the assets is what broke the client: routed through us, the
    Unity importer deserialized an empty game root (`GameRoot.children.len=0`)
    — a timing/ordering sensitivity of its loader, not bad bytes; the same
    resources are byte-identical through the proxy. Leaving them on the CDN
    keeps the load sequence exactly as the publisher ships it. The game
    document itself is still served from our origin, so its money calls are
    same-origin to us.

    Rewrites stay absolute URLs on our origin (not root-relative): the
    game's config parser splits on "//" and derives schema/host from it, so
    the schema://host shape has to survive.
    """
    if not our_origin or not rewriteable_type(content_type):
        return body
    game = game_for(game_id)
    provider = (game or {}).get("provider") or ""
    if not money and not SERVICE_HOSTS and provider not in CLIENT_PATCHERS:
        return body
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return body
    hosts = provider_demos.DEMO_HOSTS | EXTRA_HOSTS
    for host in hosts:
        for pattern in money:
            rx = re.compile(
                rf"https?://{re.escape(host)}({pattern}[^\"'\s\\,;)]*)")
            text = rx.sub(
                lambda m: (f"{our_origin}{GAME_PREFIX}/{game_id}"
                           f"/_abs/{host}{m.group(1)}"),
                text)
    for host in SERVICE_HOSTS:
        text = re.sub(
            rf"https?://{re.escape(host)}/",
            f"{our_origin}{GAME_PREFIX}/{game_id}/_abs/{host}/",
            text)
    # A client bundle is script; the same bytes arriving as a document or a
    # config blob must not be rewritten, or the substitution lands inside
    # markup the publisher wrote.
    patcher = CLIENT_PATCHERS.get(provider)
    if patcher and "javascript" in (content_type or "").lower():
        # PP_RAW_CLIENT=1 forwards the publisher's bundle untouched. Some
        # clients (Pragmatic's) decode their own strings from a table keyed by
        # a hash of their source text, so a text patch can silently break
        # deserialization; this switch tells the two apart (decisions 0059).
        if os.environ.get("PP_RAW_CLIENT") != "1":
            text = patcher(text)
    return text.encode("utf-8")


# Spribe's client *mirrors* the vendor's hostnames onto the site's own domain:
# `app-demo2.spribegaming.com` becomes `app-demo2.<our-domain>`, because a real
# operator aliases those hosts under their own domain. A personal deploy has no
# such aliases, so the client dials a host that does not exist and sits on its
# connection screen forever. On a `*.spribegaming.com` host the mirror list
# exempts it and the real servers are used — which is why the game only ever
# worked from the publisher's own name. Switching mirroring off makes the
# client use the real hosts from any origin.
_SPRIBE_MIRROR = re.compile(r"mirrorHostname\(([A-Za-z_$][\w$]*)\)\{")


def patch_spribe_client(text: str) -> str:
    """Serve Spribe's client with hostname mirroring turned off."""
    return _SPRIBE_MIRROR.sub(r"mirrorHostname(\1){return \1;", text, count=1)


# Pragmatic Play ships a Unity-exported client. Off the publisher's own origin
# its importer hits two reference-resolution bugs — the bundle resolves some
# references by hard-coded index, and those indices only line up when every
# resource arrives in the publisher's own load order. Both are fixed the same
# way: look for the object that actually carries the thing instead of trusting
# the index. Text substitutions, applied only to that publisher's client.
UNITY_FIXES: tuple[tuple[str, str], ...] = (
    # internalContinueImporting picks the game root by index; search every
    # root object for the one that carries a LocalizationRoot (the index
    # points at an empty shell that has none).
    ("var parent=ret.objects[JsonTypes.indexOf(0)]"
     ".GetComponentsInChildren(LocalizationRoot,true)[0].transform;",
     "var parent=(function(){for(var _i=0;_i<ret.objects.length;_i++){"
     "try{var _c=ret.objects[_i].GetComponentsInChildren(LocalizationRoot,true);"
     "if(_c&&_c.length)return _c[0].transform}catch(_e){}}"
     "return ret.objects[JsonTypes.indexOf(0)].transform})();"),
    # the same blind lookup through the scene roots
    ("roots[1].transform.GetComponentsInChildren(LocalizationRoot,true)[0].transform",
     "(function(){for(var _i=0;_i<roots.length;_i++){try{"
     "var _c=roots[_i].transform.GetComponentsInChildren(LocalizationRoot,true);"
     "if(_c&&_c.length)return _c[0].transform}catch(_e){}}})()"),
    # the operator config deserializes as a PPtr with no guid, so it can land
    # on the wrong component and arrive without its text; fall back to xtLayer
    ('ServerInterface.prototype.ParseConfigFile=function(){var lines='
     'this.configFile.text.split("\\n");',
     'ServerInterface.prototype.ParseConfigFile=function(){'
     'if(!this.configFile||!this.configFile.text){'
     'if(this.xtLayer&&this.xtLayer.text)this.configFile=this.xtLayer}'
     'var lines=this.configFile.text.split("\\n");'),
)


# Pragmatic's importer decrypts every component's field values in place, with a
# permutation keyed on the component's `wasabiCode` *and* on three readings of
# its environment: the browser's user agent, the wall clock, and
# `location.hostname`. Each is compared against an RSA-signed table the game
# config carries (`sessionKeyV2`), and the permutation only comes out
# deterministic when all three match. Served from any other origin two of the
# three can never match, so the permutation is rebuilt differently per call and
# every field decrypts to garbage: the stage list arrives empty, the loader
# stops on its splash, and the only symptom is a `Cannot read properties of
# undefined` from deep inside their deserializer (decisions 0059/0062).
#
# The check reads two plain globals the bundle captured at load — `_634` (the
# user agent) and `_4025` (the hostname) — so pinning those to the signed values
# restores the intended permutation. The values come out of the decrypted table
# at read time (the deserializer writes it before it decrypts the first field),
# so a publisher that changes them does not need a code change; the shipped
# constants are only the fallback when that lookup is unavailable.
_PP_SESSION_PIN = """(function(){var FALLBACK_UA='Mozilla/5.0 (Windows NT 10.0; \
Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',\
FALLBACK_HOST='demogamesfree.pragmaticplay.net';\
function signed(name,fallback){try{var cfg=window.UHT_GAME_CONFIG_SRC,\
sk=cfg&&cfg.sessionKeyV2;if(sk&&sk.length){var key=String(sk[0]).replace(\
/[^0-9a-z-A-Z ]/g,''),raw=(window.Vars||{})[key];if(raw){var txt=\
String.fromCharCode.apply(null,String(raw).split(',').map(Number)),\
m=new RegExp('"'+name+'"\\\\s*:\\\\s*"([^"]*)"').exec(txt);if(m)return m[1];}}}\
catch(e){}return fallback;}\
function pin(name,get){try{Object.defineProperty(window,name,{configurable:true,\
enumerable:true,get:get,set:function(){}});}catch(e){}}\
pin('_634',function(){return signed('userAgent',FALLBACK_UA);});\
pin('_4025',function(){return signed('serverHostname',FALLBACK_HOST);});})();\n"""


def patch_unity_client(text: str) -> str:
    """Apply the Unity-client fixes to a Pragmatic Play bundle."""
    for old, new in UNITY_FIXES:
        if old in text:
            text = text.replace(old, new)
    return _PP_SESSION_PIN + _patch_animation_curves(text)


# Several animator components read `animationCurve.keys[...]`, and off the
# publisher's origin the curve can deserialize without its keys, which throws
# on the first frame. Rather than guard each of the ~42 call sites, every
# `X.animationCurve.keys` read goes through one helper that substitutes a
# flat two-point curve when the data is missing (the widget then simply does
# not animate, instead of killing the importer).
_ANIM_CURVE = re.compile(r"([A-Za-z_$][\w$.]*)\.animationCurve\.keys")
_ANIM_HELPER = ("function __acKeys(ac){return (ac&&ac.keys&&ac.keys.length)"
                "?ac.keys:[{time:0,value:0},{time:1,value:0}];}\n")


def _patch_animation_curves(text: str) -> str:
    if ".animationCurve.keys" not in text:
        return text
    text = _ANIM_CURVE.sub(r"__acKeys(\1.animationCurve)", text)
    return _ANIM_HELPER + text


# provider -> the fix its own client needs to boot off the publisher's origin
# (decisions 0027/0036). Only ever applied to a script body.
CLIENT_PATCHERS = {
    "pragmatic_play": patch_unity_client,
    "spribe": patch_spribe_client,
}


_BASE_TAG = re.compile(r"<base\b[^>]*>", re.I)
_BASE_HREF = re.compile(r"""(href\s*=\s*)(["'])[^"']*\2""", re.I)


def rebase(html: bytes, base: str) -> bytes:
    """Give a proxied document its own `<base href>`.

    A single-page game ships `<base href="/">`, so both its asset URLs and its
    client-side routes resolve against the origin root. Served under a proxy
    path that is not the root, its router matches no route and the game never
    initialises — it sits on its connection screen with the config loaded.
    Pointing the base at the document's own path restores both.

    The tag is matched rather than its exact spelling: a publisher that
    writes `<base href='/'>` or `<base target=_top>` gets the same treatment,
    because the silent miss is a game that loads nothing and says nothing.
    """
    if not base:
        return html
    try:
        text = html.decode("utf-8")
    except UnicodeDecodeError:
        return html

    def point_at_proxy(match: re.Match) -> str:
        tag = match.group(0)
        if _BASE_HREF.search(tag):
            return _BASE_HREF.sub(
                lambda m: f"{m.group(1)}{m.group(2)}{base}{m.group(2)}",
                tag, count=1)
        return f'{tag[:-1]} href="{base}">'

    fixed, n = _BASE_TAG.subn(point_at_proxy, text, count=1)
    return fixed.encode("utf-8") if n else html


def fmt_balance(minor: int) -> str:
    """Render minor units the way the RGS does: 123456 -> "1,234.56"."""
    whole, cents = divmod(int(minor), 100)
    return f"{whole:,}.{cents:02d}"


def rewrite_balance(body: bytes, balance_minor: int) -> bytes:
    """Replace the RGS balance fields with our wallet's saldo.

    The gameService answers are form-encoded and carry the
    saldo as balance=…&balance_cash=…; the game shows whatever
    the RGS says, so our value goes in its place.
    """
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return body
    value = fmt_balance(balance_minor)
    changed = False
    for key in ("balance", "balance_cash"):
        rx = rf"({key}=)[^&]*"
        if re.search(rx, text):
            text = re.sub(rx, rf"\g<1>{value}", text)
            changed = True
    return text.encode("utf-8") if changed else body


# The two fields the Pragmatic client adds up to know its saldo: the answer
# carries `balance` and `balance_bonus`, and the client paints their sum
# (`XT.GetDouble(Vars.BalanceReceived) + XT.GetDouble(Vars.BonusBalanceReceived)`,
# read off its own bundle). The tap has to read the same total, or a round paid
# out of bonus money would look like no movement at all.
_BALANCE_FIELD = re.compile(r"(?:^|&)(balance|balance_bonus)=([^&]*)")


def publisher_balance_minor(body: bytes) -> int | None:
    """The saldo a Pragmatic RGS answer reports, in centavos, or None.

    The publisher renders it as "100,000.00" (and as a bare float in an
    error answer), so the thousands separators come off before the number
    is read. An answer carrying neither field is not a money answer and
    gives None — a caller must not read that as a zero balance.
    """
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    total = 0
    found = False
    for match in _BALANCE_FIELD.finditer(text):
        try:
            total += int(round(float(match.group(2).replace(",", "")) * 100))
        except ValueError:
            return None
        found = True
    return total if found else None


# A `doSpin` answer names its own round: `w` is the win, `c` the coin and `l`
# the lines (the client's own `coin * lines`, which is what a minimum bet of
# `c=0.1&l=20` reads as R$2.00), and `ntp` the net. A `doInit` or a
# `reloadBalance.do` carries none of them, which is how a read is told from a
# round without trusting the path it arrived on.
_ROUND_FIELDS = re.compile(r"(?:^|&)(c|l|w|ntp)=([^&]*)")


def spin_round(body: bytes) -> tuple[int, int] | None:
    """The (stake, payout) a Pragmatic round answer names, in centavos.

    The publisher's own accounting is in the answer — the bet it settled
    (`c`×`l`) and the win (`w`) — so the split does not have to be inferred
    from the movement of the saldo, which knows only the net. `w` is
    required: an answer without it is not a round. None is returned when the
    fields are absent or do not describe a coherent round, so the caller can
    fall back to the movement.
    """
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    fields = {match.group(1): match.group(2)
              for match in _ROUND_FIELDS.finditer(text)}
    if "w" not in fields:
        return None

    def minor(value: str) -> int:
        return int(round(float(value.replace(",", "")) * 100))

    try:
        payout = minor(fields["w"])
        if "c" in fields and "l" in fields:
            stake = int(round(float(fields["c"].replace(",", "")) *
                              float(fields["l"]) * 100))
        elif "ntp" in fields:
            stake = payout - minor(fields["ntp"])
        else:
            return None
    except ValueError:
        return None
    if stake < 0 or payout < 0:
        return None
    return stake, payout


BRIDGE_MARK = b"<!--wallet-bridge-->"


def _script_json(payload: dict) -> str:
    """The bridge config as a JavaScript literal that cannot end its script.

    The symbol and language come off a publisher URL, so they are third-party
    text landing inside a `<script>` element. JSON escapes quotes but not
    `<`, which is all a `</script>` needs; the line separators that are legal
    in JSON strings are not legal in JavaScript source.
    """
    import json as _json
    text = _json.dumps(payload)
    for char, escape in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"),
                         ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        text = text.replace(char, escape)
    return text

_BRIDGE = r"""
'use strict';
(function () {
  var cfg = window.__WALLET__ || {token: '', api: '/api'};
  var minStake = cfg.min_stake_minor || 200;
  var balance = cfg.balance_minor || 0;
  var bonus = cfg.bonus_minor || 0;
  function total() { return balance + bonus; }

  // The bridge is injected in <head>, so the document may have no body yet
  // (and a game frame can hand it a detached document). HUD elements go on
  // whatever root exists; a missing one must not take the money path down.
  function root() {
    return document.body || document.documentElement || null;
  }

  function hud() {
    var host = root();
    if (!host) return;
    var el = document.getElementById('__wallet_hud');
    if (!el) {
      el = document.createElement('div');
      el.id = '__wallet_hud';
      el.style.cssText = 'position:fixed;right:12px;top:12px;z-index:2147483647;' +
        'font:600 13px system-ui;padding:6px 12px;border-radius:9px;background:#0b1220;' +
        'color:#fff;border:1px solid #2a3550;box-shadow:0 6px 20px rgba(0,0,0,.4)';
      host.appendChild(el);
    }
    el.textContent = 'Saldo: R$ ' + (total() / 100).toFixed(2);
    el.style.background = total() >= minStake ? '#0b1220' : '#5a1010';
  }
  function tell(msg) {
    var host = root();
    if (!host) return;
    var el = document.getElementById('__wallet_msg');
    if (!el) {
      el = document.createElement('div');
      el.id = '__wallet_msg';
      el.style.cssText = 'position:fixed;left:50%;top:40%;transform:translateX(-50%);' +
        'z-index:2147483647;font:700 16px system-ui;padding:14px 22px;border-radius:12px;' +
        'background:#5a1010;color:#fff;display:none';
      host.appendChild(el);
    }
    el.textContent = msg; el.style.display = 'block';
    setTimeout(function () { el.style.display = 'none'; }, 3500);
  }

  function refresh() {
    return fetch(cfg.api + '/wallet/status?token=' + encodeURIComponent(cfg.token))
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d) { balance = d.balance_minor || 0; bonus = d.bonus_minor || 0; hud(); } });
  }

  // Rewrite the callee URL so the operator (not the game) decides money.
  function watch(promise, url, opts) {
    return promise;
  }

  var _fetch = window.fetch;
  window.fetch = function (input, init) {
    var url = typeof input === 'string' ? input : (input && input.url) || '';
    var method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    if (cfg.bet_url && method === 'POST' && new RegExp(cfg.bet_url).test(url)) {
      if (total() < minStake) {
        tell('Saldo insuficiente — deposite para girar.');
        return Promise.resolve(new Response('{}', { status: 402, headers: {'content-type':'application/json'} }));
      }
    }
    return watch(_fetch.apply(this, arguments), url, init);
  };

  // The Unity client fetches its own bundle (build.js) with an XHR off the
  // publisher's CDN and evals the body. Everything the proxy knows about that
  // client (index-based reference resolution, the config-file fallback, the
  // animation-curve repair — game_proxy.patch_unity_client) only reaches it if
  // that one URL is fetched through us; loaded straight off the CDN it runs
  // unpatched and dies in the importer (decision 0058). Rewrite just the
  // bundle: every other asset deliberately stays on the CDN, because proxying
  // the asset tree changes the import order (decision 0028).
  function pp_proxied_client_script(url) {
    if (typeof url !== 'string') return url;
    if (!cfg.game_id || cfg.game_id.indexOf('pp:') !== 0) return url;
    if (!/^https?:\/\/demogamesfree\.pragmaticplay\.net\/.*\/build\.js(\?|$)/.test(url)) {
      return url;
    }
    return location.origin + '/g/' + cfg.game_id + '/_abs/' +
      url.replace(/^https?:\/\//, '');
  }

  if (window.XMLHttpRequest) {
    var _open = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
      url = pp_proxied_client_script(url);
      this.__url = url; this.__method = (method || 'GET').toUpperCase();
      var rest = Array.prototype.slice.call(arguments, 2);
      return _open.apply(this, [method, url].concat(rest));
    };
    var _send = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function (body) {
      if (cfg.bet_url && this.__method === 'POST' && new RegExp(cfg.bet_url).test(this.__url || '')) {
        if (total() < minStake) {
          tell('Saldo insuficiente — deposite para girar.');
          this.abort();
          return;
        }
      }
      return _send.apply(this, arguments);
    };
  }

  // --- Pragmatic Play origin split (decision 0028/0030) --------------------
  // The Unity client derives everything "server" from location.host, so off
  // the publisher's origin it misresolves its own resources. Split the two
  // roles: identity stays the publisher's host, calls go to us (same-origin,
  // through the proxy). The bundle assigns GetDomain itself, so this polls
  // until the client object exists and then holds the split every 100ms —
  // the boot is async (dozens of resources), so the poll wins the race.
  if (cfg.game_id && cfg.game_id.indexOf('pp:') === 0) {
    var PP_HOST = 'demogamesfree.pragmaticplay.net';
    setInterval(function () {
      try {
        if (window.ServerInterface) {
          if (window.ServerInterface.GetDomain !== __ppDomain) {
            window.ServerInterface.GetDomain = __ppDomain;
          }
          if (window.ServerOptions && window.ServerOptions.serverUrl &&
              window.ServerOptions.serverUrl.indexOf(PP_HOST) >= 0) {
            window.ServerOptions.serverUrl = window.ServerOptions.serverUrl
              .replace(/^https?:\/\/[^/]+/, location.origin);
          }
          // The client hardcodes https:// + GetDomain(); on a plain-http
          // origin (local dev) that is an unreachable TLS target. serverUrl
          // is meant to be the document origin, so pin it there.
          if (window.ServerOptions && window.ServerOptions.serverUrl &&
              window.ServerOptions.serverUrl.replace(/^https?:\/\//, '')
                    .split('/')[0] !== location.host) {
            window.ServerOptions.serverUrl = window.ServerOptions.serverUrl
              .replace(/^https?:\/\/[^/]+/, location.origin);
          }
        }
      } catch (e) {}
    }, 100);
    // --- importer tree repair (decision 0036) -----------------------------
    // Off-origin the import finishes with the scene graph only half linked:
    // the LocalizationRoot carrier exists with intact parent links, but the
    // parents' children arrays stay empty, so the client's fixed-index
    // game-root lookup throws and the frame loop dies on the loading
    // screen. Reattach bottom-up along the existing parent links every
    // 250ms until the scene roots are adopted; parents created later get
    // linked on a later tick. Harmless on a healthy tree (pushes nothing).
    setInterval(function () {
      try {
        var imp = window.globalImporter;
        if (!imp || !imp.allObjects || imp.allObjects.length < 1000) return;
        if (window.globalRuntime && window.globalRuntime.sceneRoots &&
            window.globalRuntime.sceneRoots.length >= 2) return;
        var fixed = 0;
        for (var i = 0; i < imp.allObjects.length; i++) {
          var o = imp.allObjects[i];
          if (!o || !o.transform) continue;
          var t = o.transform, p = t.parent;
          if (p && p.children && p.children.indexOf(t) < 0 && fixed < 500) {
            p.children.push(t);
            fixed++;
          }
        }
      } catch (e) {}
    }, 250);
    // --- animator curve guard (decision 0036) ------------------------------    // The same half-linked import leaves some animator components with an
    // empty/missing animationCurve, and their Start/Update read keys[0] —
    // the next boot-killer after the game-root lookup (seen live in
    // WidgetColorAnimator.Start via the operator logo bundle). Wrap every
    // *Animator Start/Update to substitute a flat two-point curve when the
    // data is missing: the widget simply does not animate instead of
    // killing the boot. Wrapping is per-class, once, as each class shows
    // up; instances that already started are unaffected.
    var ANIMATORS = ['WidgetColorAnimator', 'V3Animator', 'ValueAnimator',
      'PanelAlphaAnimator', 'CurveValueAnimator', 'CurveTwoValuesAnimator',
      'SpriteFramesAnimator', 'SpriteSizeAnimator', 'ScrollableListAnimator',
      'SpineCustomAnimator', 'AudioClipValueAnimator',
      'ValueAnimatorWithBigWin'];
    function __ppFixCurve(inst) {
      try {
        var ac = inst.animationCurve;
        if (!ac) { inst.animationCurve = ac = {}; }
        if (!ac.keys || !ac.keys.length) {
          ac.keys = [{ time: 0, value: 0 }, { time: 1, value: 0 }];
        }
        if (typeof ac.Evaluate !== 'function') {
          ac.Evaluate = function () { return 0; };
        }
      } catch (e) {}
    }
    setInterval(function () {
      try {
        for (var i = 0; i < ANIMATORS.length; i++) {
          var C = window[ANIMATORS[i]];
          if (!C || !C.prototype) continue;
          var keys = [];
          try { keys = Object.getOwnPropertyNames(C.prototype); } catch (e) {}
          for (var k = 0; k < keys.length; k++) {
            var m = keys[k];
            if (m === 'constructor') continue;
            if (typeof C.prototype[m] === 'function' && !C.prototype[m].__ppGuard) {
              var orig = C.prototype[m];
              var wrapped = function () {
                __ppFixCurve(this);
                return orig.apply(this, arguments);
              };
              wrapped.__ppGuard = true;
              C.prototype[m] = wrapped;
            }
          }
        }
      } catch (e) {}
    }, 500);
    // --- per-frame choke shield (decision 0036) ------------------------------
    // Every per-frame Update flows through Runtime.CallOnGameObjectList; one
    // bad widget there kills the frame ahead of the login update, forever.
    // Isolate failures per component so the loop (and the login) survive;
    // first few are logged, the rest counted.
    setInterval(function () {
      try {
        var R = window.Runtime;
        if (R && R.prototype &&
            typeof R.prototype.CallOnGameObjectList === 'function' &&
            !R.prototype.CallOnGameObjectList.__ppGuard) {
          var frameErrs = 0;
          R.prototype.CallOnGameObjectList = function (listDesc, methodName, compIdxName) {
            var comps = (listDesc && listDesc.components) || [];
            for (var i = 0; i < comps.length; i++) {
              var c = comps[i];
              if (c == null) continue;
              try {
                c[methodName]();
              } catch (e) {
                frameErrs++;
                if (frameErrs <= 6) {
                  try { console.warn('[pp-shield] frame ' + methodName + ' on ' +
                    (c.constructor && c.constructor.name) + ': ' +
                    String(e).slice(0, 110)); } catch (x) {}
                }
              }
            }
          };
          R.prototype.CallOnGameObjectList.__ppGuard = true;
        }
      } catch (e) {}
    }, 500);
    // The remaining boot killers are all one shape: a component whose
    // deserialized reference came back empty throws inside Awake/Start (and
    // now OnEnable) and aborts the whole recursive dispatch, freezing the
    // game on its loader. Re-dispatch per component so one bad widget is
    // skipped (logged) while its siblings and children still boot. Each
    // skipped site stays visible in the console; the targeted sanitizers
    // above remain the real fixes where they apply.
    setInterval(function () {
      // Each install is guarded on its own: one throw while patching the Awake
      // dispatcher used to abort the whole block, so the OnEnable shield was
      // never installed and nothing said so.
      if (typeof callComponentCallback === 'function' &&
          !callComponentCallback.__ppGuard) {
        try {
          var origCCC = callComponentCallback;
          var errors = 0;
          var skipLog = function (phase, comp, e) {
            if (errors < 8) {
              errors++;
              try { console.warn('[pp-shield] skipped ' + phase + ' on ' +
                (comp && comp.constructor && comp.constructor.name) + ': ' +
                String(e).slice(0, 120)); } catch (x) {}
            }
          };
          callComponentCallback = function (go, funcToCall, flagToSet) {
            if (!go || go.activeInHierarchy === false) return;
            var comps = go.components || [];
            for (var i = 0; i < comps.length; i++) {
              var comp = comps[i];
              try {
                if ((comp.flags & flagToSet) === 0) {
                  comp.flags = comp.flags | flagToSet;
                  comp[funcToCall]();
                }
              } catch (e) { skipLog(funcToCall, comp, e); }
            }
            var kids = (go.transform && go.transform.children) || [];
            for (var c = 0; c < kids.length; c++) {
              try {
                callComponentCallback(kids[c].gameObject, funcToCall, flagToSet);
              } catch (e) {}
            }
          };
          callComponentCallback.__ppGuard = true;
        } catch (e) {
          try { console.warn('[pp-shield] Awake dispatcher not guarded: ' +
            String(e).slice(0, 120)); } catch (x) {}
        }
      }
      if (typeof callComponentOnEnable === 'function' &&
          !callComponentOnEnable.__ppGuard) {
        try {
          var origCOE = callComponentOnEnable;
          callComponentOnEnable = function (go) {
            if (!go || go.activeInHierarchy === false) return;
            var comps = go.components || [];
            for (var i = 0; i < comps.length; i++) {
              var comp = comps[i];
              try {
                if ((comp.flags & ComponentStateFlags.onEnable_called) === 0) {
                  callOnEnable(comp);
                }
              } catch (e) {
                try { console.warn('[pp-shield] skipped OnEnable on ' +
                  (comp && comp.constructor && comp.constructor.name) + ': ' +
                  String(e).slice(0, 120)); } catch (x) {}
              }
            }
            var kids = (go.transform && go.transform.children) || [];
            for (var c = 0; c < kids.length; c++) {
              try {
                callComponentOnEnable(kids[c].gameObject);
              } catch (e) {}
            }
          };
          callComponentOnEnable.__ppGuard = true;
        } catch (e) {
          try { console.warn('[pp-shield] OnEnable dispatcher not guarded: ' +
            String(e).slice(0, 120)); } catch (x) {}
        }
      }
    }, 500);
    // Same half-linked import class, one site at a time (each verified live
    // as the boot's next blocker): ensure the shapes the client assumes.
    setInterval(function () {
      try {
        var CI = window.CAT_Infector;
        if (CI && CI.prototype && typeof CI.prototype.Infect === 'function' &&
            !CI.prototype.Infect.__ppGuard) {
          var origInfect = CI.prototype.Infect;
          CI.prototype.Infect = function (evtInfection, hostCat) {
            try {
              if (hostCat && hostCat.events) {
                for (var i = 0; i < hostCat.events.length; i++) {
                  if (hostCat.events[i] && !hostCat.events[i].actions) {
                    hostCat.events[i].actions = [];
                  }
                }
              }
            } catch (e) {}
            try { return origInfect.apply(this, arguments); }
            catch (e) { return; }
          };
          CI.prototype.Infect.__ppGuard = true;
        }
        var AC = window.AnimationController;
        if (AC && AC.prototype && typeof AC.prototype.Play === 'function' &&
            !AC.prototype.Play.__ppGuard) {
          var origPlay = AC.prototype.Play;
          AC.prototype.Play = function () {
            try {
              if (!this.target ||
                  typeof this.target.GetAnimationState !== 'function') return;
            } catch (e) { return; }
            try { return origPlay.apply(this, arguments); }
            catch (e) { return; }
          };
          AC.prototype.Play.__ppGuard = true;
        }
        var RM = window.VS_ReelsManager;
        if (RM && RM.prototype &&
            typeof RM.prototype.AllReelsAreInvalidated === 'function' &&
            !RM.prototype.AllReelsAreInvalidated.__ppGuard) {
          var origV = RM.prototype.AllReelsAreInvalidated;
          RM.prototype.AllReelsAreInvalidated = function () {
            try { if (!this.validateReelSpin) this.validateReelSpin = []; }
            catch (e) {}
            try { return origV.apply(this, arguments); }
            catch (e) { return false; }
          };
          RM.prototype.AllReelsAreInvalidated.__ppGuard = true;
        }
        var GLR = window.GameLogicRuntime;
        if (GLR && GLR.prototype &&
            typeof GLR.prototype.Update === 'function' &&
            !GLR.prototype.Update.__ppGuard) {
          var origGLR = GLR.prototype.Update;
          GLR.prototype.Update = function () {
            try { if (!this.currentStage) return; }
            catch (e) { return; }
            try { return origGLR.apply(this, arguments); }
            catch (e) { return; }
          };
          GLR.prototype.Update.__ppGuard = true;
        }
        var ECA = window.ExtraCameraSettingsAnchors;
        if (ECA && ECA.prototype &&
            typeof ECA.prototype.Update === 'function' &&
            !ECA.prototype.Update.__ppGuard) {
          var origECA = ECA.prototype.Update;
          ECA.prototype.Update = function () {
            try {
              if (!this.extraCameraSettings || !this.anchorUpLeft ||
                  !this.anchorDownRight ||
                  typeof this.anchorUpLeft.position !== 'function' ||
                  typeof this.anchorDownRight.position !== 'function') return;
            } catch (e) { return; }
            try { return origECA.apply(this, arguments); }
            catch (e) { return; }
          };
          ECA.prototype.Update.__ppGuard = true;
        }
      } catch (e) {}
    }, 500);
    // --- session kickstart (decision 0036) -----------------------------------
    // The import/linkage repairs get the client to a clean idle loop, but
    // the server session never starts on its own off-origin (the init event
    // chain needs a ServerLink + the document's own game config, and the
    // trigger that fires it on the publisher's origin never fires here).
    // Reproduce the chain, retrying each step until its effect is visible:
    // ensure ServerLink on the ServerConnector, feed it the document's
    // gameConfig, then fire the per-symbol init request. Verified live step
    // by step: the client then POSTs gameService through our proxy.
    setInterval(function () {
      try {
        if (!window.globalImporter || !window.globalImporter.allObjects) return;
        if (window.LoaderProgress && window.LoaderProgress.InitConnection_Current > 0) return;
        var all = window.globalImporter.allObjects;
        var sc = null;
        for (var i = 0; i < all.length; i++) {
          try {
            if (all[i].name === 'ServerConnector') { sc = all[i]; break; }
          } catch (e) {}
        }
        if (!sc) return;
        var sl = null;
        for (var c = 0; c < (sc.components || []).length; c++) {
          try {
            if (sc.components[c].constructor.name === 'ServerLink') { sl = sc.components[c]; break; }
          } catch (e) {}
        }
        if (!sl) {
          try { sl = sc.AddComponent('ServerLink'); } catch (e) { return; }
        }
        if (!sl) return;
        if (!window.__ppCfgDone) {
          try {
            var cfgText = null;
            var scripts = document.scripts;
            for (var s = 0; s < scripts.length && !cfgText; s++) {
              var m = (scripts[s].textContent || '').match(/gameConfig:\s*'((?:[^'\\]|\\.)*)'/);
              if (m) cfgText = m[1];
            }
            if (cfgText) {
              var cfgObj = JSON.parse(cfgText.replace(/\\u003d/g, '='));
              sl.OnApplicationConfigReceived(cfgObj);
              window.__ppCfgDone = true;
            } else {
              return;
            }
          } catch (e) { return; }
        }
        if (window.__ppCfgDone && !window.__ppInitDone) {
          try {
            var sym = (cfg.pp_symbol || 'vs20olympgate');
            sl.requestQueue.push(sym);
            if (window.GameEvents && window.EventManager) {
              EventManager.Trigger(GameEvents.evtInitRequest + sym, null);
            }
            window.__ppInitDone = true;
          } catch (e) {}
        }
      } catch (e) {}
    }, 2000);
    // Same half-linked import class: the ServerInterface config file
    // (user/domain/symbol/lang lines) can deserialize empty off-origin and
    // ParseConfigFile dies on text.split. Synthesize the file from the
    // launch values the server put in the bridge config, then run the real
    // parser so every downstream field is set exactly as designed.
    setInterval(function () {
      try {
        var S = window.ServerInterface;
        if (S && S.prototype && typeof S.prototype.ParseConfigFile === 'function' &&
            !S.prototype.ParseConfigFile.__ppGuard) {
          var origParse = S.prototype.ParseConfigFile;
          S.prototype.ParseConfigFile = function () {
            try {
              if (!this.configFile || !this.configFile.text) {
                var sym = cfg.pp_symbol || 'vs20olympgate';
                var lang = cfg.pp_lang || 'en';
                this.configFile = { text: ['emul', '8fd105b3fbc1b',
                  'test1.gp16.pragmaticplay.net', 'ext_test1',
                  sym, lang].join('\n') };
              }
            } catch (e) {}
            try { return origParse.apply(this, arguments); }
            catch (e) { return; }
          };
          S.prototype.ParseConfigFile.__ppGuard = true;
        }
      } catch (e) {}
    }, 500);
  }
  // The client builds its server calls as `schema://GetDomain() + <path>`,
  // and `<path>` is the money URL our proxy rewrote (an absolute URL on our
  // origin whose path is /g/<id>/_abs/<host>/...). Returning the publisher's
  // host here made the client prepend *it* to our path, so every gameService
  // call flew to https://<publisher>/g/<id>/_abs/... and failed — the launcher
  // answered our saldo while the spin itself never landed. Our host is what
  // the call has to resolve against; the publisher's identity survives in the
  // rewritten paths and in the asset URLs, which are untouched.
  function __ppDomain() { return location.host; }

  // --- socket money tap ---------------------------------------------------
  // Some publishers drive the round over a socket the page itself holds
  // (Play'n GO's SignalR game hub), not over HTTP we can read. Watch that
  // socket: the spin line carries the stake, and the balance line answered
  // right after gives the round's net — which settles on OUR books. A spin
  // our saldo cannot cover is held back. The publisher's own server is
  // untouched; we only read what the page already sends and receives.
  var lastBalance = null, pendingStake = null, roundSeq = 0;

  function latin1(data) {
    if (typeof data === 'string') return data;
    try {
      var u8 = data instanceof ArrayBuffer ? new Uint8Array(data)
                                           : new Uint8Array(data.buffer || data);
      var s = '';
      for (var i = 0; i < u8.length; i++) s += String.fromCharCode(u8[i]);
      return s;
    } catch (e) { return ''; }
  }

  // Play'n GO speaks a line protocol inside its frames: a spin request line is
  // "1 <credits> <lines> <coin> <flag>" (the stake is their product) and the
  // answer carries "52 <balance> 0 0", the account balance in minor units.
  var SPIN = /(?:^|\r?\n)1 (-?\d+(?: -?\d+)+)/;
  var BALANCE = /(?:^|\r?\n)52 (-?\d+)/;

  // --- PG Soft theater tap -------------------------------------------------
  // game-api is fully encrypted: every Spin request and answer is opaque
  // bytes, so there is no spin to re-encode and no win to read. But the
  // handshake is plaintext, and the trial wallet answers plain JSON.
  // Harvest the access token off the verifySession answer, and after every
  // Spin reconcile the trial wallet through the publisher's own endpoint:
  // its delta IS the round result, settled on our books through the same
  // /wallet/round the socket tap uses. Stakes are learned from losses (a
  // loss is exactly -stake); the settled BALANCE is always exact, the
  // stake/payout split is bookkeeping around it. Without a login
  // (cfg.token empty) the report 401s and is silently dropped: free play.
  var pgAtk = null, pgApi = null, pgLast = null, pgStake = null, pgSeq = 0,
      pgChain = Promise.resolve();

  function pgHarvest(url, text) {
    if (!url || url.indexOf("verifySession") < 0 || pgAtk) return;
    try {
      var tk = JSON.parse(text).dt.tk;
      if (tk) {
        pgAtk = tk;
        pgApi = url.split("/web-api/")[0];
        pgPoll().then(function (cb) { pgLast = cb; });
      }
    } catch (e) {}
  }

  function pgWalletUrl() {
    return pgApi + "/web-api/game-proxy/v2/GameWallet/Get";
  }

  function pgPoll() {
    if (!pgAtk || !pgApi) return Promise.resolve(null);
    var body = "isagw=true&btt=2&wk=0_C&atk=" + encodeURIComponent(pgAtk) +
      "&pf=1&gid=" + encodeURIComponent(cfg.pg_gi || "");
    return fetch(pgWalletUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body,
    }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        return d && d.dt && typeof d.dt.cb === "number" ? d.dt.cb : null;
      }).catch(function () { return null; });
  }

  function pgSettle(netUnits, first) {
    var netMinor = Math.round(netUnits * 100);
    var stake;
    if (netMinor < 0 && (pgStake === null || -netMinor >= pgStake)) {
      pgStake = -netMinor;
      stake = pgStake;
    } else {
      stake = first ? (pgStake || 0) : 0;
    }
    var payout = Math.max(0, stake + netMinor);
    if (!stake && !payout) return Promise.resolve();
    return reportRound(stake, payout);
  }

  function pgWatch() {
    // trailing wins (respin features) land after the spin resolves: watch
    // until the wallet stills, settling the first move with the stake and
    // every later move as a pure win. Serialized: a spin while one settles
    // waits its turn instead of double-reading the same delta.
    pgChain = pgChain.then(function () {
      return pgPoll().then(function (base) {
        if (base === null) return;
        var first = true, calm = 0;
        return new Promise(function (done) {
          var timer = setInterval(function () {
            pgPoll().then(function (cb) {
              if (cb === null) { clearInterval(timer); done(); return; }
              var net = cb - (first ? base : pgLast);
              pgLast = cb;
              if (net !== 0) {
                calm = 0;
                pgSettle(net, first).catch(function () {});
                first = false;
              } else if (++calm >= 4) {
                clearInterval(timer);
                done();
              }
            });
          }, 800);
          setTimeout(function () { clearInterval(timer); done(); }, 12000);
        });
      });
    }).catch(function () {});
  }

  var _pgFetch = window.fetch;
  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    var promise = _pgFetch.apply(this, arguments);
    if (cfg.game_id && cfg.game_id.indexOf("pg:") === 0) {
      if (url.indexOf("verifySession") >= 0) {
        promise.then(function (r) {
          var c = r.clone();
          c.text().then(function (t) { pgHarvest(url, t); }).catch(function () {});
          return r;
        }).catch(function () {});
      } else if (url.indexOf("/v4/Spin") >= 0 &&
                 ((init && init.method) || "GET").toUpperCase() !== "GET") {
        promise.catch(function () {}).then(function () { pgWatch(); });
      }
    }
    return promise;
  };

  if (window.XMLHttpRequest) {
    var _pgOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
      this.__pgUrl = url;
      return _pgOpen.apply(this, arguments);
    };
    var _pgSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function (body) {
      if (cfg.game_id && cfg.game_id.indexOf("pg:") === 0 && this.__pgUrl) {
        var self = this, url = this.__pgUrl;
        this.addEventListener("load", function () {
          try {
            if (url.indexOf("verifySession") >= 0) pgHarvest(url, self.responseText);
            else if (url.indexOf("/v4/Spin") >= 0) pgWatch();
          } catch (e) {}
        });
      }
      return _pgSend.apply(this, arguments);
    };
  }

  function reportRound(stake, payout) {
    roundSeq += 1;
    var roundId = 'ws-' + roundSeq + '-' + Date.now();
    return fetch(cfg.api + '/wallet/round', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({token: cfg.token, round_id: roundId,
                            stake_minor: stake, payout_minor: payout}),
    }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (d) { balance = d.balance_minor || 0; bonus = d.bonus_minor || 0; hud(); }
      }).catch(function () {});
  }

  function watchSocket(ws) {
    var send = ws.send;
    ws.send = function (data) {
      var spin = SPIN.exec(latin1(data));
      if (spin) {
        var stake = spin[1].split(' ').slice(0, 3)
          .reduce(function (a, b) { return a * Math.abs(parseInt(b, 10) || 0); }, 1);
        if (stake > 0) {
          if (total() < stake) {
            tell('Saldo insuficiente — deposite para girar.');
            return;
          }
          pendingStake = stake;
        }
      }
      return send.apply(ws, arguments);
    };
    ws.addEventListener('message', function (ev) {
      var found = BALANCE.exec(latin1(ev.data));
      if (!found) return;
      var now = parseInt(found[1], 10);
      if (lastBalance === null) { lastBalance = now; return; }
      var net = now - lastBalance;
      lastBalance = now;
      if (pendingStake === null) return;
      var stake = pendingStake;
      pendingStake = null;
      reportRound(stake, Math.max(0, stake + net));
    });
  }

  // --- Spribe tap ----------------------------------------------------------
  // Spribe runs the round over a SmartFoxServer socket the page holds
  // (wss://<game>-demo.spribegaming.com/BlueBox/websocket); the bet is not an
  // HTTP call we can read. The frames are SFS2X binary — a type-tagged stream
  // whose string keys are literal, so the account balance reads straight out
  // of a frame as the big-endian double that follows the key "balance" (the
  // opening saldo, in the join answer) or "newBalance" (after every change).
  // A drop is the stake leaving that saldo, a later rise is our cash-out's
  // payout, and the round's chart line is posted at the crash, when the stake
  // is gone. Each is mirrored onto OUR books through /wallet/round, the same
  // idempotent write the other taps use. The publisher's server is untouched;
  // we only read what the page already receives.
  function bytesOf(data) {
    try {
      if (data instanceof ArrayBuffer) return new Uint8Array(data);
      if (data && data.buffer instanceof ArrayBuffer)
        return new Uint8Array(data.buffer, data.byteOffset || 0,
                              data.byteLength);
    } catch (e) {}
    return null;
  }

  function asciiAt(buf, i, s) {
    if (i < 0 || i + s.length > buf.length) return false;
    for (var j = 0; j < s.length; j++)
      if (buf[i + j] !== s.charCodeAt(j)) return false;
    return true;
  }

  function hasString(buf, s) {
    for (var i = 0; i + s.length <= buf.length; i++)
      if (asciiAt(buf, i, s)) return true;
    return false;
  }

  // An SFS key is <len:2><utf8> and a DOUBLE is a 0x07 tag then 8 bytes big
  // endian. Anchor on the literal key so nothing has to be re-encoded.
  function doubleForKey(buf, dv, key) {
    for (var i = 2; i + key.length + 9 <= buf.length; i++) {
      if (!asciiAt(buf, i, key)) continue;
      if (((buf[i - 2] << 8) | buf[i - 1]) !== key.length) continue;
      if (buf[i + key.length] !== 7) continue;
      return dv.getFloat64(i + key.length + 1, false);
    }
    return null;
  }

  function spribeWatch(ws) {
    var last = null, pending = null, chain = Promise.resolve();

    function handle(buf) {
      var dv;
      try { dv = new DataView(buf.buffer, buf.byteOffset || 0, buf.byteLength); }
      catch (e) { return null; }
      var bal = doubleForKey(buf, dv, 'newBalance');
      if (bal === null) bal = doubleForKey(buf, dv, 'balance');
      if (bal !== null) {
        var now = Math.round(bal * 100);
        if (last === null) { last = now; return null; }
        var delta = now - last;
        last = now;
        if (delta < 0) {
          if (pending) reportRound(pending, 0);
          pending = -delta;
        } else if (delta > 0 && pending) {
          reportRound(pending, delta);
          pending = null;
        }
        return null;
      }
      // A large SFS frame is zlib (the flag is 0xa0): the join answer carries
      // the opening saldo, so it has to be inflated before it can be read.
      if ((buf[0] === 0xa0 || buf[3] === 0x78) &&
          typeof DecompressionStream !== 'undefined') {
        try {
          return new Response(new Blob([buf.subarray(3)]).stream()
            .pipeThrough(new DecompressionStream('deflate')))
            .arrayBuffer()
            .then(function (ab) { handle(new Uint8Array(ab)); })
            .catch(function () {});
        } catch (e) { return null; }
      }
      // the crash posts the round's chart line with the stake still down
      if (pending && hasString(buf, 'roundChartInfo')) {
        reportRound(pending, 0);
        pending = null;
      }
      return null;
    }

    ws.addEventListener('message', function (ev) {
      var buf = bytesOf(ev.data);
      if (!buf) return;
      // serialise: an inflated frame must not overtake the ones after it
      chain = chain.then(function () { return handle(buf); })
                   .catch(function () {});
    });
  }

  if (window.WebSocket) {
    var NativeSocket = window.WebSocket;
    var PatchedSocket = function (url, protocols) {
      var socket = protocols === undefined ? new NativeSocket(url)
                                           : new NativeSocket(url, protocols);
      try {
        // each publisher's own transport carries its round protocol
        var u = String(url || socket.url);
        if (u.indexOf('gamehub') >= 0) watchSocket(socket);
        else if (u.indexOf('spribegaming') >= 0 || u.indexOf('BlueBox') >= 0)
          spribeWatch(socket);
      } catch (e) {}
      return socket;
    };
    PatchedSocket.prototype = NativeSocket.prototype;
    ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED'].forEach(function (k) {
      try { PatchedSocket[k] = NativeSocket[k]; } catch (e) {}
    });
    window.WebSocket = PatchedSocket;
  }

  window.addEventListener('load', function () { hud(); refresh(); });
  if (document.readyState === 'complete' || document.readyState === 'interactive') { hud(); }
})();
"""


def bridge_script() -> bytes:
    return _BRIDGE.encode("utf-8")


def inject_bridge(html: bytes, game_id: str, token: str, view: dict) -> bytes:
    """Insert the bridge + its config right after <head> so it loads first."""
    import json as _json
    from urllib.parse import parse_qsl, urlsplit
    cfg = {
        "token": token, "game_id": game_id, "api": "/api",
        "balance_minor": int(view.get("balance_minor") or 0),
        "bonus_minor": int(view.get("bonus_minor") or 0),
        "min_stake_minor": int(view.get("min_stake_minor") or 200),
        "can_play": bool(view.get("can_play")),
    }
    game = game_for(game_id)
    if game and (game.get("provider") or "") == "pragmatic_play":
        # The Unity client reads its operator config (user, domain, symbol,
        # lang) from a config file that can come back empty off-origin
        # (decision 0036); the bridge carries the true values so it can
        # synthesize the file instead of dying in ParseConfigFile.
        query = dict(parse_qsl(urlsplit(game.get("demo_url") or "").query))
        cfg["pp_symbol"] = query.get("gameSymbol", "")
        cfg["pp_lang"] = query.get("lang", "en")
    if game and (game.get("provider") or "") == "pg_soft":
        # the theater tap's two facts: which spin endpoint the R$0 gate
        # guards, and which game id the wallet poll names (decision 0044)
        query = dict(parse_qsl(urlsplit(game.get("demo_url") or "").query))
        cfg["bet_url"] = "/v4/Spin"
        cfg["pg_gi"] = query.get("gi", "")
    tag = (f'<script>window.__WALLET__={_script_json(cfg)};</script>'
           f'<script src="{BRIDGE_PATH}"></script>').encode("utf-8")
    lower = html.lower()
    idx = lower.find(b"<head>")
    if idx >= 0:
        at = idx + len(b"<head>")
        return html[:at] + tag + html[at:]
    return tag + html


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface a publisher redirect to the caller instead of following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_FOLLOW_OPENER = urllib.request.build_opener()
_OPENER = urllib.request.build_opener(_NoRedirect)

# What the proxy did, for `GET /api/health`. A game that does not load leaves
# almost no other trace on the server, and "was it us or was it the
# publisher" is the first question worth answering.
_COUNTS = {"upstream": 0, "failures": 0, "bytes": 0, "redirects": 0}
_COUNTS_LOCK = threading.Lock()


def note(kind: str, amount: int = 1) -> None:
    """Count one proxy event (see `_COUNTS`)."""
    with _COUNTS_LOCK:
        _COUNTS[kind] = _COUNTS.get(kind, 0) + amount


def stats() -> dict:
    """A snapshot of the proxy counters."""
    with _COUNTS_LOCK:
        return dict(_COUNTS)


def _read_body(stream) -> bytes:
    """Read a publisher answer whole, or refuse it.

    A quietly truncated body is the worst failure this proxy can hand a
    client: the game deserializes half a bundle and dies on its loader with
    nothing in the console pointing back here (decision 0036 chased exactly
    that shape of bug). The cap is a refusal the caller turns into a 502,
    never a silent cut.
    """
    data = stream.read(MAX_BODY + 1)
    if len(data) > MAX_BODY:
        raise ProxyError(f"publisher answer over {MAX_BODY} bytes")
    return data


def fetch(url: str, method: str = "GET", body: bytes | None = None,
          headers: dict | None = None, timeout: int = 20,
          follow: bool = True) -> tuple[int, dict, bytes]:
    """Forward one request to the publisher.

    With `follow=False` a redirect is not followed: the 3xx comes back with
    its Location so the caller can hand it to the browser (see
    `Handler._pass_redirect`).
    """
    checked_url(url)
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "*/*")
    for key, value in (headers or {}).items():
        if key.lower() in FORWARDED_HEADERS:
            req.add_header(key, value)
    opener = _FOLLOW_OPENER if follow else _OPENER
    try:
        with opener.open(req, timeout=timeout) as resp:
            status, up_headers, data = resp.status, dict(resp.headers), _read_body(resp)
    except urllib.error.HTTPError as exc:
        # the error *is* a response: read it, then close it — an unclosed
        # one keeps the upstream connection (and its file handle) open
        try:
            status, up_headers, data = exc.code, dict(exc.headers or {}), _read_body(exc)
        finally:
            exc.close()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        note("failures")
        raise ProxyError(f"upstream {method} failed: {type(exc).__name__}") from exc
    note("upstream")
    note("bytes", len(data))
    if status in REDIRECT_STATUSES:
        note("redirects")
    return status, up_headers, data
