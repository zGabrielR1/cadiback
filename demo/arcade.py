"""In-house arcade originals: crash, plinko and mines.

Stdlib only, same draw discipline as the slots and roulette — every round
derives from ``SHA256(game_id:round_id)``, so each result is repeatable and
auditable from the round ledger. Settlement goes through
``Books.place_bet`` + ``Books.settle_casino`` (exact minor-unit payouts,
including partial returns below the stake), never through the odds-based
path, which cannot express them.

- crash: the multiplier curve busts at C; C = 1.00 with probability 3%
  (instant bust), else floor(0.97 / (1 - u) * 100) / 100. Two ways to
  play, one draw:
  * target: the player names a cash-out target T (the `selection`,
    e.g. "2.00"); a win pays exactly stake * T.
  * live: the player watches the curve climb (exp(growth * t)) and cashes
    out at any instant; a win pays stake * the multiplier then. The bust
    is still drawn up front from the same C, so cashing at a fixed
    multiplier m wins with probability P(C >= m), the same curve.
  Theoretical RTP is 97% in both modes.
- dice: one draw trimmed to a 0.01 grid (0.00..99.99); the player picks
  under/over a target T in [1.00, 99.00] (the `selection`, e.g.
  "under:50.00"). A win pays ``0.97 / P(win)``, which can fall below the
  stake on a high-probability bet. RTP 97% on every selection.
- plinko: a 12-row board; the 12 ball moves come from 12 bits of the
  digest (1 = right). Slot multipliers are symmetric; exact RTP 97.16%.
- mines: a 5x5 field with m mines drawn by a digest-seeded shuffle. The
  player names m and up to 25-m cells (`selection`, e.g.
  "m=3:cells=1,7,25"). Any mined pick loses; a clean sheet pays
  floor(stake * 0.97 * C(25,k) / C(25-m,k)). Theoretical RTP is 97%
  minus flooring dust (under one centavo).
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from fractions import Fraction

CRASH_GAME_ID = "demo:crash-nitro"
PLINKO_GAME_ID = "demo:plinko-drops"
MINES_GAME_ID = "demo:minas"
DICE_GAME_ID = "demo:dados"

ARCADE_GAME_IDS: frozenset[str] = frozenset({
    CRASH_GAME_ID, PLINKO_GAME_ID, MINES_GAME_ID, DICE_GAME_ID,
})

HOUSE_EDGE = Fraction(3, 100)
HOUSE_KEEP = Fraction(97, 100)  # 1 - edge


def draw_digest(game_id: str, round_id: str) -> bytes:
    if not game_id or not round_id:
        raise ValueError("game_id and round_id are required")
    return hashlib.sha256(f"{game_id}:{round_id}".encode("utf-8")).digest()


def draw_unit(game_id: str, round_id: str) -> float:
    return (int.from_bytes(draw_digest(game_id, round_id)[:8], "big")
            % 100000) / 100000.0


@dataclass(frozen=True)
class ArcadeResult:
    game_id: str
    round_id: str
    unit: float      # the draw, for audit
    tier: str        # human outcome label
    multiplier: str  # display multiplier, "0" on a loss
    symbols: tuple[str, ...]
    payout_minor: int  # exact gross return for the staked amount
    is_win: bool


# --- crash ---------------------------------------------------------------

CRASH_BUST_PROBABILITY = 0.03
CRASH_MIN_TARGET = 1.01
CRASH_MAX_TARGET = 1000.0


def crash_point_from_unit(unit: float) -> float:
    """The bust multiplier for a draw in [0, 1)."""
    if unit < CRASH_BUST_PROBABILITY:
        return 1.00
    point = math.floor(0.97 / (1.0 - unit) * 100.0) / 100.0
    return max(1.01, point)


def parse_crash_target(selection: str | None) -> float:
    raw = str(selection or "").strip().lower().rstrip("x").strip()
    try:
        target = float(raw.replace(",", "."))
    except ValueError:
        raise ValueError("defina o cash-out: multiplicador de 1.01x a 1000x "
                         "(ex.: 2.00)")
    if not (CRASH_MIN_TARGET <= target <= CRASH_MAX_TARGET):
        raise ValueError("defina o cash-out: multiplicador de 1.01x a 1000x "
                         "(ex.: 2.00)")
    return target


def crash_round(game_id: str, round_id: str, selection: str | None,
                stake_minor: int) -> ArcadeResult:
    target = parse_crash_target(selection)
    unit = draw_unit(game_id, round_id)
    point = crash_point_from_unit(unit)
    won = point >= target
    payout = int(round(stake_minor * target)) if won else 0
    tier = f"cashout {target:.2f}x" if won else f"crash {point:.2f}x"
    return ArcadeResult(
        game_id=game_id, round_id=round_id, unit=unit, tier=tier,
        multiplier=f"{target:.2f}" if won else "0",
        symbols=(f"{point:.2f}x", f"alvo {target:.2f}x"),
        payout_minor=payout, is_win=won)


def crash_rtp(target: float = 2.0) -> float:
    """Exact RTP for a target over the 100000-value draw grid."""
    wins = sum(1 for n in range(100000)
               if crash_point_from_unit(n / 100000.0) >= target)
    return wins / 100000.0 * target


# --- crash: live (manual cash-out) ---------------------------------------

# The live curve: the multiplier rises with elapsed seconds as
# ``exp(CRASH_GROWTH_PER_SEC * t)`` (1.00x at t=0, ~2.7x after 2s, ~7.4x
# after 4s) and busts when it reaches the secret point. Because the bust
# is still drawn from ``crash_point_from_unit``, cashing out at a fixed
# multiplier m wins with probability P(bust >= m) and pays m, so the RTP
# is the same 97% as the target mode for every stopping rule.
CRASH_GROWTH_PER_SEC = 0.5
CRASH_LIVE_MAX = 1000.0


def crash_multiplier_at(elapsed_s: float) -> float:
    """The curve's multiplier `elapsed_s` seconds into a live round."""
    return math.exp(CRASH_GROWTH_PER_SEC * max(0.0, elapsed_s))


def crash_elapsed_for(multiplier: float) -> float:
    """Seconds until the curve reaches `multiplier` (0 for <= 1.00x)."""
    if multiplier <= 1.0:
        return 0.0
    return math.log(multiplier) / CRASH_GROWTH_PER_SEC


def crash_bust_multiplier(game_id: str, round_id: str) -> float:
    """The secret bust point for a live round, from the same draw."""
    return crash_point_from_unit(draw_unit(game_id, round_id))


def crash_live_round(game_id: str, round_id: str, elapsed_s: float,
                     stake_minor: int) -> ArcadeResult:
    """Settle a live crash round the player was flying when it ended.

    If the curve had already reached the bust at `elapsed_s`, the round
    busts (a loss) no matter when the click arrived; otherwise it pays
    ``stake * multiplier(elapsed_s)``, capped at CRASH_LIVE_MAX.
    """
    unit = draw_unit(game_id, round_id)
    point = crash_point_from_unit(unit)
    # the curve reaches the bust exactly at crash_elapsed_for(point); a
    # click at or before that instant is a win (point >= multiplier),
    # matching the target mode's ``point >= target``
    if elapsed_s > crash_elapsed_for(point):
        busted = ArcadeResult(
            game_id=game_id, round_id=round_id, unit=unit,
            tier=f"crash {point:.2f}x", multiplier="0",
            symbols=(f"{point:.2f}x", "sem saque"),
            payout_minor=0, is_win=False)
        return busted
    m = min(crash_multiplier_at(elapsed_s), CRASH_LIVE_MAX)
    won = ArcadeResult(
        game_id=game_id, round_id=round_id, unit=unit,
        tier=f"cashout {m:.2f}x", multiplier=f"{m:.2f}",
        symbols=(f"{point:.2f}x", f"saque {m:.2f}x"),
        payout_minor=int(round(stake_minor * m)), is_win=True)
    return won


def crash_live_rtp(cashout_multiplier: float) -> float:
    """Exact RTP when always cashing out at a fixed multiplier: the same
    97% as the target mode, since a win needs ``bust >= multiplier``."""
    wins = sum(1 for n in range(100000)
               if crash_point_from_unit(n / 100000.0) >= cashout_multiplier)
    return wins / 100000.0 * cashout_multiplier


# --- dice -----------------------------------------------------------------

DICE_MIN_TARGET = 1.0
DICE_MAX_TARGET = 99.0
DICE_ROLL_GRID = 10000  # rolls live on a 0.01 grid: 0.00 .. 99.99


def parse_dice_selection(selection: str | None) -> tuple[str, float]:
    """`selection` is "under:<T>" or "over:<T>", T in [1.00, 99.00]."""
    raw = str(selection or "").strip().lower().replace(" ", "")
    direction, _, value = raw.partition(":")
    if direction not in ("under", "over"):
        raise ValueError('escolha under/over: ex. "under:50.00"')
    try:
        target = round(float(value.replace(",", ".")), 2)
    except ValueError:
        raise ValueError('escolha under/over: ex. "under:50.00"')
    if not (DICE_MIN_TARGET <= target <= DICE_MAX_TARGET):
        raise ValueError("alvo de 1.00 a 99.00 (ex.: under:50.00)")
    return direction, target


def dice_hundredths(target: float) -> int:
    return int(round(target * 100))


def dice_win_chance(direction: str, target: float) -> float:
    """Fraction of the 10000-roll grid that wins for this selection."""
    h = dice_hundredths(target)
    wins = h if direction == "under" else DICE_ROLL_GRID - h - 1
    return wins / DICE_ROLL_GRID


def dice_multiplier(direction: str, target: float) -> float:
    """Gross return per unit staked on a win: 0.97 / P(win)."""
    return float(HOUSE_KEEP) / dice_win_chance(direction, target)


def dice_roll(game_id: str, round_id: str) -> float:
    """The roll for a draw, on the 0.01 grid (0.00 .. 99.99)."""
    return int(draw_unit(game_id, round_id) * DICE_ROLL_GRID) / 100.0


def dice_round(game_id: str, round_id: str, selection: str | None,
               stake_minor: int) -> ArcadeResult:
    direction, target = parse_dice_selection(selection)
    unit = draw_unit(game_id, round_id)
    roll = int(unit * DICE_ROLL_GRID) / 100.0
    won = roll < target if direction == "under" else roll > target
    tier = f"{direction} {target:.2f} · rolou {roll:.2f}"
    if won:
        mult = dice_multiplier(direction, target)
        payout = int(round(stake_minor * mult))
        return ArcadeResult(
            game_id=game_id, round_id=round_id, unit=unit, tier=tier,
            multiplier=f"{mult:.2f}",
            symbols=(f"{roll:.2f}", direction, f"alvo {target:.2f}"),
            payout_minor=payout, is_win=True)
    return ArcadeResult(
        game_id=game_id, round_id=round_id, unit=unit, tier=tier,
        multiplier="0",
        symbols=(f"{roll:.2f}", direction, f"alvo {target:.2f}"),
        payout_minor=0, is_win=False)


def dice_rtp(direction: str, target: float) -> float:
    """Exact RTP for a fixed selection over the 10000-roll grid."""
    stake = 100
    payout = int(round(stake * dice_multiplier(direction, target)))
    wins = int(round(dice_win_chance(direction, target) * DICE_ROLL_GRID))
    return wins * payout / (DICE_ROLL_GRID * stake)


# --- plinko ---------------------------------------------------------------

PLINKO_ROWS = 12
# Symmetric slot multipliers, index = number of right moves (0..12).
PLINKO_MULTIPLIERS: tuple[float, ...] = (
    130.0, 24.0, 8.1, 2.0, 0.7, 0.2, 0.2, 0.2,
    0.7, 2.0, 8.1, 24.0, 130.0,
)


def plinko_theoretical_rtp() -> float:
    total = Fraction(0)
    for k, mult in enumerate(PLINKO_MULTIPLIERS):
        prob = Fraction(math.comb(PLINKO_ROWS, k), 2 ** PLINKO_ROWS)
        total += prob * Fraction(str(mult))
    return float(total)


def plinko_path(game_id: str, round_id: str) -> tuple[int, ...]:
    """12 moves from digest bits: 1 = right, 0 = left."""
    digest = draw_digest(game_id, round_id)
    bits: list[int] = []
    for byte in digest:
        for shift in range(8):
            bits.append((byte >> shift) & 1)
            if len(bits) == PLINKO_ROWS:
                return tuple(bits)
    raise AssertionError("unreachable")


def plinko_round(game_id: str, round_id: str, stake_minor: int) -> ArcadeResult:
    unit = draw_unit(game_id, round_id)
    path = plinko_path(game_id, round_id)
    slot = sum(path)
    mult = PLINKO_MULTIPLIERS[slot]
    payout = int(round(stake_minor * mult))
    won = payout > 0
    tier = f"slot {mult:g}x"
    return ArcadeResult(
        game_id=game_id, round_id=round_id, unit=unit, tier=tier,
        multiplier=f"{mult:g}",
        symbols=("".join("R" if b else "L" for b in path), f"slot {slot}"),
        payout_minor=payout, is_win=won)


# --- mines ----------------------------------------------------------------

MINES_CELLS = 25
MINES_SIDE = 5


def parse_mines_selection(selection: str | None) -> tuple[int, tuple[int, ...]]:
    """`selection` is "m=<mines>:cells=<c1,c2,...>", cells 1..25."""
    raw = str(selection or "").strip().lower().replace(" ", "")
    try:
        head, _, tail = raw.partition(":")
        if not head.startswith("m=") or not tail.startswith("cells="):
            raise ValueError("bad shape")
        mines = int(head[2:])
        cells = tuple(int(c) for c in tail[len("cells="):].split(",") if c)
    except (ValueError, AttributeError):
        raise ValueError("escolha as minas e as casas: ex. m=3:cells=1,7,25")
    if not 1 <= mines <= MINES_CELLS - 1:
        raise ValueError("minas: de 1 a 24")
    if not cells or len(set(cells)) != len(cells):
        raise ValueError("escolha casas distintas de 1 a 25")
    if any(c < 1 or c > MINES_CELLS for c in cells):
        raise ValueError("escolha casas distintas de 1 a 25")
    if len(cells) > MINES_CELLS - mines:
        raise ValueError(f"com {mines} minas só há {MINES_CELLS - mines} "
                         "casas seguras")
    return mines, cells


def mines_field(game_id: str, round_id: str, mines: int) -> tuple[int, ...]:
    """The mined cells (1-based), from a digest-seeded shuffle."""
    seed = int.from_bytes(draw_digest(game_id, round_id)[:8], "big")
    deck = list(range(1, MINES_CELLS + 1))
    random.Random(seed).shuffle(deck)
    return tuple(sorted(deck[:mines]))


def mines_fair_multiplier(mines: int, picks: int) -> Fraction:
    """0.97 * C(25,k) / C(25-m,k): the survival odds minus the edge."""
    return (HOUSE_KEEP * Fraction(math.comb(MINES_CELLS, picks),
                                  math.comb(MINES_CELLS - mines, picks)))


def mines_round(game_id: str, round_id: str, selection: str | None,
                stake_minor: int) -> ArcadeResult:
    mines, cells = parse_mines_selection(selection)
    unit = draw_unit(game_id, round_id)
    field = mines_field(game_id, round_id, mines)
    mined = set(field)
    hit = next((c for c in cells if c in mined), None)
    if hit is None:
        mult = mines_fair_multiplier(mines, len(cells))
        payout = (stake_minor * mult.numerator) // mult.denominator
        tier = f"limpo {len(cells)} casas"
        symbols = (f"m={mines}", "minas:" + ",".join(map(str, field)),
                   "picks:" + ",".join(map(str, cells)))
        display = f"{float(mult):.2f}"
        won = True
    else:
        payout = 0
        tier = f"mina na casa {hit}"
        symbols = (f"m={mines}", "minas:" + ",".join(map(str, field)),
                   "picks:" + ",".join(map(str, cells)))
        display = "0"
        won = False
    return ArcadeResult(
        game_id=game_id, round_id=round_id, unit=unit, tier=tier,
        multiplier=display, symbols=symbols,
        payout_minor=int(payout), is_win=won)


def arcade_round(game_id: str, round_id: str, selection: str | None,
                 stake_minor: int) -> ArcadeResult:
    """Dispatch one arcade round. Plinko needs no selection."""
    if game_id == CRASH_GAME_ID:
        return crash_round(game_id, round_id, selection, stake_minor)
    if game_id == PLINKO_GAME_ID:
        return plinko_round(game_id, round_id, stake_minor)
    if game_id == MINES_GAME_ID:
        return mines_round(game_id, round_id, selection, stake_minor)
    if game_id == DICE_GAME_ID:
        return dice_round(game_id, round_id, selection, stake_minor)
    raise ValueError(f"unknown arcade game: {game_id}")


def theoretical_rtp(game_id: str) -> float:
    if game_id == CRASH_GAME_ID:
        return 0.97
    if game_id == PLINKO_GAME_ID:
        return plinko_theoretical_rtp()
    if game_id == MINES_GAME_ID:
        return float(HOUSE_KEEP)
    if game_id == DICE_GAME_ID:
        return float(HOUSE_KEEP)
    raise ValueError(f"unknown arcade game: {game_id}")
