# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""betterauth — the host-side half of a Better Auth social sign-in.

Better Auth is a TypeScript library: it owns the OAuth dance and the
provider credentials. A Python host cannot run it, and it must not trust a
browser's word about who signed in. The bridge between the two is a small,
signed claim:

    Better Auth callback -> Node bridge -> POST {provider, subject, email,
    name, email_verified, ts} with an HMAC-SHA256 header -> this module.

This package is that verifier, stated once. It is deliberately the *only*
thing the host needs to share: no provider secrets, no OAuth state, no
Better Auth session. The claim is short-lived (``MAX_AGE``) and the signature
is compared in constant time, so a replayed or forged bridge call is refused
before the host links an account.

Two things stay in the host, per the kit's boundary rule: what a signed-in
person is allowed to do (create a wallet, demand a CPF, link an existing
account) and what the user sees. This module only answers "did Better Auth
sign this, recently, and who does it say this is?".
"""
from __future__ import annotations

from .bridge import (
    MAX_AGE,
    BridgeError,
    SocialIdentity,
    payload_for,
    signature_for,
    verify_bridge,
)
from .config import (
    DEFAULT_ENV_FILE,
    DEFAULT_PROVIDERS,
    BetterAuthConfig,
    resolve_betterauth,
)

__all__ = [
    "DEFAULT_ENV_FILE",
    "DEFAULT_PROVIDERS",
    "MAX_AGE",
    "BetterAuthConfig",
    "BridgeError",
    "SocialIdentity",
    "payload_for",
    "resolve_betterauth",
    "signature_for",
    "verify_bridge",
]
