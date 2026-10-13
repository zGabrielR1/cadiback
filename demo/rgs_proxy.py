"""RGS interposition: the game's money calls, without touching the page.

Hacksaw's launcher takes its RGS base from the `env` query
parameter, so a game can be pointed at us without proxying a single
byte of the page: the page keeps living on the publisher's CDN and
only its money calls come here. Each call is forwarded to the real
RGS server to server — so the publisher's CORS wall (the one that
made the browser refuse the response) does not apply — and the
answer goes back with permissive CORS, because the game page is on
the publisher's origin.

The saldo in those answers is the operator's, not the RGS demo
credits: the caller swaps it before the answer is sent.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, unquote, urlparse

from . import provider_demos

# provider -> the RGS base the launcher would normally be given
# through `env=`. Only publishers that expose such a parameter can
# be interposed this way; a publisher without one needs the page
# proxy instead.
UPSTREAMS: dict[str, str] = {
    "hacksaw_gaming": "https://rgs-demo.hacksawgaming.com/api",
}

PREFIX = "/rgs"
# the game calls <env>/play/… — this is the path segment that
# follows the provider in our route
API_SEGMENT = "api"


class RgsError(RuntimeError):
    pass


def split_path(path: str) -> tuple[str, str] | None:
    """Decode a /rgs/<provider>/api/… path into (provider, tail).

    Returns None when the path is not an RGS route or names a
    provider we have no upstream for.
    """
    if not path.startswith(PREFIX + "/"):
        return None
    rest = unquote(path[len(PREFIX) + 1:])
    provider, _, tail = rest.partition("/")
    if not provider or not tail or provider not in UPSTREAMS:
        return None
    return provider, tail


def upstream_url(provider: str, tail: str) -> str:
    """Map our /rgs/<provider>/api/… tail onto the publisher RGS."""
    base = UPSTREAMS.get(provider)
    if not base:
        raise RgsError(f"no RGS for provider: {provider}")
    prefix = API_SEGMENT + "/"
    if tail.startswith(prefix):
        tail = tail[len(prefix):]
    if not tail:
        raise RgsError("empty RGS path")
    return f"{base}/{tail}"


def env_url(origin: str, provider: str) -> str:
    """The `env=` value that points a launcher at this interposition."""
    if provider not in UPSTREAMS:
        raise RgsError(f"no RGS for provider: {provider}")
    return f"{origin}{PREFIX}/{provider}/{API_SEGMENT}"


def _amount(value) -> int | None:
    """Read a money field as centavos.

    The RGS states money as whole cents in plain integers
    ("500000" is R$5000.00) and only uses a decimal when a
    fraction is present; both are read back as centavos.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, str):
        text = value.strip().replace(" ", "")
        if not text:
            return None
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        if "." in text:
            try:
                return int(round(float(text) * 100))
            except ValueError:
                return None
        try:
            return int(text)
        except ValueError:
            return None
    return None


def _fmt_like(original, minor: int):
    """Our saldo in the very shape the RGS used for that field."""
    if isinstance(original, str):
        return str(int(minor))
    if isinstance(original, float):
        return float(minor)
    return int(minor)


def demo_token(provider: str) -> str:
    """The publisher's own session token, read off a launcher URL.

    Our wallet token replaces it in the game's URL; the RGS only
    knows the publisher's, so it is swapped back in before a call
    is forwarded.
    """
    for demo in provider_demos.load().get("demos", []):
        if demo.get("provider") != provider:
            continue
        query = parse_qs(urlparse(demo.get("demo_url") or "").query)
        token = (query.get("token") or [""])[0]
        if token:
            return token
    return "demo"


def swap_token(body: bytes | None, token: str) -> bytes | None:
    """Replace the session token the game sent with the publisher's."""
    if not body or not token:
        return body
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return body
    if not isinstance(payload, dict) or "token" not in payload:
        return body
    payload["token"] = token
    return json.dumps(payload).encode("utf-8")


def bet_total(body: bytes | None) -> int:
    """The stake a call stakes, in centavos.

    The game sends it in the `bets` array; a call that continues a
    round carries none, and returns 0.
    """
    try:
        payload = json.loads((body or b"").decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    bets = payload.get("bets")
    total = 0
    if isinstance(bets, list):
        for bet in bets:
            if not isinstance(bet, dict):
                continue
            for key in ("betAmount", "stake", "amount"):
                amount = _amount(bet.get(key))
                if amount is not None:
                    total += amount
                    break
    return total


def round_state(body: bytes | None) -> dict:
    """What an answer says about its round.

    Returns the round id, whether it is finished, and the win it
    has accumulated so far: the RGS states the win per event as it
    reveals, and only the finish carries the settled saldo.
    """
    try:
        payload = json.loads((body or b"").decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    round_ = payload.get("round")
    if not isinstance(round_, dict):
        return {}
    state = {"id": str(round_.get("roundId") or ""),
             "done": round_.get("status") == "completed",
             "win": 0}
    events = round_.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            win = _amount(event.get("awa"))
            content = event.get("c")
            if win is None and isinstance(content, dict):
                win = _amount(content.get("awa"))
            if win:
                state["win"] = max(state["win"], win)
    return state


def session_uuid(body: bytes | None) -> str:
    """The RGS session id, from a call or an answer.

    Only the first call carries our token; every later one is
    named by the session the RGS handed back, so a session has to
    be followed by that id.
    """
    try:
        payload = json.loads((body or b"").decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return ""
    if not isinstance(payload, dict):
        return ""
    value = payload.get("sessionUuid")
    return value if isinstance(value, str) else ""


def session_token(body: bytes) -> str:
    """The operator token the game was launched with, from a call body."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return ""
    if not isinstance(payload, dict):
        return ""
    for key in ("token", "sessionToken", "playerToken"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def extract_balance(body: bytes) -> int | None:
    """The saldo an RGS answer reports, in centavos, or None."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return _balance_in(payload)


def _balance_in(node) -> int | None:
    if isinstance(node, dict):
        for key in ("balance", "realBalance", "walletBalance", "cash"):
            if key in node:
                amount = _amount(node[key])
                if amount is not None:
                    return amount
        for value in node.values():
            found = _balance_in(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _balance_in(value)
            if found is not None:
                return found
    return None


def replace_balance(body: bytes, balance_minor: int) -> bytes:
    """Swap every money field in an RGS answer for our saldo.

    The game shows whatever the RGS says, so the saldo the player
    sees has to be ours — in every field shape the client might
    read, not just one.
    """
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return body
    if not isinstance(payload, (dict, list)):
        return body
    found = _swap_in(payload, balance_minor)
    if not found:
        return body
    return json.dumps(payload).encode("utf-8")


def _swap_in(node, balance_minor: int) -> bool:
    changed = False
    if isinstance(node, dict):
        for key in list(node.keys()):
            if key in ("balance", "realBalance", "walletBalance", "cash"):
                if _amount(node[key]) is not None:
                    node[key] = _fmt_like(node[key], balance_minor)
                    changed = True
            elif isinstance(node[key], (dict, list)):
                changed = _swap_in(node[key], balance_minor) or changed
    elif isinstance(node, list):
        for value in node:
            changed = _swap_in(value, balance_minor) or changed
    return changed


def refusal(message: str) -> bytes:
    """An answer the game reads as a refused round.

    It wears the RGS's own error envelope — a non-zero status and a
    message — so the client shows it instead of spinning, rather
    than playing a round the wallet cannot pay for.
    """
    return json.dumps({
        "statusCode": 1,
        "statusMessage": message,
        "round": None,
        "accountBalance": None,
    }).encode("utf-8")


def cors_headers(origin: str, requested_headers: str = "") -> dict:
    """Permissive CORS for the game page, which lives on the publisher.

    The request is a public page reaching a local service, so it
    also needs the private-network blessing Chrome asks for before
    it lets the call through at all.
    """
    allow = origin or "*"
    return {
        "Access-Control-Allow-Origin": allow,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": (requested_headers
                                         or "content-type, accept, x-requested-with"),
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Private-Network": "true",
        "Access-Control-Max-Age": "600",
        "Vary": "Origin, Access-Control-Request-Headers",
    }
