# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""Opaque bearer sessions — minting, expiry and fingerprinting, no storage.

A session is a random token plus two timestamps. The host decides where it
lives (a table, a JSON file, a signed cookie), whether it is revoked on
password change, and what "remember me" means in its UI; this module only owns
the parts that are easy to get wrong:

  * tokens come from :mod:`secrets`, never from a counter or a hash of the
    user id;
  * expiry is an absolute instant, compared to an injected ``now`` so tests
    need no clock;
  * a database should store :func:`token_fingerprint` (SHA-256 hex), not the
    token, so a read-only leak of the session table does not hand over live
    sessions; the comparison is constant-time;
  * an unconfigured or nonsensical TTL falls back to the default instead of
    accidentally issuing a session that never expires.

The optional "remember" lifetime is a second TTL, not a boolean the module
interprets: a host that offers "stay logged in" asks for it explicitly.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import time
from dataclasses import dataclass

from ..envfile import first, load_env

DEFAULT_TTL_SECONDS = 12 * 60 * 60
DEFAULT_REMEMBER_TTL_SECONDS = 30 * 24 * 60 * 60
MAX_TTL_SECONDS = 10 * 365 * 24 * 60 * 60


class SessionError(ValueError):
    """A session value cannot be used. Safe to show to an operator."""


@dataclass(frozen=True)
class SessionPolicy:
    """The two lifetimes a host can offer. The host still owns the policy."""

    ttl_seconds: int = DEFAULT_TTL_SECONDS
    remember_ttl_seconds: int = DEFAULT_REMEMBER_TTL_SECONDS

    def __post_init__(self) -> None:
        for name, value in (("ttl_seconds", self.ttl_seconds),
                            ("remember_ttl_seconds", self.remember_ttl_seconds)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise SessionError(f"{name} must be an integer")
            if not 1 <= value <= MAX_TTL_SECONDS:
                raise SessionError(f"{name} is outside the supported range")

    def lifetime(self, remember: bool = False) -> int:
        return self.remember_ttl_seconds if remember else self.ttl_seconds

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "SessionPolicy":
        """Read ``SESSION_TTL_SECONDS`` / ``SESSION_REMEMBER_TTL_SECONDS``.

        A bad value is ignored, not fatal: sessions are plumbing, and a typo
        in a deploy must not take the login path down.
        """
        source = dict(env) if env is not None else load_env()
        ttl = _read_ttl(source, "SESSION_TTL_SECONDS", DEFAULT_TTL_SECONDS)
        remember = _read_ttl(source, "SESSION_REMEMBER_TTL_SECONDS",
                             DEFAULT_REMEMBER_TTL_SECONDS)
        return cls(ttl_seconds=ttl, remember_ttl_seconds=remember)


def resolve_session_policy(env: dict[str, str] | None = None) -> SessionPolicy:
    """The module's one environment reader, explicit so tests are hermetic."""
    return SessionPolicy.from_env(env)


def _read_ttl(source: dict[str, str], name: str, default: int) -> int:
    raw = first(source, name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if 1 <= value <= MAX_TTL_SECONDS else default


@dataclass(frozen=True)
class Session:
    """An issued session. The raw token is only here; store its fingerprint."""

    token: str
    issued_at: float
    expires_at: float
    remember: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.token, str) or not self.token:
            raise SessionError("session token must not be empty")
        for name, value in (("issued_at", self.issued_at),
                            ("expires_at", self.expires_at)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise SessionError(f"{name} must be a number")
            if not math.isfinite(value):
                raise SessionError(f"{name} must be finite")
        if self.expires_at <= self.issued_at:
            raise SessionError("expires_at must be after issued_at")

    @property
    def ttl_seconds(self) -> float:
        return self.expires_at - self.issued_at

    def expired(self, now: float | None = None) -> bool:
        instant = time.time() if now is None else float(now)
        return instant >= self.expires_at

    def remaining(self, now: float | None = None) -> float:
        instant = time.time() if now is None else float(now)
        return max(0.0, self.expires_at - instant)


def issue_session(*, remember: bool = False,
                  policy: SessionPolicy | None = None,
                  now: float | None = None,
                  token_factory=None) -> Session:
    """Mint a session. ``token_factory`` exists for deterministic tests."""
    chosen = policy or SessionPolicy()
    issued = time.time() if now is None else float(now)
    token = token_factory() if token_factory is not None else secrets.token_urlsafe(32)
    return Session(token=token, issued_at=issued,
                   expires_at=issued + chosen.lifetime(remember),
                   remember=bool(remember))


def token_fingerprint(token: str) -> str:
    """The value to store in a session table: SHA-256 hex of the raw token."""
    if not isinstance(token, str) or not token:
        raise SessionError("session token must not be empty")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(left: str, right: str) -> bool:
    """Constant-time comparison for two raw tokens or two fingerprints."""
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
