"""Deterministic demo slot engine. Stdlib only. No real money, no real RNG cert.

One payline, six tiers. Wins settle through ``Books.settle_bet_win`` so every
multiplier is >= 1.01 (the wallet's floor); losses settle through
``Books.settle_bet_loss``. Draws are ``SHA256(game_id:round_id)`` — repeatable,
auditable, and boring on purpose.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Tier:
    name: str
    multiplier: str  # decimal odds string for gross_return; "0" means loss
    probability: float
    symbols: tuple[str, str, str]


# The original demo paytable (RTP 95.90%): Neon Gems and Fortune
# Ledger keep it unchanged — every existing round on file was drawn
# against this table.
TIERS: tuple[Tier, ...] = (
    Tier("loss", "0", 0.75, ("7", "BAR", "LEMON")),
    Tier("small", "1.20", 0.12, ("CHERRY", "CHERRY", "CHERRY")),
    Tier("medium", "2.00", 0.08, ("LEMON", "LEMON", "LEMON")),
    Tier("big", "5.00", 0.035, ("BAR", "BAR", "BAR")),
    Tier("epic", "15.00", 0.012, ("DIAMOND", "DIAMOND", "DIAMOND")),
    Tier("jackpot", "100.00", 0.003, ("7", "7", "7")),
)

# Distinct paytables so the lobby's originals are different games,
# not the same reels under different titles. Probabilities sum to 1
# and each RTP is asserted by the demo suite.
CRIMSON_TIERS: tuple[Tier, ...] = (
    Tier("loss", "0", 0.7515, ("DRAGON", "RUBY", "COIN")),
    Tier("small", "1.25", 0.13, ("RUBY", "RUBY", "RUBY")),
    Tier("medium", "2.20", 0.07, ("COIN", "COIN", "COIN")),
    Tier("big", "6.00", 0.035, ("DRAGON", "DRAGON", "DRAGON")),
    Tier("epic", "18.00", 0.011, ("GEM", "GEM", "GEM")),
    Tier("jackpot", "90.00", 0.0025, ("7", "7", "7")),
)

GOLD_TIERS: tuple[Tier, ...] = (
    Tier("loss", "0", 0.722, ("VAULT", "KEY", "BAR")),
    Tier("small", "1.20", 0.15, ("KEY", "KEY", "KEY")),
    Tier("medium", "2.20", 0.08, ("BAR", "BAR", "BAR")),
    Tier("big", "6.00", 0.035, ("VAULT", "VAULT", "VAULT")),
    Tier("epic", "20.00", 0.011, ("CROWN", "CROWN", "CROWN")),
    Tier("jackpot", "90.00", 0.002, ("7", "7", "7")),
)

# game_id -> paytable. Unlisted ids fall back to the original table.
PAYTABLES: dict[str, tuple[Tier, ...]] = {
    "demo:neon-gems": TIERS,
    "demo:fortune-ledger": TIERS,
    "demo:crimson-dragons": CRIMSON_TIERS,
    "demo:gold-vault": GOLD_TIERS,
}


def tiers_for(game_id: str) -> tuple[Tier, ...]:
    return PAYTABLES.get(game_id, TIERS)


def rtp_of(game_id: str) -> float:
    return sum(t.probability * float(t.multiplier)
               for t in tiers_for(game_id))


DEMO_RTP = sum(t.probability * float(t.multiplier) for t in TIERS)
DEMO_RTP_STR = f"{DEMO_RTP * 100:.2f}"


@dataclass(frozen=True)
class SpinResult:
    game_id: str
    round_id: str
    unit: float  # draw in [0, 1)
    tier: str
    multiplier: str
    symbols: tuple[str, str, str]
    is_win: bool


def draw_unit(game_id: str, round_id: str) -> float:
    if not game_id or not round_id:
        raise ValueError("game_id and round_id are required")
    digest = hashlib.sha256(f"{game_id}:{round_id}".encode("utf-8")).hexdigest()
    return (int(digest, 16) % 100000) / 100000.0


def spin(game_id: str, round_id: str) -> SpinResult:
    tiers = tiers_for(game_id)
    cumulative = tuple(
        sum(t.probability for t in tiers[: i + 1])
        for i in range(len(tiers))
    )
    unit = draw_unit(game_id, round_id)
    for tier, edge in zip(tiers, cumulative):
        if unit < edge:
            return SpinResult(
                game_id=game_id,
                round_id=round_id,
                unit=unit,
                tier=tier.name,
                multiplier=tier.multiplier,
                symbols=tier.symbols,
                is_win=tier.multiplier != "0",
            )
    last = tiers[-1]
    return SpinResult(game_id, round_id, unit, last.name, last.multiplier, last.symbols, True)


def theoretical_rtp() -> float:
    return DEMO_RTP
