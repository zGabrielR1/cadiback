# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""The one HTTP call, and the guard that keeps the key on its own host.

A transport is a plain function:

    (method, url, headers, body, timeout) -> dict

Injecting it is what lets every host share this code without sharing an HTTP
library: the default below is `urllib` (stdlib, works in the operator's one
container), and a host that already depends on `httpx` can pass a transport
that uses it — the mailer above never knows the difference, and tests pass a
transport that records instead of dials.

The default transport refuses to follow a redirect to a *different* host.
`urllib` copies the original headers — including `Authorization: Bearer
re_...` — onto a 3xx, so an open redirect anywhere on the provider's side would
be enough to walk the account key off to an attacker's server. One check
closes that, the same way the operator's Asaas client closes it.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from .message import MailError

Transport = Callable[[str, str, dict, "bytes | None", int], dict]


class _NoCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse to replay credentials to another host on a redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).netloc != req.host:
            raise MailError("refusing cross-host redirect with credentials")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_NoCrossHostRedirect())


def urllib_transport(method: str, url: str, headers: dict,
                     body: bytes | None = None, timeout: int = 15) -> dict:
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        # The provider's body explains *why* (a 422 names the bad field). Keep
        # the first 300 chars for the log; never echo the request back.
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise MailError(f"mail provider refused ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise MailError(f"mail provider unreachable: {exc.reason}") from exc
    except ValueError as exc:
        raise MailError(f"mail provider returned unreadable JSON: {exc}") from exc
