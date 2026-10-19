# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""Authentication plumbing: password hashes, opaque sessions, documents.

What is here is the part every host writes the same way and one of them gets
subtly wrong: a slow password hash with a fresh salt, an opaque session token
with an absolute expiry, and CPF/CNPJ check digits. What is *not* here is the
host's policy — which fields are required, how long "remember me" is, what a
login error says, where a session is stored. Those stay with the host.

    from foundry.auth import PasswordHasher, PasswordPolicy, issue_session

    hasher = PasswordHasher(policy=PasswordPolicy(min_length=8,
                                                  require_digit=True))
    stored = hasher.hash("correct horse battery staple")
    assert hasher.verify("correct horse battery staple", stored)

    session = issue_session(remember=True)
    store[token_fingerprint(session.token)] = session.expires_at
"""
from __future__ import annotations

from .documents import (DocumentError, digits_only, is_valid_cnpj,
                        is_valid_cpf, mask_cnpj, mask_cpf, validate_cnpj,
                        validate_cpf)
from .password import (ALGORITHM as PASSWORD_ALGORITHM, DEFAULT_ITERATIONS,
                       MAX_PASSWORD_LENGTH, PasswordError, PasswordHash,
                       PasswordHasher, PasswordPolicy, resolve_password_hasher)
from .session import (DEFAULT_REMEMBER_TTL_SECONDS, DEFAULT_TTL_SECONDS,
                      Session, SessionError, SessionPolicy, issue_session,
                      resolve_session_policy, token_fingerprint, tokens_equal)

__all__ = [
    "DocumentError", "digits_only", "is_valid_cnpj", "is_valid_cpf",
    "mask_cnpj", "mask_cpf", "validate_cnpj", "validate_cpf",
    "PASSWORD_ALGORITHM", "DEFAULT_ITERATIONS", "MAX_PASSWORD_LENGTH",
    "PasswordError", "PasswordHash", "PasswordHasher", "PasswordPolicy",
    "resolve_password_hasher",
    "DEFAULT_TTL_SECONDS", "DEFAULT_REMEMBER_TTL_SECONDS", "Session",
    "SessionError", "SessionPolicy", "issue_session",
    "resolve_session_policy", "token_fingerprint", "tokens_equal",
]
