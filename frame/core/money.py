from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

CENTS = 100
MIN_ACCEPTABLE_ODDS = Decimal("1.01")
MAX_ACCEPTABLE_ODDS = Decimal("1000")


class MoneyError(ValueError):
    pass


def to_cents(value: int | float | str | Decimal) -> int:
    if isinstance(value, bool):
        raise MoneyError("bool is not money")
    if isinstance(value, int):
        return value * CENTS
    if isinstance(value, float):
        dec = Decimal(repr(value))
    else:
        dec = Decimal(str(value))
    if dec != dec or dec.is_infinite():
        raise MoneyError(f"non-finite amount: {value!r}")
    return int(dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * CENTS)


def to_real(cents: int) -> Decimal:
    if not isinstance(cents, int) or isinstance(cents, bool):
        raise MoneyError(f"minor units must be int, got {type(cents).__name__}")
    return (Decimal(cents) / CENTS).quantize(Decimal("0.01"))


def allocate(total: int, weights: Sequence[int | float | str | Decimal]) -> list[int]:
    if not isinstance(total, int) or isinstance(total, bool):
        raise MoneyError(f"total must be int minor units, got {type(total).__name__}")
    if total < 0:
        raise MoneyError(f"cannot allocate negative total: {total}")
    if not weights:
        raise MoneyError("allocate needs at least one weight")
    dec_weights = [Decimal(str(w)) for w in weights]
    if any(w < 0 for w in dec_weights):
        raise MoneyError("weights must be non-negative")
    weight_sum = sum(dec_weights)
    count = len(dec_weights)
    if weight_sum == 0:
        base = total // count
        parts = [base] * count
        for index in range(total - base * count):
            parts[index] += 1
        return parts
    numerators = [Decimal(total) * w for w in dec_weights]
    floors = [int(n // weight_sum) for n in numerators]
    remainder = total - sum(floors)
    order = sorted(range(count), key=lambda i: (-(numerators[i] - floors[i] * weight_sum), i))
    parts = list(floors)
    for step in range(remainder):
        parts[order[step]] += 1
    return parts


def check_odds(decimal_odds: int | float | str | Decimal) -> Decimal:
    odds = Decimal(str(decimal_odds))
    if not odds.is_finite():
        raise MoneyError(f"non-finite odds: {decimal_odds!r}")
    if odds < MIN_ACCEPTABLE_ODDS or odds > MAX_ACCEPTABLE_ODDS:
        raise MoneyError(f"odds {odds} outside [{MIN_ACCEPTABLE_ODDS},{MAX_ACCEPTABLE_ODDS}]")
    return odds


def gross_return(stake: int, decimal_odds: int | float | str | Decimal) -> int:
    if not isinstance(stake, int) or isinstance(stake, bool):
        raise MoneyError("stake must be int minor units")
    if stake < 0:
        raise MoneyError("stake must be non-negative")
    odds = check_odds(decimal_odds)
    exact = (Decimal(stake) * odds).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(exact)


def net_profit(stake: int, decimal_odds: int | float | str | Decimal) -> int:
    return gross_return(stake, decimal_odds) - stake
