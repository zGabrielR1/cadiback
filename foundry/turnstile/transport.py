# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""The one POST to siteverify, and the guard that keeps the secret on its host.

A transport is the same plain function the mail module uses:

    (method, url, headers, body, timeout) -> dict

so a host can inject its own HTTP client and a test can inject one that
records instead of dialing. The default is `urllib`: the operator's one
container has nothing else, and the module must run there.

Two details are not incidental:

  * siteverify sits behind Cloudflare, which answers a request carrying a
    User-Agent it does not recognise — `urllib`'s default included — with a
    bare, unexplained 403. An honest, stable identity is sent so the rail
    works at all (the same finding the mail module recorded).
  * the secret travels in the POST body, so the default opener refuses a
    redirect to a *different* host rather than replaying it there.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from .verification import TurnstileError

Transport = Callable[[str, str, dict, "bytes | None", int], dict]

USER_AGENT = "foundry-turnstile/0.1"


class _NoCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse to replay the secret to another host on a redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).netloc != req.host:
            raise TurnstileError("refusing cross-host redirect with the secret")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_NoCrossHostRedirect())


def urllib_transport(method: str, url: str, headers: dict,
                     body: bytes | None = None, timeout: int = 10) -> dict:
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        # siteverify answers 200 even for a refused token; a 4xx is a broken
        # request. Keep the first 300 chars for the log, never the request.
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise TurnstileError(
            f"siteverify refused the request ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise TurnstileError(f"siteverify unreachable: {exc.reason}") from exc
    except ValueError as exc:
        raise TurnstileError(
            f"siteverify returned unreadable JSON: {exc}") from exc
