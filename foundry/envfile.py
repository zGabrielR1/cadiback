# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""Read `KEY=value` files — the one dotenv parser in the kit.

Three copies of this parser had already grown independently (the operator's
Asaas client, its Render deploy script, and its deploy docs). They all agreed
on the shape — one setting per line, `#` comments, and an inline ` #` allowed
so a value may carry a trailing note — so this is that shape, stated once.

Parsing is deliberately forgiving. A missing file, an unreadable file, or a
line with no `=` yields fewer settings rather than an exception, because
"unconfigured" is a normal state for every service built on this kit: with no
credentials the operator falls back to an instant demo credit, and Resend
falls back to the console. A typo in a gitignored file must never take the
process down.

The same leniency is why an inline comment is split on `" #"` and not on a
bare `#`: a secret may legitimately contain a `#`, and only a `#` that follows
a space and the value is treated as the start of a note.
"""
from __future__ import annotations

import os


def read_env_file(path: str) -> dict[str, str]:
    """`KEY=value` lines out of a dotenv file. Blanks and comments ignored."""
    values: dict[str, str] = {}
    if not path or not os.path.isfile(path):
        return values
    try:
        # `utf-8-sig` drops a byte-order mark if an editor wrote one. Without
        # it the first name would silently become "\ufeffRESEND_API_KEY", the
        # setting would look absent, and the failure would be invisible.
        with open(path, "r", encoding="utf-8-sig") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, equals, value = line.partition("=")
        if not equals:
            # A line with no `=`, and no `#`, is malformed for a `KEY=value`
            # file — and treating the whole line as a name would invent a
            # setting nobody can look up. Skipping it is the same leniency the
            # rest of the parser shows, and it is what lets `read_secret`
            # below recognise a bare one-value credential file.
            continue
        value = value.split(" #", 1)[0].strip()
        if name.strip():
            values[name.strip()] = value
    return values


def read_secret(path: str) -> str:
    """A one-value credential file: the secret alone on a line, or `""`.

    Not every credential file is `KEY=value`. The shape this workspace already
    uses for the Render API key is a single bare line holding just the secret,
    with no name in front of it (there is only one thing in the file, so the
    name would be redundant). Comments and blank lines around it are ignored;
    a file that is really `KEY=value` yields `""` here — use
    :func:`read_env_file` for that, or :func:`load_env` which accepts either.
    """
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return ""
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            return ""  # a named setting, not a bare secret
        return line
    return ""


def load_env(env_file: str = "", environ: dict[str, str] | None = None,
             *, secret_name: str = "") -> dict[str, str]:
    """File first, real environment second.

    A genuine environment variable always wins over a line in a file, so a
    host can override a baked-in default (or a developer's local file) without
    editing either. Pass ``environ`` to read a fixed mapping — tests use that
    so they can never be steered by the machine's own credentials.

    ``secret_name`` accepts the bare one-value credential file too: when the
    file holds no `KEY=value` line at all, its single value is filed under
    ``secret_name``. That is what makes a credential file readable whether it
    was written as ``RESEND_API_KEY=re_…`` or as just ``re_…``.
    """
    source = read_env_file(env_file)
    if not source and secret_name:
        secret = read_secret(env_file)
        if secret:
            source = {secret_name: secret}
    source.update(os.environ if environ is None else environ)
    return source


def first(values: dict[str, str], key: str, default: str = "") -> str:
    """The value at ``key``, stripped, or ``default`` when absent/blank."""
    return (values.get(key) or "").strip() or default


def truthy(value: str, default: bool = False) -> bool:
    """A forgiving boolean: `1/true/yes/on` (any case) are true.

    Settings arrive as strings from an env file, so "false" — a non-empty
    string — is the classic bug when a host does a bare `bool(...)`. This
    reads the words a human would actually write.
    """
    text = (value or "").strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on", "y", "t"}
