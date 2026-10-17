# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""oauth — the OIDC Authorization Code flow (PKCE), with no dependency.

"Sign in with Google / Facebook" through a broker (Authgear) is five steps
every host writes once and one of them gets subtly wrong: discovery, the
authorize redirect, the code exchange, the userinfo read, and the CSRF state
that ties them together. This module is those five steps, stated once:

  * the flow is Authorization Code **with PKCE** — the verifier never leaves
    the server, so a stolen authorization code is not a stolen session;
  * `state` is the host's to mint and check, and the module refuses a callback
    whose state it never issued;
  * the identity is read from the **userinfo** endpoint with the access token,
    not from a signed `id_token`, because verifying an RS256 JWT means
    third-party crypto the kit's stdlib-only rule forbids — and userinfo
    carries the same `sub` and `email` from the same party;
  * the client secret travels only in the token-exchange POST body, and the
    default transport refuses to replay it to another host on a redirect;
  * an unconfigured host gets a disabled client whose `enabled` is False, so a
    sandbox keeps working while a configured deploy offers the buttons.

The module knows nothing about "players", "wallets", or "CPF". It hands the
host an :class:`Identity` (`provider:subject` plus a vouched-for email) and
lets the host decide how to link it — that, not the flow, is the host's policy.
"""
from __future__ import annotations

from .client import (DEFAULT_ENV_FILE, DisabledOAuth, OidcClient,
                     code_challenge, new_state, new_verifier, resolve_oauth)
from .config import DEFAULT_SCOPES, OAuthConfig, Provider
from .identity import Identity, OAuthError
from .transport import USER_AGENT, Transport, urllib_transport

__all__ = [
    "DEFAULT_ENV_FILE",
    "DEFAULT_SCOPES",
    "DisabledOAuth",
    "Identity",
    "OAuthConfig",
    "OAuthError",
    "OidcClient",
    "Provider",
    "Transport",
    "USER_AGENT",
    "code_challenge",
    "new_state",
    "new_verifier",
    "resolve_oauth",
    "urllib_transport",
]
