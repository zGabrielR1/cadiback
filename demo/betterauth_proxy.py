"""Same-origin proxy for the Better Auth Node server.

Better Auth must see the browser's own origin: it builds each provider's
callback URL from the request host, and its session cookies are set for the
host the browser is on. So the Python server — the one public listener — hands
``/api/betterauth/*`` to a loopback Node process and streams the answer back
verbatim. Two details are load-bearing:

* **every ``Set-Cookie`` is forwarded.** Better Auth sets the session, the
  signed cookie cache and the OAuth state as separate cookies; collapsing
  them (a dict does) silently breaks the flow.
* **the public host travels as ``X-Forwarded-Host`` / ``-Proto``.** Behind
  Render/Vercel the public host is not the loopback Host, and Better Auth's
  ``trustedProxyHeaders`` mode reads exactly those two headers.

Unconfigured is a normal state: the Node process may not be running (local
work without credentials), and the caller then gets a clean 502 that the
storefront treats as "no social login".
"""
from __future__ import annotations

import http.client
import json
import os
from urllib.parse import urlsplit

PREFIX = "/api/betterauth/"
DEFAULT_INTERNAL_URL = "http://127.0.0.1:3100"
MAX_BODY = 1024 * 1024
TIMEOUT = 20

# What the auth server may need from the browser request. `content-length` is
# rebuilt from the body we actually send, and hop-by-hop headers are dropped.
FORWARDED = frozenset({
    "cookie", "origin", "referer", "content-type", "accept",
    "accept-language", "user-agent", "x-requested-with", "x-forwarded-for",
    "authorization",
})


def internal_url() -> str:
    """The loopback Better Auth server, from the live Demo config."""
    from .server import DEMO
    return (getattr(getattr(DEMO, "betterauth", None), "internal_url", "")
            or os.environ.get("BETTER_AUTH_INTERNAL_URL", "")
            or DEFAULT_INTERNAL_URL)


def _fail(handler, status: int, message: str) -> None:
    body = json.dumps({"error": message}).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def forward(handler, parsed, body: bytes | None) -> None:
    """Forward one `/api/betterauth/*` request to the Node server."""
    target = urlsplit(internal_url())
    host = target.hostname or "127.0.0.1"
    port = target.port or (443 if target.scheme == "https" else 80)
    path = parsed.path
    if parsed.query:
        path += "?" + parsed.query
    headers = {key: value for key, value in handler.headers.items()
               if key.lower() in FORWARDED}
    headers["X-Forwarded-Host"] = (handler.headers.get("X-Forwarded-Host")
                                   or handler.headers.get("Host") or "")
    headers["X-Forwarded-Proto"] = (handler.headers.get("X-Forwarded-Proto")
                                    or ("https" if handler._our_origin()
                                        .startswith("https") else "http"))
    if body is not None:
        headers["Content-Length"] = str(len(body))
    connection_cls = (http.client.HTTPSConnection
                      if target.scheme == "https" else http.client.HTTPConnection)
    connection = connection_cls(host, port, timeout=TIMEOUT)
    try:
        connection.request(handler.command, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read(MAX_BODY + 1)
        if len(data) > MAX_BODY:
            _fail(handler, 502, "resposta de autenticação grande demais")
            return
        handler.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() in ("connection", "transfer-encoding",
                               "content-length"):
                continue
            # one header line per value: Set-Cookie is the whole point
            handler.send_header(key, value)
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        if handler.command != "HEAD":
            handler.wfile.write(data)
    except (OSError, http.client.HTTPException):
        _fail(handler, 502, "servidor de autenticação indisponível")
    finally:
        connection.close()
