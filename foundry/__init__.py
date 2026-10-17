# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""foundry — a kit of small, host-agnostic modules for building web services.

One rule makes a module usable three very different places — inside a
zero-dependency single container, inside a FastAPI service, and inside a
Next.js serverless function:

    the core is stdlib-only, and every outside dependency is injected.

So a foundry module exposes exactly three things and nothing else:

  * frozen dataclasses for the values it moves around,
  * a small ``Protocol`` for each side effect it performs (a transport, a
    mailer), with a working stdlib default, and
  * one ``resolve_*`` function that reads configuration from the environment.

It never imports a web framework, never reads a global, and never decides
policy for the host. The host owns the business logic, the templates, and the
routes; foundry owns the boring, easy-to-get-wrong plumbing underneath them.

Hosts consume a module one of two ways:

  * as a path dependency (``uv``/``pip`` pointing at this repository), or
  * vendored — ``scripts/vendor.py`` copies *just* the modules a host needs
    into that host's tree, so its repository and its deploy stay
    self-contained and a machine with no package index can still build it.

The vendored copy is the reason the operator can stay stdlib-only while
sharing code with a FastAPI wallet: nothing foundry ships has a dependency to
bring along.
"""
from __future__ import annotations

__version__ = "0.1.0"

# The modules that exist today. Kept as data so the vendor script, the docs and
# the tests agree on one list instead of three.
MODULES = ("envfile", "mail", "turnstile", "oauth", "deploy")
