# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""Password hashing — the one slow hash, with a versioned stored format.

Hashing a password is plumbing every host writes and one of them writes with a
fast hash by accident. This module states the shape once:

  * PBKDF2-HMAC-SHA256, a fresh random salt per password, and a stored string
    that names the algorithm and the work factor:
    ``pbkdf2_sha256$600000$<salt hex>$<digest hex>``;
  * verification is constant-time and returns False for every malformed or
    unknown record instead of raising — a corrupt row must not become a 500 or
    an oracle;
  * the work factor can rise over time: :meth:`PasswordHasher.needs_rehash`
    tells the host when a successful login is the right moment to re-hash;
  * a password policy is a value the *host* passes in. With no policy the
    module enforces only the universal rules (text, non-empty, bounded
    length), because "6 characters with a digit" is a product decision.

The format is self-describing, so a future algorithm is a new prefix rather
than a migration that must guess what an old row meant.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from ..envfile import first, load_env

ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000
MAX_ITERATIONS = 5_000_000
DEFAULT_SALT_BYTES = 16
DEFAULT_KEY_BYTES = 32
MAX_PASSWORD_LENGTH = 1024


class PasswordError(ValueError):
    """A password or a stored hash cannot be used. Safe to show to an operator."""


@dataclass(frozen=True)
class PasswordPolicy:
    """The host's password rules, as a value.

    The module never chooses these; a host that wants "at least 8 characters
    with a letter and a digit" constructs this and passes it to
    :class:`PasswordHasher`. Messages are generic English on purpose — the host
    owns the copy it shows a person.
    """

    min_length: int = 8
    max_length: int = MAX_PASSWORD_LENGTH
    require_letter: bool = False
    require_digit: bool = False

    def __post_init__(self) -> None:
        if self.min_length < 1:
            raise PasswordError("min_length must be positive")
        if self.max_length < self.min_length:
            raise PasswordError("max_length must be >= min_length")
        if self.max_length > MAX_PASSWORD_LENGTH:
            raise PasswordError(f"max_length cannot exceed {MAX_PASSWORD_LENGTH}")

    def validate(self, password: str) -> str:
        if not isinstance(password, str):
            raise PasswordError("password must be text")
        if len(password) < self.min_length:
            raise PasswordError(
                f"password must be at least {self.min_length} characters")
        if len(password) > self.max_length:
            raise PasswordError(
                f"password must be at most {self.max_length} characters")
        if self.require_letter and not any(c.isalpha() for c in password):
            raise PasswordError("password must contain a letter")
        if self.require_digit and not any(c.isdigit() for c in password):
            raise PasswordError("password must contain a digit")
        return password


@dataclass(frozen=True)
class PasswordHash:
    """A parsed storage record. :meth:`encode` is what goes in the database."""

    iterations: int
    salt: bytes
    digest: bytes

    def __post_init__(self) -> None:
        if not 1 <= self.iterations <= MAX_ITERATIONS:
            raise PasswordError("iteration count is outside the supported range")
        if not 8 <= len(self.salt) <= 64:
            raise PasswordError("salt length is outside the supported range")
        if not 16 <= len(self.digest) <= 128:
            raise PasswordError("digest length is outside the supported range")

    def encode(self) -> str:
        return "$".join((ALGORITHM, str(self.iterations),
                         self.salt.hex(), self.digest.hex()))

    @classmethod
    def parse(cls, encoded: object) -> "PasswordHash | None":
        """A record, or None. Every bad shape is None, never an exception."""
        if not isinstance(encoded, str):
            return None
        parts = encoded.split("$")
        if len(parts) != 4 or parts[0] != ALGORITHM:
            return None
        try:
            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            digest = bytes.fromhex(parts[3])
        except (TypeError, ValueError):
            return None
        try:
            return cls(iterations=iterations, salt=salt, digest=digest)
        except PasswordError:
            return None


@dataclass(frozen=True)
class PasswordHasher:
    """Stable password plumbing with an adjustable work factor."""

    iterations: int = DEFAULT_ITERATIONS
    policy: PasswordPolicy | None = None
    salt_bytes: int = DEFAULT_SALT_BYTES
    key_bytes: int = DEFAULT_KEY_BYTES

    def __post_init__(self) -> None:
        if not 1 <= self.iterations <= MAX_ITERATIONS:
            raise PasswordError("iteration count is outside the supported range")
        if not 8 <= self.salt_bytes <= 64:
            raise PasswordError("salt_bytes must be between 8 and 64")
        if not 16 <= self.key_bytes <= 128:
            raise PasswordError("key_bytes must be between 16 and 128")

    def hash(self, password: str, *, salt: bytes | None = None) -> str:
        """Hash a new password. A supplied salt exists for deterministic tests."""
        if not isinstance(password, str):
            raise PasswordError("password must be text")
        if not password:
            raise PasswordError("password must not be empty")
        if len(password) > MAX_PASSWORD_LENGTH:
            raise PasswordError(
                f"password must be at most {MAX_PASSWORD_LENGTH} characters")
        if self.policy is not None:
            self.policy.validate(password)
        raw_salt = secrets.token_bytes(self.salt_bytes) if salt is None else salt
        if not 8 <= len(raw_salt) <= 64:
            raise PasswordError("salt must be between 8 and 64 bytes")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), raw_salt, self.iterations,
            dklen=self.key_bytes)
        return PasswordHash(self.iterations, raw_salt, digest).encode()

    def verify(self, password: str, encoded: object) -> bool:
        """True only for the matching password and a well-formed record."""
        parsed = PasswordHash.parse(encoded)
        if parsed is None or not isinstance(password, str):
            return False
        if not password or len(password) > MAX_PASSWORD_LENGTH:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), parsed.salt, parsed.iterations,
            dklen=len(parsed.digest))
        return hmac.compare_digest(digest, parsed.digest)

    def needs_rehash(self, encoded: object) -> bool:
        """True for a legacy/unknown record or a lower work factor."""
        parsed = PasswordHash.parse(encoded)
        if parsed is None:
            return True
        return (parsed.iterations < self.iterations
                or len(parsed.salt) < self.salt_bytes
                or len(parsed.digest) < self.key_bytes)


def resolve_password_hasher(env: dict[str, str] | None = None,
                            *, policy: PasswordPolicy | None = None
                            ) -> PasswordHasher:
    """Build a hasher from the environment, falling back to the safe default.

    ``PASSWORD_PBKDF2_ITERATIONS`` is the only setting: a bad value is ignored
    rather than allowed to weaken or DoS the login path.
    """
    source = dict(env) if env is not None else load_env()
    raw = first(source, "PASSWORD_PBKDF2_ITERATIONS", str(DEFAULT_ITERATIONS))
    try:
        iterations = int(raw)
    except (TypeError, ValueError):
        iterations = DEFAULT_ITERATIONS
    if not 1 <= iterations <= MAX_ITERATIONS:
        iterations = DEFAULT_ITERATIONS
    return PasswordHasher(iterations=iterations, policy=policy)
