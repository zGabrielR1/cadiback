# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""The values an OIDC sign-in moves around: an identity, and its refusals.

An OIDC userinfo answer is a bare JSON object, and the two fields that matter
are read *together*: `sub` is the stable, provider-scoped identifier (the only
thing that is guaranteed not to change when someone renames an account), and
`email` is the address the provider vouches for. A host that keys accounts on
`email` alone drifts when a provider lets a login change its address; a host
that keys on `sub` alone cannot link a returning social user to an account
they already made with a password. So both are captured here, in one frozen
value, and the caller decides the link — exactly the division foundry draws
between plumbing and policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class OAuthError(ValueError):
    """A refusal, a misconfiguration, or an unreachable identity provider.

    Phrased for a log line or a client message: it never contains the client
    secret, and it never echoes a raw token or provider body — only a reason.
    """


@dataclass(frozen=True)
class Identity:
    """One verified sign-in, reduced to what account-linking needs."""

    subject: str
    email: str = ""
    email_verified: bool = False
    name: str = ""
    provider: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_userinfo(cls, payload, *, provider: str = "") -> "Identity":
        """Build from a userinfo JSON object.

        A non-object answer is refused rather than coerced: an HTML error page
        parsed into `{}` would otherwise look like an `Identity` with no
        subject and hide the fact that the request never reached the provider.
        A missing `sub` is refused too — an identity with no stable key cannot
        be linked to an account without falling back to the email address,
        which is the very thing `sub` exists to avoid.
        """
        if not isinstance(payload, dict):
            raise OAuthError("userinfo returned a non-object answer")
        subject = str(payload.get("sub") or "").strip()
        if not subject:
            raise OAuthError("userinfo has no subject (sub)")
        email = str(payload.get("email") or "").strip().lower()
        return cls(
            subject=subject,
            email=email,
            email_verified=bool(payload.get("email_verified")),
            name=str(payload.get("name")
                     or payload.get("preferred_username") or "").strip(),
            provider=str(provider or "").strip().lower(),
            raw=payload,
        )

    @property
    def key(self) -> str:
        """The link key: `provider:subject`, both lowercased."""
        return f"{self.provider.lower()}:{self.subject}"

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.key
