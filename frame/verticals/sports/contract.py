from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Fixture:
    key: str
    sport: str
    competition: str
    home: str
    away: str
    kickoff_date: str
    # a source that carries an in-play status fills this; a source that only
    # ships a kickoff leaves it empty and the caller derives the status
    status: str = ""


@dataclass(frozen=True)
class Market:
    key: str
    fixture_key: str
    kind: str
    selections: tuple[str, ...]
    prices: tuple[float, ...]


@dataclass(frozen=True)
class Quote:
    market_key: str
    prices: tuple[float, ...]
    offered_at: str
    version: int


@dataclass(frozen=True)
class BetReceipt:
    bet_key: str
    market_key: str
    stake_minor: int
    decimal_odds: float
    accepted_version: int


class SportsEngine(Protocol):
    """The whole sports surface we depend on. Anything satisfying this can be swapped."""

    def fixtures(self) -> list[Fixture]: ...
    def markets(self, fixture_key: str) -> list[Market]: ...
    def quote(self, market_key: str) -> Quote | None: ...
    def accept(self, bet_key: str, market_key: str, stake_minor: int) -> BetReceipt: ...
    def settle(self, bet_key: str, result: dict[str, str]) -> str: ...
    def void(self, bet_key: str, reason: str) -> str: ...
