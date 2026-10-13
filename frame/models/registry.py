from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..core import devig


class RegistryError(KeyError):
    pass


@runtime_checkable
class FairProbabilityProvider(Protocol):
    name: str
    kinds: tuple[str, ...]

    def fair(self, prices: tuple[float, ...], kind: str) -> list[float]: ...


@dataclass(frozen=True)
class DevigProvider:
    name: str
    kinds: tuple[str, ...] = (devig.ONE_X_TWO, devig.TWO_WAY)

    def fair(self, prices: tuple[float, ...], kind: str) -> list[float]:
        if kind not in self.kinds:
            raise RegistryError(f"{self.name} does not serve market kind {kind}")
        return [float(p) for p in devig.fair(prices, method=self.name, kind=kind)]


@dataclass
class ModelRegistry:
    """The frame outlives the model. Providers register once; consumers ask by name."""

    _providers: dict[str, FairProbabilityProvider] = field(default_factory=dict)

    def register(self, provider: FairProbabilityProvider) -> None:
        if not getattr(provider, "name", ""):
            raise RegistryError("provider needs a name")
        if provider.name in self._providers:
            raise RegistryError(f"provider already registered: {provider.name}")
        self._providers[provider.name] = provider

    def get(self, name: str) -> FairProbabilityProvider:
        if name not in self._providers:
            raise RegistryError(f"unknown provider: {name}; known={sorted(self._providers)}")
        return self._providers[name]

    def names(self) -> list[str]:
        return sorted(self._providers)

    def resolve(self, kind: str) -> FairProbabilityProvider:
        for name in self.names():
            provider = self._providers[name]
            if kind in provider.kinds:
                return provider
        raise RegistryError(f"no provider serves market kind {kind}")

    def fair(self, name: str, prices: tuple[float, ...], kind: str) -> list[float]:
        return self.get(name).fair(prices, kind)


def default_registry() -> ModelRegistry:
    registry = ModelRegistry()
    for method in devig.METHODS:
        registry.register(DevigProvider(name=method))
    return registry
