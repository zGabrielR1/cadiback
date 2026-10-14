"""PG Soft: a minted trial session, and the hosts that session binds.

PG Soft is the one publisher whose client will not boot from a page we did
not mint. `https://public.pg-demo.com/demo/?gi=<id>` is a launcher SPA that
POSTs the game's own parameters to

    https://public-api.pg-demo.com/web-api/operator-proxy/v2/Game/GetTrialLaunchURLHTML

and gets back an HTML document carrying a base64/msgpack config. That config
names three kinds of host and one operator token:

    https://m.<session>.com/<gi>/index.html?ot=<token>&l=pt&btt=2
    static.<session>.com            every asset, each URL signed
    api.<session>.com               the money

Decision 0035 recorded this as "a per-session dynamic host allowlist … a
Hacksaw-sized job". The live capture changed two things about it:

* **The session hosts are not all dynamic.** Every mint returns three
  candidate triples and the launcher picks one at random; one of them is
  always the stable `m.pg-demo.com` / `static.pg-demo.com`, with the money
  on `api.f26xzzc7c.com` + `api.8jkxzybcq.com`. Preferring that triple means
  the allowlist does not churn — the random hosts stay a fallback, not the
  common case.
* **Every asset URL is signed.** Assets are requested as
  `…/<file>?verify=<unix-ts>-<base64 hmac>`. The signature covers the path,
  so the proxy has to forward the query byte-for-byte and cannot cache a
  signed URL under a key that drops it. This is why `game_proxy`'s own cache
  revalidates rather than serving a stale signature.

What this module deliberately does **not** do is settle money. The client is
a 1 MB string-array-obfuscated bundle behind an environment check: in a
synthetic browser its `#GameCanvas` never gets a size (measured: `0x0@0,0`
with a 1280x800 viewport), the engine never lays out, and it therefore never
opens its lobby or issues a single `game-api` call — only `/healthcheck`
against the money host. So the spin and balance request shapes are not
known, and a money tap written against a guessed shape would be worse than
none: it would look right and settle nothing. The money path stays the
publisher's until a real browser session can be observed. See decision 0040.
"""

from __future__ import annotations

import base64
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

LAUNCHER = "https://public.pg-demo.com/demo/"
MINT_API = ("https://public-api.pg-demo.com/"
            "web-api/operator-proxy/v2/Game/GetTrialLaunchURLHTML")

# The stable triple every mint includes. Preferred so the set of hosts we
# allow changes when the publisher changes it, not every time a player opens
# a game.
STABLE_GAME_HOST = "m.pg-demo.com"
STABLE_STATIC_HOST = "static.pg-demo.com"
# the single label the URL patterns capture, i.e. what sits between the
# `m.`/`static.` prefix and `.com` — compared as a label, not as a host
STABLE_LABEL = "pg-demo"

# A session lives as long as the player is in the game. The TTL is generous
# because a host is only *added* by this module and dropped when idle; a
# stale binding is a small, self-healing exposure, and a short one would
# unbind the hosts under a player who is still playing.
SESSION_TTL = 60 * 60
MAX_SESSIONS = 200

# A minted host is a single label plus `.com` — `rhzzzvqpd`, `f26xzzc7c`.
# Anything longer or shaped differently is not something we mint, and the
# binding is an SSRF decision, so it is checked rather than trusted.
_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$")

_GAME_URL = re.compile(
    r"https://m\.([a-z0-9-]+)\.com/(\d+)/index\.html\?ot=([A-Za-z0-9]+)")
_STATIC_HOST = re.compile(r"static\.([a-z0-9-]+)\.com")
_API_HOST = re.compile(r"api\.([a-z0-9-]+)\.com")

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
MINT_TIMEOUT = 20

# --- the money API, as measured -------------------------------------------
#
# Captured 2026-10-14 with `scripts/capture_session.mjs` (devtools.protocol),
# after the one thing that was making every capture fail turned out to be the
# browser's own User-Agent: headless advertises `HeadlessChrome`, PG's engine
# refuses to lay out under it (`#GameCanvas` measured 0x0), so it never opened
# its lobby and never made a money call. With an ordinary UA the same code
# reaches the whole sequence.
#
#   POST <api>/web-api/auth/session/v2/verifySession
#        btt=2&vc=2&pf=1&l=pt&gi=<gi>&tk=null&otk=<ot>
#        -> {"dt": {"tk": "<access token>", "geu": "game-api/<slug>/",
#                    "bau": "web-api/game-proxy/", "occ": {"tcm": "You are
#                    playing Demo."}, ...}}
#   POST <api>/web-api/game-proxy/v2/GameName/Get
#        lang=pt&atk=<tk>&btt=2&pf=1&gid=<gi>
#        -> {"dt": {"31": "…"}}   — "31" is a LOCALIZATION KEY, not the name;
#                                   it answers "Baccarat Deluxe" for every
#                                   title probed. The slug from `geu` is the
#                                   only per-game identifier here.
#   POST <api>/web-api/game-proxy/v2/Resources/GetByResourcesTypeIds
#   POST <api>/game-api/<slug>/v4/GameInfo/Get      (BINARY — protobuf-ish)
#   POST <api>/web-api/game-proxy/v2/GameWallet/Get
#        isagw=true&btt=2&wk=0_C&atk=<tk>&pf=1&gid=<gi>
#        -> {"dt": {"tb": 100000.00, "cb": 100000.00, "pb": 0.00,
#                    "ch": {"cb": 100000.00, "k": "0_C"}, ...}}
#
# The wallet is the good news and the spin is the hard part: balances are
# plain JSON in minor-unit-friendly decimals, so `rewrite_balance` and the
# Hacksaw-shaped money tap apply as-is — but `GameInfo/Get` and therefore
# almost certainly the spin are a **binary** protocol, so a tap that has to
# re-encode a spin is a different job from one that has to rewrite a number.
SESSION_PATH = "/web-api/auth/session/v2/verifySession"
NAME_PATH = "/web-api/game-proxy/v2/GameName/Get"
RESOURCES_PATH = "/web-api/game-proxy/v2/Resources/GetByResourcesTypeIds"
WALLET_PATH = "/web-api/game-proxy/v2/GameWallet/Get"
HEALTH_PATH = "/healthcheck"

# The balance keys in a `GameWallet/Get` answer, in the order they matter:
# `cb` is what the client shows, `tb` the account total, `pb` the previous
# value (a delta of `cb - pb` is the round's net) and `ch` the change record.
WALLET_BALANCE_KEYS = ("cb", "tb", "ch", "pb", "tbb", "tfgb")


class PgError(RuntimeError):
    """PG refused the mint, or the answer carried no usable session."""


class Session:
    """One minted PG session: where the game is, and which hosts it may use."""

    __slots__ = ("session_id", "gi", "token", "game_url", "game_host",
                 "static_host", "api_hosts", "expires_at")

    def __init__(self, session_id: str, gi: str, token: str, game_url: str,
                 game_host: str, static_host: str, api_hosts: tuple[str, ...]):
        # Binding a host hands the proxy permission to fetch it server-side,
        # so the shape is checked here, at the point the host comes out of a
        # publisher's answer, rather than at the far end of a request.
        # The shape is `<prefix>.<label>.com` — `m.rhzzzvqpd.com`,
        # `api.f26xzzc7c.com` — and nothing else, which also refuses a
        # look-alike like `m.example.com.attacker.net` that a loose suffix
        # check would wave through.
        for host in (game_host, static_host, *api_hosts):
            parts = host.split(".")
            if (len(parts) != 3 or parts[2] != "com"
                    or not _HOST.match(parts[0])
                    or not _HOST.match(parts[1])):
                raise PgError(f"refusing a minted host that is not "
                              f"<prefix>.<label>.com: {host!r}")
        self.session_id = session_id
        self.gi = gi
        self.token = token
        self.game_url = game_url
        self.game_host = game_host
        self.static_host = static_host
        self.api_hosts = api_hosts
        self.expires_at = time.time() + SESSION_TTL

    @property
    def hosts(self) -> tuple[str, ...]:
        """Every host this session needs. Bound for as long as it lives."""
        return (self.game_host, self.static_host) + self.api_hosts

    def as_dict(self) -> dict:
        return {"session_id": self.session_id, "gi": self.gi,
                "game_host": self.game_host, "static_host": self.static_host,
                "api_hosts": list(self.api_hosts),
                "expires_in": max(0, int(self.expires_at - time.time()))}


_SESSIONS: dict[str, Session] = {}
_LOCK = threading.Lock()
_COUNTS = {"minted": 0, "failed": 0}


def note(kind: str, amount: int = 1) -> None:
    with _LOCK:
        _COUNTS[kind] = _COUNTS.get(kind, 0) + amount


def stats() -> dict:
    with _LOCK:
        return {**_COUNTS, "sessions": len(_SESSIONS)}


def _decode_strings(html: str) -> list[str]:
    """The printable strings inside the launcher's config blob.

    The blob is msgpack wrapped in base64 and its own decoder is shipped in
    the same document, but every field we need is a URL or a hostname, and
    those survive as printable runs. Pulling the runs out is a third of the
    code and does not break when the publisher re-instruments its packing.
    """
    match = re.search(r"[A-Za-z0-9+/]{500,}={0,2}", html)
    if not match:
        return []
    try:
        raw = base64.b64decode(match.group(0))
    except (ValueError, base64.binascii.Error):
        return []
    return [m.group(0).decode("ascii", "replace")
            for m in re.finditer(rb"[ -~]{6,}", raw)]


def parse_session(html: str, gi: str) -> tuple[str, str, str, tuple[str, ...]]:
    """(game_url, game_host, static_host, api_hosts) out of a mint answer.

    Picks the stable triple when the publisher offered one, because a stable
    host is an allowlist entry that does not churn per player.
    """
    strings = _decode_strings(html)
    games = [m.groups() for m in _GAME_URL.finditer(html)] or \
        [m.groups() for s in strings for m in _GAME_URL.finditer(s)]
    if not games:
        raise PgError("no game URL in the minted launcher")
    # finditer, not search: several hosts can land in one printable run when
    # the blob happens to pack them adjacently, and taking only the first
    # would silently bind one money host where the publisher named two
    statics = [m.group(1) for s in strings for m in _STATIC_HOST.finditer(s)]
    apis = [m.group(1) for s in strings for m in _API_HOST.finditer(s)]

    stable = [g for g in games if g[0] == STABLE_LABEL]
    host, game_gi, ot = (stable or games)[0]
    if game_gi != gi:
        raise PgError(f"mint answered for gi={game_gi}, asked for gi={gi}")
    game_host = f"m.{host}.com"
    static_host = next((f"static.{s}.com" for s in statics if s == host),
                       STABLE_STATIC_HOST)
    api_hosts = tuple(dict.fromkeys(f"api.{a}.com" for a in apis))
    url = f"https://{game_host}/{gi}/index.html?ot={ot}&l=pt&btt=2"
    return url, game_host, static_host, api_hosts


def mint(gi: str, lang: str = "pt", session_id: str = "") -> Session:
    """Ask the publisher for a trial session and bind the hosts it names.

    The request is the launcher's own: the game's parameters, form-encoded,
    with the launcher's origin. A mint is cheap and idempotent from the
    player's point of view, so one is made per launch rather than cached.
    """
    body = urllib.parse.urlencode({"gi": gi, "lang": lang}).encode()
    request = urllib.request.Request(
        MINT_API, data=body, method="POST",
        headers={"User-Agent": USER_AGENT, "Origin": "https://public.pg-demo.com",
                 "Referer": f"{LAUNCHER}?gi={gi}&lang={lang}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=MINT_TIMEOUT) as response:
            html = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        note("failed")
        raise PgError(f"PG refused the mint: HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        note("failed")
        raise PgError(f"cannot reach PG: {exc}") from exc

    try:
        url, game_host, static_host, api_hosts = parse_session(html, gi)
    except PgError:
        note("failed")
        raise
    if not api_hosts:
        note("failed")
        raise PgError("minted launcher named no money host")

    import uuid
    session = Session(session_id or uuid.uuid4().hex[:16], gi, ot_of(url), url,
                      game_host, static_host, api_hosts)
    bind(session)
    note("minted")
    return session


def ot_of(game_url: str) -> str:
    """The operator token PG minted, read back off the URL it handed us."""
    match = re.search(r"[?&]ot=([A-Za-z0-9]+)", game_url)
    return match.group(1) if match else ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A mint that answers with a redirect is a mint that failed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def bind(session: Session) -> None:
    """Make this session's hosts proxyable, and forget the idle ones."""
    with _LOCK:
        now = time.time()
        for sid, old in list(_SESSIONS.items()):
            if old.expires_at <= now:
                del _SESSIONS[sid]
        # bounded: a flood of launches must not grow this without limit
        while len(_SESSIONS) >= MAX_SESSIONS:
            del _SESSIONS[next(iter(_SESSIONS))]
        _SESSIONS[session.session_id] = session


def session_for(session_id: str) -> Session | None:
    if not session_id:
        return None
    with _LOCK:
        session = _SESSIONS.get(session_id)
        if session is None or session.expires_at <= time.time():
            _SESSIONS.pop(session_id, None)
            return None
        return session


def allowed_host(host: str) -> bool:
    """Is `host` one this process has actually minted a session for?"""
    with _LOCK:
        now = time.time()
        for session in _SESSIONS.values():
            if session.expires_at > now and host in session.hosts:
                return True
    return False


def forget(session_id: str) -> None:
    with _LOCK:
        _SESSIONS.pop(session_id, None)
