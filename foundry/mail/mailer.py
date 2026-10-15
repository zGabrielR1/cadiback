# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""Mailers: Resend over HTTP, the console for dev, and a null that does nothing.

`resolve_mailer` is the only function a host needs at startup. It reads the
environment and returns a mailer that is *always safe to call* — the reason a
signup path can say `try: mailer.send(...) except MailError: pass` and never
worry that a missing key took the site down:

    MAIL_PROVIDER unset + RESEND_API_KEY set   -> Resend
    MAIL_PROVIDER unset + no key               -> console (logs, sends nothing)
    MAIL_PROVIDER=resend + no key              -> null (misconfigured: do nothing)
    MAIL_PROVIDER=console                      -> console
    MAIL_PROVIDER=none                         -> null

The distinction between *console* and *null* is deliberate: "no credentials
yet" is a normal dev state worth logging, while "resend, but the key is
missing" is a misconfiguration that must not silently pretend to send.
"""
from __future__ import annotations

import sys
from typing import Protocol, runtime_checkable

from ..envfile import first, load_env
from .message import MailError, Message, SendResult, deliverable
from .transport import Transport, urllib_transport

RESEND_BASE_URL = "https://api.resend.com"
DEFAULT_ENV_FILE = ".env.resend"

# Resend sits behind Cloudflare, which answers a request carrying a User-Agent
# it does not recognise — including `urllib`'s default — with a bare 403 that
# explains nothing. Sending an honest, stable identity is the difference
# between a working rail and every send failing for a reason no log states.
# It is set here rather than in the default transport so that an injected
# transport (httpx, requests) inherits it too.
USER_AGENT = "foundry-mail/0.1"


@runtime_checkable
class Mailer(Protocol):
    """What a host codes against. Nothing here names a provider."""

    name: str

    @property
    def enabled(self) -> bool:
        """True when :meth:`send` will really attempt delivery."""

    def send(self, message: Message, *, idempotency_key: str = "") -> SendResult:
        ...


class ResendMailer:
    """Resend over HTTPS. The account key never leaves this object."""

    name = "resend"

    def __init__(self, api_key: str, *, base_url: str = RESEND_BASE_URL,
                 default_from: str = "", default_from_name: str = "",
                 timeout: int = 15, transport: Transport | None = None,
                 allow_reserved: bool = False) -> None:
        self._api_key = api_key
        self.base_url = (base_url or RESEND_BASE_URL).rstrip("/")
        self.default_from = default_from
        self.default_from_name = default_from_name
        self.timeout = timeout
        self._transport = transport or urllib_transport
        self.allow_reserved = allow_reserved

    @property
    def enabled(self) -> bool:
        # An `http://` base would put the account key on the wire in clear, so
        # it is treated as unconfigured rather than used.
        return bool(self._api_key and self.base_url.startswith("https://"))

    def send(self, message: Message, *, idempotency_key: str = "") -> SendResult:
        if not self.enabled:
            raise MailError("Resend is not configured (RESEND_API_KEY / https base)")
        msg = message.with_defaults(from_email=self.default_from,
                                    from_name=self.default_from_name)
        msg.validate()
        if not self.allow_reserved:
            for addr in msg.recipients():
                if not deliverable(addr.email):
                    raise MailError(
                        f"refusing to send to a reserved/undeliverable address: {addr.email}")
        import json as _json
        body = _json.dumps(msg.to_payload()).encode("utf-8")
        headers = {"Authorization": f"Bearer {self._api_key}",
                   "Content-Type": "application/json",
                   "Accept": "application/json",
                   "User-Agent": USER_AGENT}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        out = self._transport("POST", f"{self.base_url}/emails", headers, body,
                              self.timeout)
        return SendResult(id=str(out.get("id") or ""), provider=self.name, raw=out)


class ConsoleMailer:
    """Writes one line per message to stderr. Sends nothing, needs no key.

    This is the default when no provider is configured, and the default in
    tests: a signup that would have emailed somebody prints the fact instead,
    and no test ever touches the network.
    """

    name = "console"

    def __init__(self, default_from: str = "console@localhost",
                 default_from_name: str = "") -> None:
        self.default_from = default_from
        self.default_from_name = default_from_name
        self.sent: list[dict] = []  # dev/test convenience: what would have gone out

    @property
    def enabled(self) -> bool:
        return False

    def send(self, message: Message, *, idempotency_key: str = "") -> SendResult:
        msg = message.with_defaults(from_email=self.default_from,
                                    from_name=self.default_from_name)
        msg.validate()
        to = ", ".join(a.email for a in msg.recipients())
        record = {"to": to, "subject": msg.subject,
                  "idempotency_key": idempotency_key}
        self.sent.append(record)
        print(f"[mail:console] would send to {to!r}: {msg.subject!r}", file=sys.stderr)
        return SendResult(id=f"console-{len(self.sent)}", provider=self.name, raw=record)


class NullMailer:
    """Does nothing, on purpose. Used when a provider is named but unusable.

    `send` raises rather than swallow: a host that wraps mail in try/except
    (as it should) sees a clear reason in the log, while the attempt is
    refused instead of silently dropped.
    """

    name = "none"

    @property
    def enabled(self) -> bool:
        return False

    def send(self, message: Message, *, idempotency_key: str = "") -> SendResult:
        raise MailError("mail is disabled (MAIL_PROVIDER=none or no usable provider)")


def resolve_mailer(*, env: dict[str, str] | None = None,
                   env_file: str = "") -> Mailer:
    """Build a mailer from the environment.

    ``env`` is exclusive when given (tests): no ambient state is consulted, so
    a test can never be steered by this machine's own credentials. Otherwise a
    real environment variable wins over a line in ``env_file``.
    """
    source = dict(env) if env is not None else load_env(env_file)
    provider = first(source, "MAIL_PROVIDER").lower()
    key = first(source, "RESEND_API_KEY")
    from_email = first(source, "MAIL_FROM")
    from_name = first(source, "MAIL_FROM_NAME")
    base_url = first(source, "RESEND_BASE_URL", RESEND_BASE_URL).rstrip("/")

    if provider == "none":
        return NullMailer()
    if provider == "console":
        return ConsoleMailer(from_email or "console@localhost", from_name)
    if provider == "resend":
        return ResendMailer(key, base_url=base_url, default_from=from_email,
                            default_from_name=from_name) if key else NullMailer()
    # auto: a key means the real thing, its absence means the console.
    if key:
        return ResendMailer(key, base_url=base_url, default_from=from_email,
                            default_from_name=from_name)
    return ConsoleMailer(from_email or "console@localhost", from_name)
