# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""The values a mail module moves around: an address, a message, a result.

These are frozen dataclasses, not dicts, because an email that reaches a
customer is the kind of thing that should be impossible to mutate halfway
through building it. They also carry the validation, so an impossible message
(no recipient, no subject, neither html nor text) is rejected before a
provider ever sees it — a 422 from Resend is a worse error message than the
one produced here.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field, replace

# Deliberately loose: the provider is the real authority on deliverability.
# This only catches shapes that are certainly not addresses, so the stricter
# checks below can be about *policy* (reserved domains) rather than syntax.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

# RFC 2606 / 6761 reserved names. Mail to these can never be delivered, so a
# provider accepts it and then bounces it — which is exactly the traffic that
# damages a sending domain. Refuse it before it leaves the process.
_RESERVED_DOMAINS = frozenset({"example.com", "example.org", "example.net"})
_RESERVED_SUFFIXES = (".invalid", ".test", ".localhost", ".example", ".local",
                      ".internal")


class MailError(ValueError):
    """A refusal, a misconfiguration, or an unreachable provider.

    Phrased for a log line or a panel message: it never contains the API key
    or any other secret, even when the provider's own error body did.
    """


@dataclass(frozen=True)
class Address:
    email: str
    name: str = ""

    def formatted(self) -> str:
        # `Name <addr>` is what every mail API expects; a bare address is the
        # fallback when the caller has no display name.
        return f"{self.name} <{self.email}>" if self.name else self.email


def _as_address(value) -> Address:
    """Accept the three shapes a caller might reasonably hand over."""
    if isinstance(value, Address):
        return value
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return Address(str(value[0]).strip(), str(value[1]).strip())
    return Address(str(value or "").strip())


def _as_list(value) -> list:
    """Normalize a recipient field to a list.

    A *list* is always a list of recipients; a *2-tuple of strings* is the
    `(email, name)` convenience form. Keeping the two shapes apart means
    `["a@b.com", "c@d.com"]` can never be misread as one address named
    `"c@d.com"`, and the empty tuple used as a default field collapses to `[]`.
    """
    if value is None:
        return []
    if isinstance(value, (str, Address)):
        return [value]
    if isinstance(value, tuple):
        if len(value) == 2 and all(isinstance(part, str) for part in value):
            return [value]
        return list(value)
    return list(value)


def deliverable(email: str, *, allow_reserved: bool = False) -> bool:
    """True when an address is *worth handing to a provider*.

    This is a spend/reputation guard, not a validity oracle: it rejects the
    shapes that are certainly undeliverable and the reserved domains that must
    never receive mail, and trusts the provider for everything else.
    """
    addr = (email or "").strip().lower()
    if not _EMAIL_RE.match(addr):
        return False
    if allow_reserved:
        return True
    domain = addr.rsplit("@", 1)[1]
    return not (domain in _RESERVED_DOMAINS
                or domain.endswith(_RESERVED_SUFFIXES))


@dataclass(frozen=True)
class Attachment:
    filename: str
    content: bytes | str
    content_type: str = "application/octet-stream"

    def to_payload(self) -> dict:
        data = (self.content.encode("utf-8")
                if isinstance(self.content, str) else self.content)
        return {"filename": self.filename,
                "content": base64.b64encode(data).decode("ascii"),
                "content_type": self.content_type}


@dataclass(frozen=True)
class Message:
    """One email, reduced to what a mail API needs.

    ``from_email``/``from_name`` are optional: a mailer with a configured
    default sender fills them in, so a host that always sends as the same
    address never has to repeat it on every message.
    """

    to: object
    subject: str = ""
    html: str = ""
    text: str = ""
    from_email: str = ""
    from_name: str = ""
    reply_to: str = ""
    cc: object = ()
    bcc: object = ()
    headers: dict[str, str] = field(default_factory=dict)
    tags: tuple = ()
    attachments: tuple = ()

    # -- normalization ---------------------------------------------------
    def recipients(self) -> list[Address]:
        return [_as_address(a) for a in _as_list(self.to)] + \
               [_as_address(a) for a in _as_list(self.cc)] + \
               [_as_address(a) for a in _as_list(self.bcc)]

    def with_defaults(self, *, from_email: str = "", from_name: str = "") -> Message:
        """Fill a missing sender from a mailer's configured default."""
        if self.from_email:
            return self
        return replace(self, from_email=from_email, from_name=from_name or self.from_name)

    def validate(self) -> None:
        if not self.recipients():
            raise MailError("a message needs at least one recipient")
        if not self.from_email:
            raise MailError("a message needs a sender (set MAIL_FROM or the mailer default)")
        if not (self.subject or "").strip():
            raise MailError("a message needs a subject")
        if not (self.html or self.text):
            raise MailError("a message needs an html or text body")
        for addr in self.recipients():
            if not deliverable(addr.email, allow_reserved=True):
                raise MailError(f"malformed recipient address: {addr.email!r}")

    def to_payload(self) -> dict:
        """The Resend request body. Unknown/blank fields are omitted so the
        provider's defaults (not our blanks) apply."""
        sender = Address(self.from_email, self.from_name).formatted()
        body: dict = {
            "from": sender,
            "to": [_as_address(a).formatted() for a in _as_list(self.to)],
            "subject": self.subject,
        }
        if self.html:
            body["html"] = self.html
        if self.text:
            body["text"] = self.text
        if self.reply_to:
            body["reply_to"] = self.reply_to
        cc = [_as_address(a).formatted() for a in _as_list(self.cc)]
        bcc = [_as_address(a).formatted() for a in _as_list(self.bcc)]
        if cc:
            body["cc"] = cc
        if bcc:
            body["bcc"] = bcc
        if self.headers:
            body["headers"] = dict(self.headers)
        if self.tags:
            body["tags"] = [dict(t) if isinstance(t, dict) else {"name": str(t)}
                            for t in self.tags]
        if self.attachments:
            body["attachments"] = [
                a.to_payload() if isinstance(a, Attachment)
                else Attachment(**a).to_payload() for a in self.attachments]
        return body


@dataclass(frozen=True)
class SendResult:
    """What came back. ``id`` is the provider's handle for the message — the
    thing a support ticket quotes, so it is surfaced rather than buried."""

    id: str = ""
    provider: str = ""
    raw: dict = field(default_factory=dict)
