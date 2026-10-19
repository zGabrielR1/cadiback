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
  `…/<file>?sign=<unix-ts>-<base64 sig>…` (sometimes `?verify=`, both
  spellings observed 2026-10-15: `probes/pg-handshake-2026-10-15.json`
  vs `probes/pg-spin.json`). The signature covers the path, so the proxy has to forward
  the query byte-for-byte and cannot cache a signed URL under a key that
  drops it. This is why `game_proxy`'s own cache revalidates rather than
  serving a stale signature. Unsigned asset paths 403 with
  `ANTI_HOTLINKING_GENERAL_FORMAT_ERROR` on the static host and 404 on
  the game host — there is no unsigned fallback to route to.

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
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

LAUNCHER = "https://public.pg-demo.com/demo/"
LAUNCHER_ORIGIN = "https://public.pg-demo.com"
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
# plain JSON in minor-unit-friendly decimals, so `rewrite_wallet` shows
# the player's real saldo in every `GameWallet/Get` answer — but
# `GameInfo/Get` and therefore almost certainly the spin are a **binary**
# protocol, so a tap that has to re-encode a spin is a different job from
# one that has to rewrite a number. Display sync is done; settlement is
# not, and the game stays `wallet_isolated` until a real-browser capture
# settles the spin shape.
SESSION_PATH = "/web-api/auth/session/v2/verifySession"
NAME_PATH = "/web-api/game-proxy/v2/GameName/Get"
RESOURCES_PATH = "/web-api/game-proxy/v2/Resources/GetByResourcesTypeIds"
WALLET_PATH = "/web-api/game-proxy/v2/GameWallet/Get"
HEALTH_PATH = "/healthcheck"

# The balance keys in a `GameWallet/Get` answer, in the order they matter:
# `cb` is what the client shows, `tb` the account total, `pb` the previous
# value (a delta of `cb - pb` is the round's net) and `ch` the change record.
WALLET_BALANCE_KEYS = ("cb", "tb", "ch", "pb", "tbb", "tfgb")

# Tails of ours that are the money API, not the game: they live on the
# session's api hosts. Measured 2026-10-15: the game host answers 404 on
# `/web-api/...` while the api host routes it (500 on a bad token, which
# is the server refusing the credential, not the route). `/healthcheck`
# is deliberately not here — the game host answers it 200.
MONEY_TAILS = ("/web-api/", "/game-api/")


def rewrite_wallet(body: bytes, balance_minor: int) -> bytes:
    """Show the player's real saldo in a `GameWallet/Get` answer.

    The answer is plain JSON — `{"dt": {"tb": 100000.00, "cb": 100000.00,
    "pb": 0.00, "ch": {"cb": 100000.00, ...}}}` — so `cb`/`tb`/`ch.cb`
    are replaced with the wallet's value in the same shape the publisher
    used (floats stay floats, ints stay ints). `pb` is set to the same
    value so the client derives no phantom last-round delta, and the
    tournament/free-game keys (`tbb`, `tfgb`) are left alone: their
    semantics are unknown and rewriting them would invent bonus money.

    Display only: it does not settle anything. Spins stay the publisher's
    (binary protocol) and the game stays `wallet_isolated`. Anything that
    is not this JSON — the binary `GameInfo/Get` included — passes through
    byte-for-byte.
    """
    import json as _json
    try:
        payload = _json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return body
    if not isinstance(payload, dict):
        return body
    inner = payload.get("dt")
    if not isinstance(inner, dict):
        return body
    units = int(balance_minor) / 100
    changed = False
    for key in ("cb", "tb"):
        value = inner.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        inner[key] = round(units, 2) if isinstance(value, float) else int(units)
        changed = True
    if changed:
        current = inner.get("cb")
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            inner["pb"] = current
        change = inner.get("ch")
        if isinstance(change, dict) and isinstance(change.get("cb"),
                                                   (int, float)) \
                and not isinstance(change.get("cb"), bool):
            change["cb"] = current
        note("balanced")
        return _json.dumps(payload).encode("utf-8")
    return body


class PgError(RuntimeError):
    """PG refused the mint, or the answer carried no usable session."""


class Session:
    """One minted PG session: where the game is, and which hosts it may use."""

    __slots__ = ("session_id", "gi", "token", "game_url", "game_host",
                 "static_host", "api_hosts", "expires_at", "hv", "us")

    def __init__(self, session_id: str, gi: str, token: str, game_url: str,
                 game_host: str, static_host: str, api_hosts: tuple[str, ...],
                 hv: str = "", us: str = ""):
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
        # the triple's own handshake fields, passed through verbatim on the
        # launch URL (`__hv`/`__sv`): the client signs its asset URLs from
        # them, and without them it falls back to an unsigned path the
        # publisher never serves (decision 0044 appendix)
        self.hv = hv
        self.us = us
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


def _msgpack_next(blob: bytes, pos: int):
    """One msgpack value starting at pos. Only the shapes the mint answer
    uses (ints, bools, nil, floats, fix/str8/str16 strings, fix arrays and
    maps); anything else raises and the caller treats the blob as opaque."""
    import struct as _struct
    code = blob[pos]
    if code <= 0x7f:
        return code, pos + 1
    if code >= 0xe0:
        return code - 0x100, pos + 1
    if 0xa0 <= code <= 0xbf:
        size = code - 0xa0
        return blob[pos + 1:pos + 1 + size].decode("utf-8", "replace"), pos + 1 + size
    if 0x90 <= code <= 0x9f:
        return _msgpack_list(blob, pos + 1, code - 0x90)
    if 0x80 <= code <= 0x8f:
        return _msgpack_map(blob, pos + 1, code - 0x80)
    if code == 0xc0:
        return None, pos + 1
    if code == 0xc2:
        return False, pos + 1
    if code == 0xc3:
        return True, pos + 1
    if code == 0xca:
        return _struct.unpack(">f", blob[pos + 1:pos + 5])[0], pos + 5
    if code == 0xcb:
        return _struct.unpack(">d", blob[pos + 1:pos + 9])[0], pos + 9
    if code == 0xcc:
        return blob[pos + 1], pos + 2
    if code == 0xcd:
        return int.from_bytes(blob[pos + 1:pos + 3], "big"), pos + 3
    if code == 0xd9:
        size = blob[pos + 1]
        return blob[pos + 2:pos + 2 + size].decode("utf-8", "replace"), pos + 2 + size
    if code == 0xda:
        size = int.from_bytes(blob[pos + 1:pos + 3], "big")
        return blob[pos + 3:pos + 3 + size].decode("utf-8", "replace"), pos + 3 + size
    raise ValueError(f"msgpack opcode {code:#x} at {pos}")


def _msgpack_list(blob: bytes, pos: int, size: int):
    out = []
    for _ in range(size):
        value, pos = _msgpack_next(blob, pos)
        out.append(value)
    return out, pos


def _msgpack_map(blob: bytes, pos: int, size: int):
    out = {}
    for _ in range(size):
        key, pos = _msgpack_next(blob, pos)
        value, pos = _msgpack_next(blob, pos)
        out[key] = value
    return out, pos


def mangle(domain: str, shift: int = 0) -> str:
    """The launcher's domain mangling for the game URL (`ao`/`or`).

    Reverse-engineered off the mint page itself (`minter.js` in a mint
    answer): each letter shifts forward by a random 1..25 (`.` becomes
    `=`, digits and `-` pass through), prefixed with the shift as two
    decimal digits. Verified against a real launcher redirect:
    `mangle("api.f26xzzc7c.com", 18) == "18sha=x26prru7u=uge"`.
    """
    import random as _random
    if not 1 <= shift <= 25:
        shift = _random.randint(1, 25)
    table = [chr((i + shift) % 26 + 97) for i in range(26)]

    def sub(char: str) -> str:
        if char == ".":
            return "="
        code = ord(char)
        if 97 <= code <= 122:
            return table[code - 97]
        if 65 <= code <= 90:
            return table[code - 65]
        return char

    return f"{shift // 10}{shift % 10}" + "".join(sub(c) for c in domain)


def unmangle(token: str) -> str:
    """Inverse of mangle (tests and debugging only)."""
    shift = int(token[:2])
    table = [chr((i + shift) % 26 + 97) for i in range(26)]
    back = {v: chr(97 + i) for i, v in enumerate(table)}

    def sub(char: str) -> str:
        if char == "=":
            return "."
        return back.get(char, char)

    return "".join(sub(c) for c in token[2:])


def parse_triples(html: str) -> dict[str, dict]:
    """Every candidate triple in a mint answer, keyed by host label.

    Each entry carries the game URL plus the triple's own handshake
    fields (`hv`, `us`) that the launcher forwards as `__hv`/`__sv` —
    the client signs its asset URLs from them. A blob that does not
    parse is not an error here: `parse_session` (hosts) already decided
    whether the mint is usable, this only enriches it.
    """
    match = re.search(r"[A-Za-z0-9+/]{500,}={0,2}", html)
    if not match:
        return {}
    try:
        blob = base64.b64decode(match.group(0))
        payload, consumed = _msgpack_next(blob, 0)
    except (ValueError, base64.binascii.Error, IndexError, KeyError):
        return {}
    if consumed != len(blob) or not isinstance(payload, dict):
        return {}
    triples: dict[str, dict] = {}
    entries = payload.get("f")
    if not isinstance(entries, list):
        return {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        game_url = entry.get("u") if isinstance(entry.get("u"), str) else ""
        found = _GAME_URL.search(game_url)
        resources = entry.get("rd")
        first = resources[0] if isinstance(resources, list) and resources \
            and isinstance(resources[0], dict) else {}
        hv = first.get("hv") if isinstance(first.get("hv"), str) else ""
        us = first.get("us") if isinstance(first.get("us"), str) else ""
        if found and hv and us:
            triples[found.group(1)] = {"game_url": game_url, "hv": hv,
                                       "us": us}
    return triples


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
    # the handshake fields must belong to the triple actually served
    # (stable or weighted): look them up by the chosen game host
    label = game_host.split(".")[1] if game_host.count(".") == 2 else ""
    triple = parse_triples(html).get(label, {})
    session = Session(session_id or uuid.uuid4().hex[:16], gi, ot_of(url), url,
                      game_host, static_host, api_hosts,
                      hv=str(triple.get("hv") or ""),
                      us=str(triple.get("us") or ""))
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


# The access token PG mints in `verifySession` (`dt.tk`). It is session-scoped
# and expires with the session; the server keeps it only when the handshake
# actually came through us (ao-steering), because that is when the browser
# cannot read the publisher's trial wallet cross-origin on its own.
_ACCESS: dict[str, str] = {}


def note_access(session_id: str, token: str) -> None:
    """Remember the token `verifySession` minted for one PG session."""
    if not session_id or not token:
        return
    with _LOCK:
        _ACCESS[session_id] = token
        while len(_ACCESS) > MAX_SESSIONS:
            _ACCESS.pop(next(iter(_ACCESS)))


def access_for(session_id: str) -> str:
    with _LOCK:
        return _ACCESS.get(session_id, "")


def trial_balance(session_id: str) -> float | None:
    """Poll the publisher's trial wallet for one session, untouched.

    This is the one number the theatre must never rewrite: the client's own
    `GameWallet/Get` is rewritten to the player's saldo (that is the display),
    so the tap asks the publisher directly through the token the handshake
    handed us. None means "not steered" — an unsteered launch never showed us
    the token, and the tap stays quiet rather than inventing a balance.
    """
    session = session_for(session_id)
    atk = access_for(session_id)
    if session is None or not atk or not session.api_hosts:
        return None
    from demo import game_proxy
    body = urllib.parse.urlencode({
        "isagw": "true", "btt": "2", "wk": "0_C", "atk": atk,
        "pf": "1", "gid": session.gi,
    }).encode()
    url = f"https://{session.api_hosts[0]}{WALLET_PATH}"
    try:
        status, _headers, data = game_proxy.fetch(
            url, "POST", body,
            {"Content-Type": "application/x-www-form-urlencoded"})
        if status != 200:
            return None
        payload = json.loads(data.decode("utf-8"))
        value = payload["dt"]["cb"]
        return float(value) if isinstance(value, (int, float)) else None
    except (game_proxy.ProxyError, OSError, ValueError, KeyError, TypeError):
        return None


def public_host() -> str:
    """The host PG's document is served from in production.

    Empty in the default single-origin deploy: PG then uses the request's
    own origin, which is what the local harness and the demo rely on. Set
    ``PG_PUBLIC_HOST`` (e.g. ``pg.example.com``) to serve the document from
    a host whose registrable domain also owns ``api.<domain>`` — that is
    the only shape the client's money calls can share with our origin
    without CORS. ``PG_HOST`` is accepted as an alias.
    """
    value = (os.environ.get("PG_PUBLIC_HOST")
             or os.environ.get("PG_HOST") or "").strip().lower()
    return value.rstrip("/")


def api_host() -> str:
    """The host PG's money calls must land on.

    Explicit via ``PG_AO_HOST`` / ``PG_API_HOST`` (the local harness uses
    this), otherwise derived as ``api.<registrable domain>`` of the public
    host. Empty when neither is configured.
    """
    explicit = (os.environ.get("PG_AO_HOST")
                or os.environ.get("PG_API_HOST") or "").strip().lower()
    if explicit:
        return explicit
    host = public_host()
    if not host:
        return ""
    labels = host.split(".")
    if len(labels) < 2:
        return ""
    return "api." + ".".join(labels[-2:])


def cookie_domain() -> str:
    """Registrable domain for the PG session cookies, or ``\"\"``.

    Cross-subdomain money calls (document on ``pg.example.com``, money on
    ``api.example.com``) need the cookies on ``.example.com``; a single-
    origin deploy must not set a Domain attribute at all.
    """
    host = public_host()
    if not host:
        return ""
    labels = host.split(".")
    if len(labels) < 2:
        return ""
    return "." + ".".join(labels[-2:])


def routing() -> dict:
    """Read-only view of the production routing, for /api/health."""
    return {
        "public_host": public_host() or None,
        "api_host": api_host() or None,
        "production_ready": bool(public_host() and api_host()),
    }
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
