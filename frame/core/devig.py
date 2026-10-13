from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .money import check_odds

MULTIPLICATIVE = "multiplicative"
POWER = "power"
ADDITIVE = "additive"
SHIN = "shin"
METHODS = (MULTIPLICATIVE, POWER, ADDITIVE, SHIN)

ONE_X_TWO = "1x2"
TWO_WAY = "2way"
MARKET_KINDS = {ONE_X_TWO: 3, TWO_WAY: 2}

MAX_OVERROUND = 0.25
MIN_MARGIN = 0.0
MAX_MARGIN = 0.35


class MarketError(ValueError):
    pass


def implied(prices: Sequence[int | float | str | Decimal]) -> list[Decimal]:
    if not prices:
        raise MarketError("no prices")
    return [Decimal(1) / check_odds(p) for p in prices]


def overround(prices: Sequence[int | float | str | Decimal]) -> Decimal:
    total = sum(implied(prices), Decimal(0))
    return total - Decimal(1)


def check_market(prices: Sequence[int | float | str | Decimal], kind: str) -> None:
    expected = MARKET_KINDS.get(kind)
    if expected is None:
        raise MarketError(f"unknown market kind {kind!r}; expected one of {sorted(MARKET_KINDS)}")
    if len(prices) != expected:
        raise MarketError(f"market kind {kind} needs exactly {expected} prices, got {len(prices)}")
    book = overround(prices)
    if book < 0:
        raise MarketError(f"negative book (arb) is not a margin book: {book}")
    if book > MAX_OVERROUND:
        raise MarketError(f"overround {book:.4f} above ceiling {MAX_OVERROUND}")


def devig_multiplicative(prices: Sequence[int | float | str | Decimal]) -> list[Decimal]:
    raw = implied(prices)
    total = sum(raw, Decimal(0))
    return [r / total for r in raw]


def devig_additive(prices: Sequence[int | float | str | Decimal]) -> list[Decimal]:
    raw = implied(prices)
    excess = sum(raw, Decimal(0)) - Decimal(1)
    count = Decimal(len(raw))
    shifted = [r - excess / count for r in raw]
    if min(shifted) <= 0:
        return devig_multiplicative(prices)
    total = sum(shifted, Decimal(0))
    return [x / total for x in shifted]


def devig_power(
    prices: Sequence[int | float | str | Decimal],
    max_iterations: int = 80,
) -> list[Decimal]:
    raw = implied(prices)
    low = Decimal("0.01")
    high = Decimal("20")
    for _ in range(max_iterations):
        k = (low + high) / 2
        total = sum(x ** (Decimal(1) / k) for x in raw)
        if total > 1:
            high = k
        else:
            low = k
    k = (low + high) / 2
    powered = [x ** (Decimal(1) / k) for x in raw]
    total = sum(powered, Decimal(0))
    return [p / total for p in powered]


def _shin_curve(raw: list[Decimal], z: Decimal) -> list[Decimal]:
    one_minus = Decimal(1) - z
    return [
        ((z * z + 4 * one_minus * r * r).sqrt() - z) / (2 * one_minus)
        for r in raw
    ]


def devig_shin(
    prices: Sequence[int | float | str | Decimal],
    max_iterations: int = 300,
) -> list[Decimal]:
    raw = implied(prices)
    if sum(raw, Decimal(0)) == Decimal(1):
        return list(raw)
    low = Decimal("0")
    high = Decimal(1) - Decimal("1e-12")
    for _ in range(max_iterations):
        z = (low + high) / 2
        total = sum(_shin_curve(raw, z), Decimal(0))
        if total > 1:
            low = z
        else:
            high = z
        if high - low < Decimal("1e-30"):
            break
    z = (low + high) / 2
    return _shin_curve(raw, z)


_DISPATCH = {
    MULTIPLICATIVE: devig_multiplicative,
    POWER: devig_power,
    ADDITIVE: devig_additive,
    SHIN: devig_shin,
}


def fair(
    prices: Sequence[int | float | str | Decimal],
    method: str = MULTIPLICATIVE,
    kind: str | None = None,
) -> list[Decimal]:
    if method not in _DISPATCH:
        raise MarketError(f"unknown devig method {method!r}; expected one of {METHODS}")
    if kind is not None:
        check_market(prices, kind)
    return _DISPATCH[method](prices)


@dataclass(frozen=True)
class MarginReport:
    kind: str
    method: str
    prices: tuple[Decimal, ...]
    fair: tuple[Decimal, ...]
    overround: Decimal
    margin_by_outcome: tuple[Decimal, ...]
    favourite_longshot: Decimal | None

    @property
    def uniform_margin(self) -> bool:
        return len({m for m in self.margin_by_outcome}) == 1

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "method": self.method,
            "prices": [str(p) for p in self.prices],
            "fair": [str(p) for p in self.fair],
            "overround": str(self.overround),
            "margin_by_outcome": [str(m) for m in self.margin_by_outcome],
            "uniform_margin": self.uniform_margin,
            "favourite_longshot": str(self.favourite_longshot) if self.favourite_longshot is not None else None,
        }


def margin_report(
    prices: Sequence[int | float | str | Decimal],
    kind: str,
    method: str = MULTIPLICATIVE,
) -> MarginReport:
    check_market(prices, kind)
    checked = [check_odds(p) for p in prices]
    probabilities = fair(checked, method, kind)
    book = overround(checked)
    per_outcome = tuple((Decimal(1) / p) - f for p, f in zip(checked, probabilities))
    ordered = sorted(range(len(checked)), key=lambda i: probabilities[i])
    fl_bias = None
    if len(checked) > 2:
        fl_bias = per_outcome[ordered[-1]] - per_outcome[ordered[0]]
    return MarginReport(
        kind=kind,
        method=method,
        prices=tuple(checked),
        fair=tuple(probabilities),
        overround=book,
        margin_by_outcome=per_outcome,
        favourite_longshot=fl_bias,
    )
