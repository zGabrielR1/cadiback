# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""The one place the OIDC settings are read, and the one place they are shaped.

`OAuthConfig.from_env` is the module's single `from_env`, per the kit's third
rule: configuration comes only from the environment (or an explicitly passed
mapping, which makes a test hermetic), and every failure mode degrades to
"unconfigured" rather than raising. A missing endpoint, a blank client id, an
`http://` endpoint, or a missing secret all produce a config whose
:attr:`configured` is False, which is what lets the operator hide the social
buttons instead of offering a login that cannot complete.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..envfile import first, load_env

DEFAULT_ENV_FILE = ".env.authgear"

# The openid scope is what makes `sub` appear in userinfo; profile and email
# add the display name and address. Anything else a host needs it adds itself.
DEFAULT_SCOPES = ("openid", "profile", "email")

_PROVIDER_RE = re.compile(r"^[a-z0-9._-]{2,32}$")


@dataclass(frozen=True)
class Provider:
    """One social identity to offer. `id` is what the broker understands."""

    id: str
    label: str = ""

    def shown_label(self) -> str:
        return self.label or self.id.capitalize()


@dataclass(frozen=True)
class OAuthConfig:
    endpoint: str = ""
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""
    scopes: tuple[str, ...] = DEFAULT_SCOPES
    providers: tuple[Provider, ...] = ()
    timeout: int = 10

    @property
    def configured(self) -> bool:
        """True only when the flow could actually complete.

        An `http://` endpoint would put the client secret on the wire in
        clear, and a missing secret means a *Traditional Web Application* was
        not set up, so the token exchange would be refused. Both are treated
        as unconfigured rather than used.
        """
        return bool(self.endpoint.startswith("https://") and self.client_id
                    and self.client_secret)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None,
                 env_file: str = DEFAULT_ENV_FILE) -> "OAuthConfig":
        source = dict(env) if env is not None else load_env(
            env_file, secret_name="AUTHGEAR_CLIENT_SECRET")
        endpoint = first(source, "AUTHGEAR_ENDPOINT").rstrip("/")
        providers = _providers(first(source, "AUTHGEAR_PROVIDERS",
                                     "google,facebook"))
        scopes = _split(first(source, "AUTHGEAR_SCOPES",
                              " ".join(DEFAULT_SCOPES)))
        try:
            timeout = int(first(source, "AUTHGEAR_TIMEOUT", "10"))
        except ValueError:
            timeout = 10
        return cls(
            endpoint=endpoint,
            client_id=first(source, "AUTHGEAR_CLIENT_ID"),
            client_secret=first(source, "AUTHGEAR_CLIENT_SECRET")
            or first(source, "AUTHGEAR_SECRET"),
            redirect_uri=first(source, "AUTHGEAR_REDIRECT_URI"),
            scopes=tuple(scopes) or DEFAULT_SCOPES,
            providers=providers,
            timeout=timeout,
        )


def _split(value: str) -> list[str]:
    return [part.strip() for part in (value or "").replace(",", " ").split()
            if part.strip()]


def _providers(value: str) -> tuple[Provider, ...]:
    out: list[Provider] = []
    for part in value.split(","):
        raw = part.strip()
        if not raw:
            continue
        ident, _, label = raw.partition(":")
        ident = ident.strip().lower()
        if not _PROVIDER_RE.match(ident):
            continue  # a malformed id would render a button that cannot work
        out.append(Provider(id=ident, label=label.strip()))
    return tuple(out)
