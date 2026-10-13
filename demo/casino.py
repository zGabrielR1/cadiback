"""In-house table game: European single-zero roulette.

One deterministic engine, stdlib only. The ball lands on a pocket
derived from ``SHA256(game_id:round_id)`` — the same draw discipline
as the demo slots, so every round is repeatable and auditable from
the round ledger.

Payouts are the real European ones: straight-up 35:1 (gross return
36x), every even-money and dozen-style bet 1:1 (gross return 2x).
Zero is neither red nor black, neither even nor odd, neither low nor
high: it loses every bet except a straight-up 0, which is what makes
the house edge 1/37 (RTP 36/37 = 97.297%) on every market.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

ROULETTE_GAME_ID = "demo:roulette-europeia"

# European wheel: 0 plus 1..36.
POCKETS: tuple[int, ...] = (0,) + tuple(range(1, 37))

# Red pockets on a European wheel (the rest of 1..36 are black).
RED: frozenset[int] = frozenset({
    1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27,
    30, 32, 34, 36,
})

# Even-money style bets, gross-return multiplier 2.00.
EVEN_MONEY: dict[str, frozenset[int]] = {
    "red": RED,
    "black": frozenset(POCKETS[1:]) - RED,
    "even": frozenset(n for n in POCKETS[1:] if n % 2 == 0),
    "odd": frozenset(n for n in POCKETS[1:] if n % 2 == 1),
    "low": frozenset(range(1, 19)),
    "high": frozenset(range(19, 37)),
}

STRAIGHT_MULTIPLIER = "36.00"   # 35:1 odds, stake returned on top
EVEN_MONEY_MULTIPLIER = "2.00"  # 1:1 odds

RTP = 36.0 / 37.0  # 97.297% on every market

VALID_SELECTIONS: frozenset[str] = frozenset(
    {str(n) for n in POCKETS} | set(EVEN_MONEY)
)


@dataclass(frozen=True)
class RouletteResult:
    game_id: str
    round_id: str
    unit: float      # draw in [0, 1), for audit
    ball: int        # winning pocket 0..36
    selection: str
    tier: str        # "straight" | "even-money" | "loss"
    multiplier: str  # decimal odds string for gross_return
    symbols: tuple[str, str, str]
    is_win: bool


def draw_unit(game_id: str, round_id: str) -> float:
    if not game_id or not round_id:
        raise ValueError("game_id and round_id are required")
    digest = hashlib.sha256(f"{game_id}:{round_id}".encode("utf-8")).hexdigest()
    return (int(digest, 16) % 100000) / 100000.0


def ball_from_unit(unit: float) -> int:
    """Map the draw onto the 37 pockets, uniformly."""
    return int(unit * len(POCKETS)) % len(POCKETS)


def _pocket_name(ball: int) -> str:
    if ball == 0:
        return "verde"
    return "vermelho" if ball in RED else "preto"


def _parity_name(ball: int) -> str:
    if ball == 0:
        return "nem par nem ímpar"
    return "par" if ball % 2 == 0 else "ímpar"


def validate_selection(selection: str | None) -> str:
    """A table game needs a selection: no selection, no bet."""
    raw = str(selection or "").strip().lower()
    if raw not in VALID_SELECTIONS:
        raise ValueError(
            "seleção obrigatória: número 0-36, vermelho, preto, "
            "par, ímpar, baixo (1-18) ou alto (19-36)")
    return raw


def roulette_spin(game_id: str, round_id: str,
                  selection: str | None) -> RouletteResult:
    unit = draw_unit(game_id, round_id)
    ball = ball_from_unit(unit)
    pick = validate_selection(selection)
    if pick == str(ball):
        tier, multiplier = "straight", STRAIGHT_MULTIPLIER
    elif ball in EVEN_MONEY.get(pick, frozenset()):
        tier, multiplier = "even-money", EVEN_MONEY_MULTIPLIER
    else:
        tier, multiplier = "loss", "0"
    return RouletteResult(
        game_id=game_id,
        round_id=round_id,
        unit=unit,
        ball=ball,
        selection=pick,
        tier=tier,
        multiplier=multiplier,
        symbols=(str(ball), _pocket_name(ball), _parity_name(ball)),
        is_win=tier != "loss",
    )


def theoretical_rtp() -> float:
    return RTP
