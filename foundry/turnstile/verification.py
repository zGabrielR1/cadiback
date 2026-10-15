# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""The values a Turnstile check moves around: a result, and its refusals.

A siteverify answer is a bare JSON object with a handful of fields a caller
must read *together* to decide anything: `success`, the `action` the widget was
rendered with, and the `hostname` it was solved on. Reading three keys off a
dict at every call site is how a check silently degrades to "did `success`
come back truthy" — so the answer becomes a frozen value with one
:meth:`Verification.validate` that states the whole policy in one place.

The policy is exactly Cloudflare's canonical one, and it is deliberately
stricter than `success === true`:

  * `success` must be true, and
  * the returned `action` must equal the one the surface expected, and
  * the returned `hostname` must be on the deployment's allowlist.

A token minted on someone else's page with our public site key passes the
first check and fails the third; a token lifted from a signup form passes the
first and fails the second.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class TurnstileError(ValueError):
    """A refusal, a misconfiguration, or an unreachable siteverify.

    Phrased for a log line or a client message: it never contains the secret
    key, and it never echoes the raw provider body — only its error codes.
    """


@dataclass(frozen=True)
class Verification:
    """One siteverify answer, reduced to what the policy check needs."""

    success: bool = False
    action: str = ""
    hostname: str = ""
    challenge_ts: str = ""
    error_codes: tuple = ()
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_response(cls, payload) -> "Verification":
        """Build from a siteverify JSON object.

        A non-object answer is refused rather than coerced: an HTML error page
        parsed into `{}` would otherwise look like a plain refusal and hide the
        fact that the request never reached siteverify.
        """
        if not isinstance(payload, dict):
            raise TurnstileError("siteverify returned a non-object answer")
        codes = payload.get("error-codes") or []
        if isinstance(codes, str):
            codes = [codes]
        return cls(
            success=bool(payload.get("success")),
            action=str(payload.get("action") or ""),
            hostname=str(payload.get("hostname") or ""),
            challenge_ts=str(payload.get("challenge_ts") or ""),
            error_codes=tuple(str(code) for code in codes),
            raw=payload,
        )

    def validate(self, *, action: str = "", hostnames=()) -> "Verification":
        """Apply the canonical policy; return self, or raise TurnstileError.

        ``action`` is optional so a surface with no action of its own can skip
        that half; ``hostnames`` is not — an empty allowlist refuses, because
        a check with no expected hostname accepts a token solved anywhere.
        """
        if not self.success:
            detail = ", ".join(self.error_codes) or "no reason given"
            raise TurnstileError(f"turnstile refused the token ({detail})")
        if action and self.action != action:
            raise TurnstileError(
                f"turnstile action mismatch: expected {action!r}, "
                f"got {self.action!r}")
        allowed = {str(host).strip().lower() for host in hostnames
                   if str(host).strip()}
        if not allowed:
            raise TurnstileError("no expected hostnames configured; refusing")
        if self.hostname.strip().lower() not in allowed:
            raise TurnstileError(
                f"turnstile hostname not allowed: {self.hostname!r}")
        return self
