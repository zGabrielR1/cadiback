# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""The one place Better Auth settings are read, and the one place they fail safe.

The Python host does not run Better Auth. It needs exactly four facts:

* where the auth server lives (for the health report and local runs),
* the shared bridge secret (to verify a signed social identity),
* which providers the storefront may offer, and
* whether the host is configured at all.

All four come from the environment (or from ``.env.betterauth`` when no
mapping is passed, per the kit's one-read rule). A half-configured rail is
treated as disabled: without a bridge secret no signed claim can be trusted,
so the host must hide the buttons rather than offer a login that cannot land.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..envfile import first, load_env

DEFAULT_ENV_FILE = ".env.betterauth"
DEFAULT_PROVIDERS = ("google", "facebook", "apple")
DEFAULT_INTERNAL_URL = "http://127.0.0.1:3100"


@dataclass(frozen=True)
class BetterAuthConfig:
    """What the Python host needs to know about the auth server."""

    base_url: str = ""
    secret: str = ""
    bridge_secret: str = ""
    providers: tuple[str, ...] = DEFAULT_PROVIDERS
    internal_url: str = DEFAULT_INTERNAL_URL
    api_key: str = ""

    @property
    def configured(self) -> bool:
        """A bridge secret is the only credential this side ever holds.

        Without it a signed claim cannot be verified, so the social buttons
        must stay hidden even if the auth server itself is running. The
        provider credentials live only in the Node process.
        """
        return bool(self.bridge_secret)

    @property
    def provider_ids(self) -> tuple[str, ...]:
        """Provider ids the storefront may render, in a stable order."""
        return tuple(dict.fromkeys(p.strip().lower()
                                   for p in self.providers if p.strip()))

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None,
                 env_file: str = DEFAULT_ENV_FILE) -> "BetterAuthConfig":
        source = dict(env) if env is not None else load_env(
            env_file, secret_name="BETTER_AUTH_BRIDGE_SECRET")
        providers = tuple(
            part.strip().lower()
            for part in first(source, "BETTER_AUTH_PROVIDERS",
                              ",".join(DEFAULT_PROVIDERS)).split(",")
            if part.strip()
        )
        return cls(
            base_url=first(source, "BETTER_AUTH_URL").rstrip("/"),
            secret=first(source, "BETTER_AUTH_SECRET"),
            bridge_secret=first(source, "BETTER_AUTH_BRIDGE_SECRET"),
            providers=providers or DEFAULT_PROVIDERS,
            internal_url=(first(source, "BETTER_AUTH_INTERNAL_URL",
                                DEFAULT_INTERNAL_URL).rstrip("/")
                          or DEFAULT_INTERNAL_URL),
            api_key=first(source, "BETTER_AUTH_API_KEY"),
        )


def resolve_betterauth(env: dict[str, str] | None = None,
                       env_file: str = DEFAULT_ENV_FILE) -> BetterAuthConfig:
    """Build the config from the environment; never raises on absence."""
    return BetterAuthConfig.from_env(env=env, env_file=env_file)
