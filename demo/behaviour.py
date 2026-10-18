"""Per-player outcome control — the painel's win/loss dial, made real.

The owner can force one account to win, force it to lose, or give it a win
rate, then watch how the player reacts. Every settlement the *operator* decides
reads this dial: the in-house originals (slots, roulette, arcade, wheel). A
publisher round is decided by the publisher, so there the dial scales the
payout **we post** instead, and the round is marked (see ``server.py``).

The dial never fabricates a game outcome. A forced win picks a *real* winning
draw from the game's own paytable (a fresh seed); a forced loss picks a real
losing one. A bias that cannot find a matching draw within ``SEARCH_CAP``
attempts falls back to the unbias draw and reports ``applied=False``, so the
painel never claims a win it did not deliver.

Modes::

    normal        no bias (the draw stands)
    always_win    every round returns more than the stake
    always_lose   every round returns less than the stake
    win_rate      a deterministic share of rounds win, ``win_rate_percent``
"""

from __future__ import annotations

import hashlib

MODES: tuple[str, ...] = ("normal", "always_win", "always_lose", "win_rate")
DEFAULT_MODE = "normal"
# Attempts (each a sha256 draw) before a bias gives up and reports itself
# unapplied. 8192 draws is a few milliseconds and covers a 1-in-10000 paytable.
SEARCH_CAP = 8192


def normalize_mode(value: object) -> str:
    mode = str(value or DEFAULT_MODE).strip().lower()
    return mode if mode in MODES else DEFAULT_MODE


def normalize_rate(value: object) -> int:
    """A win-rate percent on the 0..100 integer grid (None -> 100)."""
    if value is None or value == "":
        return 100
    try:
        rate = int(round(float(value)))
    except (TypeError, ValueError):
        return 100
    return max(0, min(100, rate))


def _unit(key: str) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return (int.from_bytes(digest[:8], "big") % 100000) / 100000.0


def outcome_for(key: str, mode: object, rate_percent: object = None):
    """The forced outcome for one round.

    Returns ``True`` to force a win, ``False`` to force a loss, or ``None``
    when the round is unbiased. ``key`` should name the round uniquely (player
    + game + round) so a ``win_rate`` decision is stable and auditable.
    """
    mode = normalize_mode(mode)
    if mode == "always_win":
        return True
    if mode == "always_lose":
        return False
    if mode == "win_rate":
        rate = normalize_rate(rate_percent)
        if rate <= 0:
            return False
        if rate >= 100:
            return True
        return _unit(f"{key}:rate") < (rate / 100.0)
    return None


def _search(draw, round_id: str, ok, cap: int):
    """The first ``round_id`` variant whose payout satisfies ``ok``."""
    if ok(draw(round_id)):
        return round_id, True
    for i in range(1, cap + 1):
        candidate = f"{round_id}-{i}"
        if ok(draw(candidate)):
            return candidate, True
    return None


def coerce(draw, round_id: str, stake: int, want: bool,
           cap: int = SEARCH_CAP) -> tuple[str, bool]:
    """Find a draw that matches the forced outcome.

    ``draw(round_id)`` returns the round's gross payout in minor units for the
    given seed. A win is ``payout > stake``; a loss prefers ``payout == 0`` and
    falls back to ``payout < stake`` for a game that never returns nothing
    (plinko's 0.2x floor). Returns ``(round_id, applied)``.
    """
    if want:
        found = _search(draw, round_id, lambda p: p > stake, cap)
    else:
        found = _search(draw, round_id, lambda p: p == 0, cap)
        if found is None:
            found = _search(draw, round_id, lambda p: p < stake, cap)
    if found is None:
        return round_id, False
    return found


def publisher_win(win: int, stake: int, mode: object,
                  rate_percent: object = None, key: str = "") -> int:
    """Scale a publisher-reported gross win to match the dial.

    The publisher owns its round, so a forced win floors the payout at 2x the
    stake and a forced loss zeroes it; a win rate decides per round.
    """
    want = outcome_for(key, mode, rate_percent)
    if want is None:
        return win
    if want:
        return max(win, stake * 2)
    return 0
