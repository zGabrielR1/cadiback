"""Settling a posted sports slip against the fixture's real final score.

The board prices markets from our own model and the feed supplies the facts
(final status + the two scores), so a bet's outcome has one authoritative
answer — what actually happened — not a hash roll. `resolve` maps one market
kind + selection onto that answer and returns

    "won"    the stake pays stake × price
    "lost"   the stake goes to the house
    "push"   refund at odds 1.00 (full-game lines live on the .5 grid, so
             this answers only the defensive tie case of a two-way market)
    None     the result does not *determine* the market (match not final, a
             half market the full score cannot decide) — stay pending

Half markets are settled honestly on what a final score proves: a half's
total is an integer and the other half owns the remainder, so `Mais 25.0` on
the first half is decisively lost once the FULL total is ≤ 25 (each half tops
out at the full total) — while the covering direction can stay undetermined,
and an undetermined result means *pending*, never an invented verdict.
"""

from __future__ import annotations

_HOME = {"casa", "home", "1"}
_DRAW = {"empate", "draw", "x", "n"}
_AWAY = {"fora", "away", "2", "visitante"}
_OVER = {"mais", "over", "cima", "+"}
_UNDER = {"menos", "under", "baixo", "-"}


def _norm(text: object) -> str:
    return str(text or "").strip().casefold()


def _fragment(kind: object) -> str:
    """`full`, `h1` or `h2` for the total kinds — empty for every other kind."""
    text = _norm(kind)
    if text != "total" and not text.startswith("total-"):
        return ""
    tail = text.split("-", 1)[1] if "-" in text else "full"
    return tail if tail in ("full", "h1", "h2") else ""


def resolve(kind: object, selection: object, home: object, away: object,
            home_score: object, away_score: object,
            line: object = None) -> str | None:
    """The verdict for one market against one real final score."""
    pick = _norm(selection)
    if not pick:
        return None
    try:
        hs, as_ = int(home_score), int(away_score)
    except (TypeError, ValueError):
        return None
    side, other = _norm(home), _norm(away)

    text = _norm(kind)
    if text == "1x2":
        if pick in _HOME or pick == side:
            return "won" if hs > as_ else "lost"
        if pick in _DRAW:
            return "won" if hs == as_ else "lost"
        if pick in _AWAY or pick == other:
            return "won" if as_ > hs else "lost"
        return None
    if text == "moneyline":
        if pick in _HOME or pick == side:
            return "push" if hs == as_ else ("won" if hs > as_ else "lost")
        if pick in _AWAY or pick == other:
            return "push" if hs == as_ else ("won" if as_ > hs else "lost")
        return None
    if text == "dc":
        if pick == "1x":
            return "won" if hs >= as_ else "lost"
        if pick == "x2":
            return "won" if as_ >= hs else "lost"
        if pick == "12":
            return "won" if hs != as_ else "lost"
        return None
    if text == "btts":
        both = hs > 0 and as_ > 0
        if pick in ("sim", "yes"):
            return "won" if both else "lost"
        if pick in ("não", "nao", "no"):
            return "lost" if both else "won"
        return None

    fragment = _fragment(kind)
    if not fragment:
        return None
    try:
        bound = float(line)
    except (TypeError, ValueError):
        return None
    total = hs + as_
    over = pick in _OVER
    if not over and pick not in _UNDER:
        return None
    if fragment == "full":
        if total > bound:
            return "won" if over else "lost"
        if total < bound:
            return "lost" if over else "won"
        return "push"
    # a half fragment: the full total is the upper bound of either half
    if over:
        return "lost" if total <= bound else None
    limit = int(bound) - 1 if bound == int(bound) else int(bound)
    return "won" if total <= limit else None
