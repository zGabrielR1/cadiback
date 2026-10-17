# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""The HTTP the OIDC flow needs, with the same plain function the kit ships.

A transport is the same five-argument callable the mail and turnstile modules
use — `(method, url, headers, body, timeout) -> dict` — so a host can inject
its own HTTP client, and a test can inject one that answers from a table
instead of dialing. The default is `urllib`: the operator's one container has
nothing else, and the module must run there.

Two details are carried over from the turnstile module because they are not
incidental:

  * an identity provider behind a CDN (Authgear sits behind one) answers a
    request carrying a User-Agent it does not recognise with a bare,
    unexplained 403, so an honest, stable identity is always sent;
  * the token exchange carries the client secret in the POST body, so the
    default opener refuses to replay it to a *different* host on a redirect.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from .identity import OAuthError

Transport = Callable[[str, str, dict, "bytes | None", int], dict]

USER_AGENT = "foundry-oauth/0.1"


class _NoCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse to replay the client secret to another host on a redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).netloc != req.host:
            raise OAuthError("refusing cross-host redirect with the secret")
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
        # Keep the first 300 chars of the provider's own error for the log;
        # never the request, which is where the secret lives.
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise OAuthError(
            f"identity provider refused the request ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise OAuthError(f"identity provider unreachable: {exc.reason}") from exc
    except ValueError as exc:
        raise OAuthError(
            f"identity provider returned unreadable JSON: {exc}") from exc
