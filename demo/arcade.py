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
- keno: 20 of 80 numbers drawn from a digest-seeded shuffle; the player
  picks 1..10 spots (`selection`, e.g. "5:3,17,42,58,71") and the hit count
  pays. The ladder doubles per extra hit and is scaled so the expected
  return is exactly 97% for every spot count — derived, not typed. Low tiers
  on a high spot count pay below the stake, which is a partial return and is
  reported as one.
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
KENO_GAME_ID = "demo:keno"

ARCADE_GAME_IDS: frozenset[str] = frozenset({
    CRASH_GAME_ID, PLINKO_GAME_ID, MINES_GAME_ID, DICE_GAME_ID, KENO_GAME_ID,
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


# --- keno -----------------------------------------------------------------

# 80 numbers, 20 drawn, 1..10 spots picked. The hit count is what pays, and
# the payout ladder is DERIVED, not typed — which is what decision 0034 said
# was the reason not to build this ("a full paytable to get exactly right").
# It no longer is one:
#
#   1. the shape is fixed and simple: every extra hit DOUBLES the payout, so
#      the ladder for a 10-spot is a clean 2x from the bottom tier to the top;
#   2. the hit probabilities are exact — hypergeometric over 80 choose 20;
#   3. the whole ladder is then scaled by a single factor so its expected
#      return is HOUSE_KEEP.
#
# So the RTP is 97.0000% by construction for every spot count, and changing
# the shape cannot silently make the house generous. The ladder is then
# snapped to four decimals so the only dust left is the per-round centavo.
KENO_POOL = 80
KENO_DRAWN = 20
KENO_MIN_SPOTS = 1
KENO_MAX_SPOTS = 10
KENO_STEP = 2  # each additional hit doubles

# Snapping matters more than it looks. Unsnap, the multipliers are ugly
# Fractions (0.69813043...), and flooring one per round costs up to a whole
# centavo on EVERY paying round — 1.5% of the RTP at a R$1 stake, far too
# much dust to still call the model 97%. Snapped, each multiplier is within
# half a ten-thousandth of ideal, the ladder's exact RTP is 97% to six
# decimals, and what remains is the sub-centavo rounding of one payout.
KENO_SCALE = 10000
KENO_SETTLE_PASSES = 8

def _snap(value: Fraction) -> Fraction:
    """Round a multiplier to four decimals, exactly."""
    return Fraction(round(value * KENO_SCALE), KENO_SCALE)


def keno_hit_probability(spots: int, hits: int) -> Fraction:
    """P(exactly `hits` of `spots` picked numbers are drawn), exactly.

    Hypergeometric: C(spots, hits) * C(80 - spots, 20 - hits) / C(80, 20).
    """
    if not 0 <= hits <= spots:
        raise ValueError("hits must be between 0 and the spots played")
    if not KENO_MIN_SPOTS <= spots <= KENO_MAX_SPOTS:
        raise ValueError(f"spots must be {KENO_MIN_SPOTS}..{KENO_MAX_SPOTS}")
    missed = KENO_DRAWN - hits
    unseen = KENO_POOL - spots
    if not 0 <= missed <= unseen:
        return Fraction(0)  # more drawn numbers than there are unpicked ones
    return Fraction(math.comb(spots, hits) * math.comb(unseen, missed),
                    math.comb(KENO_POOL, KENO_DRAWN))


def keno_paytable(spots: int) -> dict[int, Fraction]:
    """hits -> gross return per unit staked, scaled so the RTP is HOUSE_KEEP.

    Zero hits never pays: with 20 of 80 drawn it is the common case, and a
    tier that paid would have to pay almost nothing per hit while still
    counting as a win.

    The normalisation is re-applied a few times because each pass snaps the
    multipliers and snapping moves the total; it settles immediately in
    practice, and the passes are bounded so a pathological input cannot spin.
    """
    tiers = list(range(1, spots + 1))
    probs = {k: keno_hit_probability(spots, k) for k in tiers}
    ladder = {k: _snap(HOUSE_KEEP * Fraction(KENO_STEP) ** (k - 1)) for k in tiers}
    for _ in range(KENO_SETTLE_PASSES):
        total = sum(probs[k] * ladder[k] for k in tiers)
        if not total:
            return {}
        ladder = {k: _snap(ladder[k] / total * HOUSE_KEEP) for k in tiers}
    return ladder


def keno_multiplier(spots: int, hits: int) -> Fraction:
    """The gross return for one hit count; 0 when the hit count does not pay."""
    return keno_paytable(spots).get(hits, Fraction(0))


def keno_rtp(spots: int) -> float:
    """Exact RTP of the derived ladder — 97% for every spot count."""
    return float(sum(keno_hit_probability(spots, k) * mult
                     for k, mult in keno_paytable(spots).items()))


def keno_realised_rtp(spots: int, stake_minor: int) -> float:
    """What the player actually gets back, after rounding each payout.

    The model is 97% at every spot count, but a payout is whole centavos, so
    a round returns a rounded number and the realised RTP sits just under the
    model: ~96.7% at a R$1 stake, ~97.0% at R$10, converging as the stake
    grows. That is the same dust mines has, and it is reported here rather
    than hidden — the catalog carries the model, this is the truth about one
    stake size.
    """
    ladder = keno_paytable(spots)
    return float(sum(keno_hit_probability(spots, k) * keno_payout(stake_minor, mult)
                     for k, mult in ladder.items()) / stake_minor)


def keno_payout(stake_minor: int, multiplier: Fraction) -> int:
    """The round's gross return in whole centavos, rounded half up.

    Rounding rather than flooring is deliberate and it is not a detail: with
    ten tiers, flooring a fractional multiplier can cost most of a centavo on
    every paying round, which at a R$1 stake is ~0.5% of the RTP — dust
    large enough to make "97%" untrue. Half-up is unbiased, so the losses and
    the gains cancel.
    """
    if not multiplier:
        return 0
    return (2 * stake_minor * multiplier.numerator + multiplier.denominator) \
        // (2 * multiplier.denominator)


def parse_keno_selection(selection: str | None) -> tuple[int, tuple[int, ...]]:
    """`selection` is "<spots>:<n1,n2,...>", numbers 1..80.

    The spot count is written out rather than inferred, so a selection cannot
    mean two different rounds: "5:3,17,42" is five spots, and the same three
    numbers under a different count is a different bet with a different pay
    table, so the two are kept apart.
    """
    raw = str(selection or "").strip().lower().replace(" ", "")
    head, _, tail = raw.partition(":")
    if not tail:
        raise ValueError("escolha quantos números jogar: ex. 5:3,17,42,58,71")
    try:
        spots = int(head)
        picks = tuple(int(c) for c in tail.split(",") if c)
    except ValueError:
        raise ValueError("escolha quantos números jogar: ex. 5:3,17,42,58,71")
    if not KENO_MIN_SPOTS <= spots <= KENO_MAX_SPOTS:
        raise ValueError(f"jogue de {KENO_MIN_SPOTS} a {KENO_MAX_SPOTS} números")
    if len(picks) != spots:
        raise ValueError(f"marque {spots} número(s) — você marcou {len(picks)}")
    if len(set(picks)) != len(picks):
        raise ValueError("escolha números distintos")
    if any(c < 1 or c > KENO_POOL for c in picks):
        raise ValueError(f"escolha números distintos de 1 a {KENO_POOL}")
    return spots, tuple(sorted(picks))


def keno_draw(game_id: str, round_id: str) -> tuple[int, ...]:
    """The 20 drawn numbers (1..80), from a digest-seeded shuffle.

    Same discipline as mines: a seeded shuffle of the whole pool, so the draw
    is uniform, repeatable and auditable from the round ledger alone.
    """
    seed = int.from_bytes(draw_digest(game_id, round_id)[:8], "big")
    deck = list(range(1, KENO_POOL + 1))
    random.Random(seed).shuffle(deck)
    return tuple(sorted(deck[:KENO_DRAWN]))


def keno_round(game_id: str, round_id: str, selection: str | None,
               stake_minor: int) -> ArcadeResult:
    spots, picks = parse_keno_selection(selection)
    unit = draw_unit(game_id, round_id)
    drawn = set(keno_draw(game_id, round_id))
    hit_numbers = tuple(sorted(picked for picked in picks if picked in drawn))
    hits = len(hit_numbers)
    mult = keno_multiplier(spots, hits)
    payout = keno_payout(stake_minor, mult)
    # A sub-stake tier is a partial return, not a win: 1 hit on 10 spots pays
    # 0.22x, and reporting that as a win would be a lie the panel then shows.
    won = payout >= stake_minor and payout > 0
    tier = (f"{hits} de {spots}" if mult else f"{hits} de {spots} · sem prêmio")
    return ArcadeResult(
        game_id=game_id, round_id=round_id, unit=unit, tier=tier,
        multiplier=f"{float(mult):.2f}" if mult else "0",
        symbols=(",".join(map(str, drawn)),
                 ",".join(map(str, hit_numbers)) or "-",
                 f"{hits}/{spots}"),
        payout_minor=int(payout), is_win=won)


def keno_theoretical_rtp(spots: int = 5) -> float:
    """RTP for one spot count; 97% for all of them (see the module note)."""
    return keno_rtp(spots)


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
    if game_id == KENO_GAME_ID:
        return keno_round(game_id, round_id, selection, stake_minor)
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
    if game_id == KENO_GAME_ID:
        return keno_rtp(5)
    raise ValueError(f"unknown arcade game: {game_id}")
