# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""turnstile — verify a Cloudflare Turnstile token, with no dependency.

Turnstile is a CAPTCHA replacement: a widget on the page hands the browser a
short-lived token, and the *server* exchanges that token for an answer at
Cloudflare's `siteverify` endpoint. The check is deliberately server-side —
the browser can lie, the token cannot be trusted until siteverify confirms it.

This module is the server half, stated once so no host re-solves it:

  * the secret comes from the environment, never from code or a log;
  * the secret is never replayed to another host on a redirect;
  * a token that is missing, oversized, from the wrong action, or solved on a
    hostname that is not ours is refused — the canonical policy, not just
    `success === true`;
  * an unconfigured host gets a disabled verifier whose `enabled` is False, so
    a sandbox without credentials keeps working while a configured deploy
    gates.

The frontend half (the widget) is the host's: foundry ships a snippet in
`templates/turnstile/`, but the host owns where it goes. Nothing here knows
what a "login" or a "signup" is; a host renders the widget, reads the token,
and calls :meth:`Verifier.verify`.
"""
from __future__ import annotations

from .transport import Transport, urllib_transport
from .verification import TurnstileError, Verification
from .verifier import (DEFAULT_ENDPOINT, DEFAULT_ENV_FILE, FIELD_NAME,
                       DisabledVerifier, SiteverifyVerifier, Verifier,
                       resolve_verifier)

__all__ = [
    "DEFAULT_ENDPOINT",
    "DEFAULT_ENV_FILE",
    "DisabledVerifier",
    "FIELD_NAME",
    "SiteverifyVerifier",
    "Transport",
    "TurnstileError",
    "Verification",
    "Verifier",
    "resolve_verifier",
    "urllib_transport",
]
