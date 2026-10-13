from __future__ import annotations

from dataclasses import dataclass, field

from .contract import BetReceipt, Fixture, Market, Quote


class EngineError(RuntimeError):
    pass


SELECTIONS = frozenset({"home", "draw", "away", "over", "under"})


@dataclass
class SportsStub:
    """Deterministic engine for contract tests. Never used in a customer path."""

    prices: dict[str, tuple[float, ...]] = field(
        default_factory=lambda: {
            "mkt:bra.1:2026-10-03:FLA-VAS:1x2": (1.95, 3.40, 4.20),
            "mkt:bra.1:2026-10-03:FLA-VAS:2way": (1.90, 1.92),
        }
    )
    versions: dict[str, int] = field(default_factory=dict)
    accepted: dict[str, BetReceipt] = field(default_factory=dict)
    settled: dict[str, str] = field(default_factory=dict)

    def fixtures(self) -> list[Fixture]:
        return [
            Fixture(
                key="fix:bra.1:2026-10-03:FLA-VAS",
                sport="football",
                competition="bra.1",
                home="Fluminense",
                away="Vasco",
                kickoff_date="2026-10-03",
            )
        ]

    def markets(self, fixture_key: str) -> list[Market]:
        prefix = f"mkt:{fixture_key.split(':', 1)[1]}"
        found: list[Market] = []
        for key, prices in self.prices.items():
            if not key.startswith(prefix):
                continue
            kind = key.rsplit(":", 1)[1]
            selections = ("home", "draw", "away") if kind == "1x2" else ("over", "under")
            found.append(
                Market(
                    key=key,
                    fixture_key=fixture_key,
                    kind=kind,
                    selections=selections,
                    prices=prices,
                )
            )
        return found

    def quote(self, market_key: str) -> Quote | None:
        prices = self.prices.get(market_key)
        if prices is None:
            return None
        version = self.versions.get(market_key, 1)
        return Quote(market_key=market_key, prices=prices, offered_at="2026-10-03T00:00:00+00:00", version=version)

    def reprice(self, market_key: str, prices: tuple[float, ...]) -> int:
        if market_key not in self.prices:
            raise EngineError(f"unknown market: {market_key}")
        self.prices[market_key] = prices
        self.versions[market_key] = self.versions.get(market_key, 1) + 1
        return self.versions[market_key]

    def accept(self, bet_key: str, market_key: str, stake_minor: int) -> BetReceipt:
        quote = self.quote(market_key)
        if quote is None:
            raise EngineError(f"no quote for {market_key}")
        if bet_key in self.accepted:
            raise EngineError(f"bet already accepted: {bet_key}")
        if stake_minor <= 0:
            raise EngineError("stake must be positive")
        receipt = BetReceipt(
            bet_key=bet_key,
            market_key=market_key,
            stake_minor=stake_minor,
            decimal_odds=quote.prices[0],
            accepted_version=quote.version,
        )
        self.accepted[bet_key] = receipt
        return receipt

    def settle(self, bet_key: str, result: dict[str, str]) -> str:
        if bet_key not in self.accepted:
            raise EngineError(f"unknown bet: {bet_key}")
        if bet_key in self.settled:
            raise EngineError(f"bet already settled: {bet_key}")
        selection = result.get("selection")
        if selection not in SELECTIONS:
            raise EngineError(f"settlement selection must be one of {sorted(SELECTIONS)}, got {selection!r}")
        state = "lost" if selection == "away" or selection == "under" else "won"
        self.settled[bet_key] = state
        return state

    def void(self, bet_key: str, reason: str) -> str:
        if bet_key in self.settled:
            raise EngineError(f"cannot void a settled bet: {bet_key}")
        self.settled[bet_key] = f"void:{reason}"
        return self.settled[bet_key]
