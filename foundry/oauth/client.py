# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""The OIDC Authorization Code flow, stated once, with PKCE.

Every host that adds "sign in with Google / Facebook" through a broker
(Authgear here) re-writes the same five steps, and gets one of them subtly
wrong: it forgets PKCE, or it trusts an `id_token` it never verified, or it
loses the CSRF `state`. This module is those five steps, and only those:

  1. ``discovery()`` — read the provider's endpoints from its well-known
     document, so nothing is hard-coded and a test can answer from a table;
  2. ``authorize_url(state, code_challenge, provider)`` — where to send the
     browser;
  3. ``exchange_code(code, code_verifier)`` — swap the code for tokens;
  4. ``userinfo(access_token)`` — read the *verified* identity;
  5. ``identity_from_code(...)`` — 3 and 4 together, which is what a callback
     handler calls.

**The identity comes from userinfo, not from the `id_token`.** Verifying a
signed JWT means RSA and a JWKS fetch — third-party crypto the kit's
stdlib-only rule forbids — and the userinfo endpoint, reached with the access
token over TLS, carries the same `sub` and `email` the id_token would, from
the same party, with no verification we would have to implement and get
exactly right. The id_token is a optimization for hosts that already do JWT;
this module trades it for a round-trip and no crypto.

`resolve_oauth` is the only function a host needs at startup, and it always
returns something safe to hold: configured credentials give an `OidcClient`,
their absence gives a `DisabledOAuth` whose `enabled` is False so a sandbox
keeps working and its social buttons stay hidden.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.parse

from .config import DEFAULT_ENV_FILE, OAuthConfig, Provider
from .identity import Identity, OAuthError
from .transport import USER_AGENT, Transport, urllib_transport

WELL_KNOWN = "/.well-known/openid-configuration"
# After this many seconds the discovery document is re-read. It changes only
# when a provider rotates its endpoints, so a generous window avoids a fetch
# on every login.
DISCOVERY_TTL = 3600


def code_challenge(verifier: str) -> str:
    """S256 PKCE challenge: base64url(sha256(verifier)) with no padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def new_verifier() -> str:
    """A fresh PKCE code verifier, in the RFC 7636 unreserved charset."""
    return secrets.token_urlsafe(64)


def new_state() -> str:
    return secrets.token_urlsafe(24)


class OidcClient:
    """Authgear (or any OIDC provider) over the Authorization Code flow."""

    name = "authgear"

    def __init__(self, config: OAuthConfig, *, transport: Transport | None = None,
                 clock=None) -> None:
        self.config = config
        self._transport = transport or urllib_transport
        self._clock = clock or _monotonic
        self._discovery: dict | None = None
        self._discovered_at = 0.0

    # -- read-only surface a host renders against --------------------
    @property
    def enabled(self) -> bool:
        return self.config.configured

    @property
    def providers(self) -> tuple[Provider, ...]:
        return self.config.providers

    # -- 1. discovery ------------------------------------------------
    def _well_known(self) -> dict:
        now = self._clock()
        if self._discovery is None or now - self._discovered_at > DISCOVERY_TTL:
            url = self.config.endpoint + WELL_KNOWN
            payload = self._get(url)
            if not isinstance(payload, dict) or not payload.get("authorization_endpoint"):
                raise OAuthError("discovery document is missing endpoints")
            self._discovery = payload
            self._discovered_at = now
        return self._discovery

    def _endpoint(self, name: str) -> str:
        value = str(self._well_known().get(name) or "").strip()
        if not value:
            raise OAuthError(f"identity provider has no {name}")
        return value

    # -- 2. authorize -----------------------------------------------
    def authorize_url(self, *, state: str, code_challenge: str,
                      provider: str = "", redirect_uri: str = "") -> str:
        """The URL to send the browser to. `provider` is a best-effort hint:
        when the broker supports it the login page opens straight on that
        identity, and when it does not the broker's own chooser is shown."""
        if not self.enabled:
            raise OAuthError("oauth is not configured")
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": redirect_uri or self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if provider:
            params["provider"] = provider
        sep = "&" if "?" in self._endpoint("authorization_endpoint") else "?"
        return self._endpoint("authorization_endpoint") + sep + \
            urllib.parse.urlencode(params)

    # -- 3. token exchange ------------------------------------------
    def exchange_code(self, code: str, code_verifier: str,
                      redirect_uri: str = "") -> dict:
        if not self.enabled:
            raise OAuthError("oauth is not configured")
        if not isinstance(code, str) or not code.strip():
            raise OAuthError("no authorization code in the callback")
        fields = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri or self.config.redirect_uri,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code_verifier": code_verifier,
        }
        body = urllib.parse.urlencode(fields).encode("ascii")
        payload = self._post(self._endpoint("token_endpoint"), body)
        if not isinstance(payload, dict) or not payload.get("access_token"):
            detail = ""
            if isinstance(payload, dict):
                detail = str(payload.get("error") or "")
            raise OAuthError(f"token exchange returned no access token {detail}".strip())
        return payload

    # -- 4. userinfo -------------------------------------------------
    def userinfo(self, access_token: str, *, provider: str = "") -> Identity:
        if not isinstance(access_token, str) or not access_token.strip():
            raise OAuthError("cannot read userinfo without an access token")
        payload = self._get(self._endpoint("userinfo_endpoint"),
                            bearer=access_token)
        return Identity.from_userinfo(payload, provider=provider)

    # -- 5. the whole callback in one call --------------------------
    def identity_from_code(self, code: str, code_verifier: str, *,
                           provider: str = "", redirect_uri: str = "") -> Identity:
        tokens = self.exchange_code(code, code_verifier, redirect_uri)
        return self.userinfo(str(tokens["access_token"]), provider=provider)

    # -- transport helpers ------------------------------------------
    def _headers(self, *, bearer: str = "") -> dict:
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        return headers

    def _get(self, url: str, *, bearer: str = "") -> dict:
        return self._transport("GET", url, self._headers(bearer=bearer), None,
                               self.config.timeout)

    def _post(self, url: str, body: bytes) -> dict:
        headers = self._headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        return self._transport("POST", url, headers, body, self.config.timeout)


class DisabledOAuth:
    """No credentials: refuse, on purpose.

    Every method raises rather than pretending to work, so a host that forgets
    to check `enabled` fails closed. `enabled` is False, which is the signal a
    host uses to hide the social buttons entirely while the rail is
    unconfigured.
    """

    name = "none"

    @property
    def enabled(self) -> bool:
        return False

    @property
    def providers(self) -> tuple[Provider, ...]:
        return ()

    def authorize_url(self, **_: object) -> str:
        raise OAuthError("oauth is disabled (no AUTHGEAR_ENDPOINT/CLIENT_ID)")

    def exchange_code(self, *_: object, **__: object) -> dict:
        raise OAuthError("oauth is disabled (no AUTHGEAR_ENDPOINT/CLIENT_ID)")

    def userinfo(self, *_: object, **__: object) -> Identity:
        raise OAuthError("oauth is disabled (no AUTHGEAR_ENDPOINT/CLIENT_ID)")

    def identity_from_code(self, *_: object, **__: object) -> Identity:
        raise OAuthError("oauth is disabled (no AUTHGEAR_ENDPOINT/CLIENT_ID)")


def _monotonic() -> float:  # pragma: no cover - trivial clock default
    import time
    return time.monotonic()


def resolve_oauth(*, env: dict[str, str] | None = None,
                  env_file: str = DEFAULT_ENV_FILE) -> OidcClient | DisabledOAuth:
    """Build a client from the environment.

    ``env`` is exclusive when given (tests): no ambient state is consulted, so
    a test can never be steered by this machine's own credentials. Otherwise a
    real environment variable wins over a line in ``env_file``.
    """
    config = OAuthConfig.from_env(env=env, env_file=env_file)
    if not config.configured:
        return DisabledOAuth()
    return OidcClient(config)
