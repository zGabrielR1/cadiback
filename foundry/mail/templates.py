# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""Two tiny helpers so a host can build an email body without a template engine.

This is intentionally *not* a template language. It is `{{name}}`
substitution plus a minimal HTML wrapper — enough that a signup email is a
plain string in the host's source instead of a string built by five `+`
concatenations, and small enough that there is nothing new to learn or
sandbox. Anything richer belongs to the host's own framework.

`render` escapes nothing by default: the caller chooses the values, and the
caller knows whether a value is markup. The opinionated version is
:func:`render`, used with ``escape=True`` for values that came from a user.
"""
from __future__ import annotations

import html as _html
import re

_TOKEN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def render(text: str, values: dict | None = None, *, escape: bool = False,
           keep_unknown: bool = False) -> str:
    """Replace ``{{key}}`` with ``values[key]``.

    An unknown key raises unless ``keep_unknown`` is set. A typo that ships a
    literal ``{{link}}`` to a customer is worse than a loud failure in the
    signup path, so the default is loud.
    """
    values = values or {}

    def swap(match: re.Match) -> str:
        key = match.group(1)
        if key not in values:
            if keep_unknown:
                return match.group(0)
            raise KeyError(f"no value for template key {key!r}")
        value = "" if values[key] is None else str(values[key])
        return _html.escape(value) if escape else value

    return _TOKEN.sub(swap, text or "")


def wrap_html(*, title: str, body: str, footer: str = "") -> str:
    """A bare, inline-styled HTML document.

    Inline styles and a single column are the boring choices that survive
    every mail client; there is no external CSS, no web font and no image, so
    nothing here depends on the recipient loading anything.
    """
    footer_html = (f'<p style="margin:24px 0 0;color:#6b7280;font-size:12px">'
                   f'{_html.escape(footer)}</p>' if footer else "")
    return (
        '<!doctype html><html><body style="margin:0;padding:24px;'
        'background:#f3f4f6;font-family:-apple-system,Segoe UI,Roboto,'
        'Helvetica,Arial,sans-serif;color:#111827">'
        '<div style="max-width:520px;margin:0 auto;background:#ffffff;'
        'border-radius:12px;padding:28px">'
        f'<h1 style="margin:0 0 12px;font-size:20px">{_html.escape(title)}</h1>'
        f'<div style="font-size:15px;line-height:1.55">{body}</div>'
        f'{footer_html}'
        "</div></body></html>"
    )
