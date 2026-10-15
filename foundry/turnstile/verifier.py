# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""Verifiers: canonical siteverify over HTTPS, and a disabled one that refuses.

`resolve_verifier` is the only function a host needs at startup. It reads the
environment and returns a verifier that is *always safe to hold*:

    TURNSTILE_SECRET_KEY set (+ at least one hostname)  -> siteverify
    TURNSTILE_SECRET_KEY unset                          -> disabled

A disabled verifier is the "unconfigured is a normal state" case, exactly like
the console mailer: it never dials, and :attr:`enabled` is False so the host
can decide whether the surface is gated at all. The module does not decide
that policy for the host — a sandbox with no secret must keep working, and a
production deploy with one must gate.

`enabled` requires a non-empty hostname allowlist as well as a secret. A
verifier that has a secret but no hostname could never accept a token (the
policy refuses an empty allowlist), so reporting it as enabled would be a lie
that turns every login into a 403. `verify()` still refuses an empty allowlist
outright, so a caller that ignores `enabled` cannot accidentally accept one.
"""
from __future__ import annotations

import urllib.parse
from typing import Protocol, runtime_checkable

from ..envfile import first, load_env
from .transport import USER_AGENT, Transport, urllib_transport
from .verification import TurnstileError, Verification

DEFAULT_ENDPOINT = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
DEFAULT_ENV_FILE = ".env.turnstile"

# The form field Cloudflare's widget writes, and the one siteverify reads.
FIELD_NAME = "cf-turnstile-response"

# Cloudflare caps a token at 2048 characters; anything longer is not a token.
MAX_TOKEN_LENGTH = 2048


@runtime_checkable
class Verifier(Protocol):
    """What a host codes against. Nothing here names a page or a route."""

    name: str

    @property
    def enabled(self) -> bool:
        """True when :meth:`verify` will really reach siteverify."""

    def verify(self, token: str, *, action: str = "", hostnames=(),
               remote_ip: str = "") -> Verification:
        ...


class SiteverifyVerifier:
    """Cloudflare siteverify over HTTPS. The secret never leaves this object."""

    name = "turnstile"

    def __init__(self, secret_key: str, *, endpoint: str = DEFAULT_ENDPOINT,
                 hostnames=(), timeout: int = 10,
                 transport: Transport | None = None) -> None:
        self._secret = secret_key
        self.endpoint = endpoint or DEFAULT_ENDPOINT
        self.hostnames = tuple(hostnames)
        self.timeout = timeout
        self._transport = transport or urllib_transport

    @property
    def enabled(self) -> bool:
        # An `http://` endpoint would put the secret on the wire in clear, and
        # an empty allowlist could never accept a token: both are treated as
        # unconfigured rather than used.
        return bool(self._secret and self.endpoint.startswith("https://")
                    and self.hostnames)

    def verify(self, token: str, *, action: str = "", hostnames=None,
               remote_ip: str = "") -> Verification:
        allowed = tuple(hostnames) if hostnames is not None else self.hostnames
        if not (self._secret and self.endpoint.startswith("https://") and allowed):
            raise TurnstileError(
                "turnstile is not configured (TURNSTILE_SECRET_KEY, an https "
                "endpoint, and at least one hostname are all required)")
        # Refuse locally what siteverify would reject anyway: a missing or
        # oversized token is not worth a round-trip.
        if not isinstance(token, str) or not token.strip():
            raise TurnstileError("no turnstile token in the request")
        if len(token) > MAX_TOKEN_LENGTH:
            raise TurnstileError("turnstile token is too long")
        fields = {"secret": self._secret, "response": token}
        if remote_ip:
            fields["remoteip"] = remote_ip
        body = urllib.parse.urlencode(fields).encode("ascii")
        headers = {"Content-Type": "application/x-www-form-urlencoded",
                   "Accept": "application/json",
                   "User-Agent": USER_AGENT}
        out = self._transport("POST", self.endpoint, headers, body, self.timeout)
        return Verification.from_response(out).validate(action=action,
                                                        hostnames=allowed)


class DisabledVerifier:
    """No credentials: refuse, on purpose.

    `verify` raises rather than returning success, so a host that forgets to
    check `enabled` fails closed. `enabled` is False, which is the signal a
    host uses to skip the gate entirely while the rail is unconfigured.
    """

    name = "none"

    @property
    def enabled(self) -> bool:
        return False

    def verify(self, token: str, *, action: str = "", hostnames=(),
               remote_ip: str = "") -> Verification:
        raise TurnstileError("turnstile is disabled (no TURNSTILE_SECRET_KEY)")


def _split(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def resolve_verifier(*, env: dict[str, str] | None = None,
                     env_file: str = DEFAULT_ENV_FILE) -> Verifier:
    """Build a verifier from the environment.

    ``env`` is exclusive when given (tests): no ambient state is consulted, so
    a test can never be steered by this machine's own credentials. Otherwise a
    real environment variable wins over a line in ``env_file``.

    ``TURNSTILE_HOSTNAMES`` is the deployment's own frontend host(s).
    ``TURNSTILE_DEV_HOSTNAMES`` is an optional second list for local
    development (``localhost``, ``127.0.0.1``); it is kept separate so a
    production deploy simply does not set it, and a production allowlist never
    silently contains loopback.
    """
    source = dict(env) if env is not None else load_env(
        env_file, secret_name="TURNSTILE_SECRET_KEY")
    secret = first(source, "TURNSTILE_SECRET_KEY") or first(source, "TURNSTILE_SECRET")
    if not secret:
        return DisabledVerifier()
    hostnames = _split(first(source, "TURNSTILE_HOSTNAMES")) + \
        _split(first(source, "TURNSTILE_DEV_HOSTNAMES"))
    endpoint = first(source, "TURNSTILE_ENDPOINT", DEFAULT_ENDPOINT).rstrip("/") \
        or DEFAULT_ENDPOINT
    try:
        timeout = int(first(source, "TURNSTILE_TIMEOUT", "10"))
    except ValueError:
        timeout = 10
    return SiteverifyVerifier(secret, endpoint=endpoint, hostnames=hostnames,
                              timeout=timeout)
