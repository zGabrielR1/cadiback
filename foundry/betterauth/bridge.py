# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""The signed claim Better Auth's bridge sends, and its refusals.

The bridge is a plain HTTP POST from the Node auth server to the Python
host. It carries the identity Better Auth just verified and a timestamp,
signed with a shared secret over the exact bytes of the JSON body. Two
checks make the claim trustworthy and current:

* **constant-time HMAC-SHA256** over the body, so a forged or edited claim
  is refused before anything is read from it; and
* **a short window** (``MAX_AGE``), so a captured bridge call cannot be
  replayed tomorrow to link a stale identity.

The module knows nothing about accounts, wallets or CPF. It hands the host a
frozen :class:`SocialIdentity` and lets the host decide what that person may
do, exactly the line the kit draws between plumbing and policy.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass

MAX_AGE = 120


class BridgeError(ValueError):
    """A malformed, unsigned, forged or expired bridge claim."""


@dataclass(frozen=True)
class SocialIdentity:
    """One provider-verified identity, reduced to what account-linking needs.

    ``subject`` is the provider's stable id for the person (Google's ``sub``,
    Facebook's ``id``, Apple's ``sub``). ``email`` may be empty: Apple only
    sends it on the first consent and Facebook may omit it. The host decides
    whether an email-less identity may complete a profile.
    """

    provider: str
    subject: str
    email: str = ""
    email_verified: bool = False
    name: str = ""

    def __post_init__(self) -> None:
        provider = str(self.provider or "").strip().lower()
        subject = str(self.subject or "").strip()
        if not provider:
            raise BridgeError("a social identity needs a provider")
        if not subject:
            raise BridgeError("a social identity needs a subject")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "email", str(self.email or "").strip().lower())
        object.__setattr__(self, "name", str(self.name or "").strip())
        object.__setattr__(self, "email_verified", _truthy(self.email_verified))

    @property
    def key(self) -> str:
        """The link key: ``provider:subject``, both normalised."""
        return f"{self.provider}:{self.subject}"


def _truthy(value: object) -> bool:
    """Apple serialises ``email_verified`` as the string ``"true"``."""
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def payload_for(identity: SocialIdentity, *,
                now: float | None = None) -> dict:
    """The JSON claim the Node bridge signs. Exposed so both sides agree."""
    return {
        "provider": identity.provider,
        "subject": identity.subject,
        "email": identity.email,
        "email_verified": identity.email_verified,
        "name": identity.name,
        "ts": int(time.time() if now is None else now),
    }


def _canonical(payload: dict) -> bytes:
    """The bytes that get signed: sorted keys, no whitespace surprises."""
    return json.dumps(payload, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def signature_for(payload: dict | bytes, secret: str) -> str:
    """``sha256=<hex>`` over the canonical payload."""
    if isinstance(payload, dict):
        body = _canonical(payload)
    else:
        body = payload
    if not secret:
        raise BridgeError("bridge secret is not configured")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return "sha256=" + digest


def verify_bridge(body: bytes, signature: str, secret: str, *,
                  now: float | None = None,
                  max_age: int = MAX_AGE) -> SocialIdentity:
    """Verify one bridge claim and return the identity it names.

    ``body`` must be the exact bytes received (the signature covers them),
    not a re-serialised object: re-encoding changes whitespace and key order.
    An absent secret, a missing/malformed signature, a body that is not a
    JSON object, a missing timestamp, a timestamp outside the window, or a
    claim with no provider/subject is refused with :class:`BridgeError`.
    """
    if not secret:
        raise BridgeError("bridge is not configured")
    if not isinstance(signature, str) or not signature.strip():
        raise BridgeError("missing bridge signature")
    expected = signature_for(body, secret)
    if not hmac.compare_digest(expected, signature.strip()):
        raise BridgeError("bridge signature does not match")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BridgeError("bridge body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise BridgeError("bridge body must be a JSON object")
    stamp = payload.get("ts")
    try:
        issued = float(stamp)
    except (TypeError, ValueError) as exc:
        raise BridgeError("bridge claim has no timestamp") from exc
    current = time.time() if now is None else float(now)
    if issued > current + max_age:
        raise BridgeError("bridge claim is from the future")
    if current - issued > max_age:
        raise BridgeError("bridge claim has expired")
    return SocialIdentity(
        provider=str(payload.get("provider") or ""),
        subject=str(payload.get("subject") or ""),
        email=str(payload.get("email") or ""),
        email_verified=payload.get("email_verified"),
        name=str(payload.get("name") or ""),
    )
