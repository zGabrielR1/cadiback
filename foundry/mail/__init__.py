# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""mail — send email through Resend (or the console), with no dependency.

The module is a thin, honest shell around one HTTP call: ``POST {base}/emails``
with a bearer key. Everything that usually goes wrong around that call is
handled here so no host has to re-solve it:

  * credentials come from the environment, never from code or a log;
  * the key is never replayed to another host on a redirect;
  * a reserved or malformed recipient (``example.com``, ``.invalid``) is
    refused *locally* — the fastest way to burn a sending domain's reputation
    is to hand a provider a list of addresses that cannot exist;
  * an ``Idempotency-Key`` is passed through, so a retried signup does not
    send a second welcome email;
  * an unconfigured host gets a console mailer that logs instead of failing,
    which is what makes the same code run in dev, in tests and in production.

Hosts keep their own copy. Nothing here knows what a "player", a "wallet" or a
"tenant" is; a host builds a :class:`Message` and calls :meth:`Mailer.send`.
"""
from __future__ import annotations

from .mailer import ConsoleMailer, Mailer, NullMailer, ResendMailer, resolve_mailer
from .message import Address, Attachment, MailError, Message, SendResult, deliverable
from .templates import render, wrap_html
from .transport import Transport, urllib_transport

__all__ = [
    "Address",
    "Attachment",
    "ConsoleMailer",
    "MailError",
    "Mailer",
    "Message",
    "NullMailer",
    "ResendMailer",
    "SendResult",
    "Transport",
    "deliverable",
    "render",
    "resolve_mailer",
    "urllib_transport",
    "wrap_html",
]
