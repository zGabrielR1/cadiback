"""Deterministic pricing model shared by every sports engine.

Team strength is a sha256-derived rating (no external data needed);
probabilities come from independent Poissons for soccer and a logistic
for NFL. Decimal prices come from the raw probabilities through a *per-market*
margin, not a flat one:

  * the margin is set per sport (`SPORT_MARGIN`) and nudged per market kind
    (`KIND_MARGIN`), so a 3-way derivative or a both-teams-to-score book
    carries a little more than the headline result;
  * `price_market` builds the book with the power form
    ``o_i = (1+margin)·p_i^k / Σ p_j^k`` — the overround is exactly `margin`
    by construction (k=1 gives the flat multiplicative margin; k>1 pushes more
    margin onto longshots, i.e. a favourite–longshot book), and a cent-grid
    correction keeps the delivered book as close to that margin as two decimals
    allow;
  * the per-30s drift is applied to the *probabilities* and renormalized, so it
    moves the shape of the book without changing how much margin it holds —
    which the old "multiply each price by 1+d" did not.

Same input, same price — reproducible under test. `to_price` and `drift` are
kept as thin back-compat wrappers: the in-house slate (`demo/odds_engine.py`)
and the frame tests still call them.
"""

from __future__ import annotations

import hashlib
import math
import time

MARGIN = 0.05

# Per-sport margin: tighter on the deep, liquid markets, wider on the thin ones.
SPORT_MARGIN = {
    "soccer": 0.05, "basketball": 0.045, "tennis": 0.055, "hockey": 0.055,
    "volleyball": 0.06, "futsal": 0.06, "handball": 0.06, "esports": 0.06,
    "baseball": 0.05, "football": 0.05, "rugby": 0.06, "cricket": 0.065,
}
# Added on top of the sport's margin for the derivative kinds.
KIND_MARGIN = {"dc": 0.02, "btts": 0.02, "total-h1": 0.01, "total-h2": 0.01,
               "ah": 0.01, "dnb": 0.01, "scorer-h": 0.05, "scorer-a": 0.05}
# The power `k`: >1 puts relatively more margin on the long side (a real book's
# favourite–longshot bias). 1.0 is a flat multiplicative margin.
KIND_BIAS = {"1x2": 1.12, "moneyline": 1.12, "total": 1.15, "total-h1": 1.0,
             "total-h2": 1.0, "dc": 1.0, "btts": 1.0, "dnb": 1.05, "ah": 1.1}
DEFAULT_MARGIN = 0.055

# How a side's goals are shared among its eleven, by role from the keeper out.
# A forward is ~a hundred times likelier than the keeper to get one and ~ten
# times likelier than a defender, which is the shape a real scorer list has.
SCORER_WEIGHT = {"GK": 0.01, "DEF": 0.10, "MID": 0.35, "FWD": 1.00}


def _hash(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def team_strength(name: str) -> float:
    """Deterministic per-team rating in [0.75, 1.25]."""
    return 0.75 + (_hash(name) % 100) / 200.0


def _poisson(lmbda: float, k: int) -> float:
    """Poisson pmf via the recurrence p_k = p_{k-1} * lmbda / k, so a large
    mean (basketball's ~220 points) never evaluates lmbda**k and overflows."""
    if lmbda <= 0.0:
        return 1.0 if k == 0 else 0.0
    term = math.exp(-lmbda)
    for i in range(1, k + 1):
        term *= lmbda / i
    return term


def _poisson_cdf(lmbda: float, k: int) -> float:
    """P(X <= k) for X ~ Poisson(lmbda), same recurrence as `_poisson`."""
    if lmbda <= 0.0:
        return 1.0
    term = math.exp(-lmbda)
    total = term
    for i in range(1, k + 1):
        term *= lmbda / i
        total += term
    return total


def soccer_probs(home: str, away: str) -> tuple[float, float, float]:
    """(home, draw, away) win probabilities via independent Poissons."""
    sh, sa = team_strength(home), team_strength(away)
    lh, la = _soccer_lambdas(sh, sa)
    p_home = p_draw = p_away = 0.0
    for h in range(11):
        for a in range(11):
            p = _poisson(lh, h) * _poisson(la, a)
            if h > a:
                p_home += p
            elif h == a:
                p_draw += p
            else:
                p_away += p
    return p_home, p_draw, p_away


def _soccer_lambdas(sh: float, sa: float) -> tuple[float, float]:
    return 1.45 * (sh / sa), 1.20 * (sa / sh)


def soccer_expected(home: str, away: str) -> tuple[float, float]:
    """(home, away) expected full-match goals from the strength model."""
    return _soccer_lambdas(team_strength(home), team_strength(away))


def scorer_probs(players, lam: float) -> list[float]:
    """P(each listed starter scores at least once) over what is left of the
    match.

    `lam` is the side's expected *remaining* goals; the caller scales the full
    match's rate by the clock. Those goals are shared among the eleven by role
    (`SCORER_WEIGHT`) and each player's chances are independent Poissons, so
    ``P = 1 - e^{-share·λ}`` — monotone in the time left and in the role, and
    never high enough to quote a certainty.
    """
    weights = [SCORER_WEIGHT.get(str(p.get("role") or "MID").upper(), 0.35)
               for p in players]
    total = sum(weights)
    if total <= 0.0 or float(lam) <= 0.0:
        return [0.0] * len(players)
    return [1.0 - math.exp(-(w / total) * float(lam)) for w in weights]


def match_probs(home: str, away: str, base: float) -> tuple[float, float, float]:
    """(home, draw, away) for a clock sport whose total is `base`: each side
    gets half of it, scaled by the strength ratio, on independent Poissons."""
    sh, sa = team_strength(home), team_strength(away)
    lh = (base / 2.0) * (sh / sa)
    la = (base / 2.0) * (sa / sh)
    p_home = p_draw = p_away = 0.0
    for h in range(int(lh + 6 * math.sqrt(lh)) + 2):
        ph = _poisson(lh, h)
        for a in range(int(la + 6 * math.sqrt(la)) + 2):
            p = ph * _poisson(la, a)
            if h > a:
                p_home += p
            elif h == a:
                p_draw += p
            else:
                p_away += p
    return p_home, p_draw, p_away


def both_score(home: str, away: str) -> float:
    """P(both sides finish with at least one)."""
    sh, sa = team_strength(home), team_strength(away)
    lh, la = _soccer_lambdas(sh, sa)
    return (1.0 - math.exp(-lh)) * (1.0 - math.exp(-la))


def total_probs_over(home: str, away: str, line: float,
                     factor: float = 1.0) -> float:
    """P(the total beats `line`); `factor` scales the expected total for a
    fragment of the game (a half, a period)."""
    sh, sa = team_strength(home), team_strength(away)
    lt = (1.45 * (sh / sa) + 1.20 * (sa / sh)) * factor
    return 1.0 - _poisson_cdf(lt, int(line))


def count_over(current: float, mean: float, frac: float,
               line: float) -> float:
    """P(a counting market finishes over `line`) for in-play.

    `mean` is the expected full-match count (cards, corners, fouls); `frac` is
    how much of the match has been played; `current` is the count so far. The
    remainder is an independent Poisson, so the live book tightens as the
    clock runs and there is less time left to add to the tally. Clamped away
    from the two extremes so a book never quotes a certainty.
    """
    remaining = max(0.0, float(mean) * (1.0 - max(0.0, min(1.0, float(frac)))))
    need = int(math.floor(float(line) - float(current)))
    over = 1.0 - _poisson_cdf(remaining, need)
    return min(0.98, max(0.02, over))


def nfl_probs(home: str, away: str) -> float:
    """Home win probability via logistic on the strength gap."""
    gap = team_strength(home) - team_strength(away)
    return 1.0 / (1.0 + math.exp(-6.0 * gap))


def nfl_total(home: str, away: str) -> float:
    sh, sa = team_strength(home), team_strength(away)
    lt = 43.5 + (sh + sa - 2.0) * 8.0
    return 1.0 - _poisson_cdf(lt, 45)


def points_total_over(home: str, away: str, base: float, scale: float,
                      line: float, factor: float = 1.0) -> float:
    sh, sa = team_strength(home), team_strength(away)
    lt = (base + (sh + sa - 2.0) * scale) * factor
    return 1.0 - _poisson_cdf(lt, int(line))


def to_price(prob: float) -> float:
    """Back-compat single price: the flat 5% multiplicative margin. New code
    prices a whole market through `price_market` so the overround is exact."""
    return max(1.01, round(1.0 / (prob * (1.0 + MARGIN)), 2))


def drift(seed_key: str, bucket: int, minute: float) -> float:
    """Per-30s wobble in ±3%, grown by the live minute. A *price* factor in the
    back-compat path; `price_market` applies the same values to probabilities."""
    seed = _hash(f"{seed_key}:{bucket}")
    wobble = ((seed % 200) - 100) / 3333.0
    return wobble * (1.0 + minute / 90.0)


# -- the per-market book -------------------------------------------------

def normalize(probs) -> list[float]:
    """A non-negative probability vector that sums to 1."""
    vals = [max(0.0, float(p)) for p in probs]
    total = sum(vals)
    if total <= 0.0:
        n = len(vals) or 1
        return [1.0 / n] * n
    return [v / total for v in vals]


def margin_for(sport: str, kind: str) -> float:
    """The target overround for one market: the sport's base plus the kind's."""
    return (SPORT_MARGIN.get(str(sport or "").lower(), DEFAULT_MARGIN)
            + KIND_MARGIN.get(str(kind or "").lower(), 0.0))


def bias_for(kind: str) -> float:
    return KIND_BIAS.get(str(kind or "").lower(), 1.0)


def drift_probs(base_key: str, bucket: int, minute: float,
                probs) -> list[float]:
    """Perturb probabilities by the per-leg wobble, then renormalize: the drift
    changes the shape of the book, never the margin it holds."""
    perturbed = [max(1e-9, p * (1.0 + drift(f"{base_key}:{i}", bucket, minute)))
                 for i, p in enumerate(probs)]
    return normalize(perturbed)


def _cent_fix(prices: list[float], target: float) -> list[float]:
    """Nudge the shortest-priced leg in 0.01 steps so the rounded book's
    overround lands as close to `target` as the cent grid allows."""
    if not prices:
        return prices
    out = list(prices)
    idx = min(range(len(out)), key=lambda i: out[i])

    def overround() -> float:
        return sum(1.0 / p for p in out) - 1.0

    for _ in range(6):
        err = overround() - target
        if abs(err) < 0.004:
            break
        step = 0.01 if err > 0 else -0.01
        out[idx] = round(max(1.01, out[idx] + step), 2)
    return out


def price_market(fixture_key: str, kind: str, probs, *, margin: float,
                 bias: float = 1.0, bucket: int | None = None,
                 minute: float = 0.0) -> tuple[float, ...]:
    """Decimal prices for one market with `margin` as the exact overround.

    ``o_i = (1+margin)·p_i^k / Σ p_j^k`` with ``k = bias``; the drift is applied
    to the probabilities first, so the delivered overround is `margin` (up to
    cent rounding) regardless of how the wobble moved the shape.
    """
    if bucket is None:
        bucket = int(time.time()) // 30
    p = drift_probs(f"{fixture_key}:{kind}", bucket, minute, normalize(probs))
    if bias and abs(bias - 1.0) > 1e-9:
        powered = [max(1e-12, q) ** bias for q in p]
        total = sum(powered) or 1.0
        implied = [(1.0 + margin) * v / total for v in powered]
    else:
        implied = [(1.0 + margin) * q for q in p]
    prices = [max(1.01, round(1.0 / o, 2)) if o > 0 else 1000.0
              for o in implied]
    return tuple(_cent_fix(prices, margin))


def overround(prices) -> float:
    """The book's margin: sum of implied probabilities minus one."""
    return sum(1.0 / float(p) for p in prices if float(p) > 0) - 1.0


def price_independent(fixture_key: str, kind: str, probs, *, margin: float,
                      bucket: int | None = None,
                      minute: float = 0.0) -> tuple[float, ...]:
    """Prices for *independent* selections — an anytime-scorer list.

    `price_market` renormalizes, which is right when the selections are
    exhaustive (a 1x2, an over/under: exactly one wins) and wrong for a list a
    player can win alongside others, where the implied probabilities do not sum
    to one. Here each leg carries its own margin, so the book holds `margin`
    per leg — the shape a real scorer list is delivered in — and the prices
    move on the same 30s wobble as the rest of the board.
    """
    if bucket is None:
        bucket = int(time.time()) // 30
    out = []
    for i, prob in enumerate(probs):
        quote = min(0.97, max(0.003, float(prob)))
        quote *= 1.0 + 0.5 * drift(f"{fixture_key}:{kind}:{i}", bucket, minute)
        implied = min(0.97, quote) * (1.0 + margin)
        out.append(max(1.01, round(1.0 / implied, 2)))
    return tuple(out)


def handicap_two_way(p_home: float, p_away: float, hcap: float,
                     scale: float = 0.9) -> tuple[float, float]:
    """Two-way handicap probabilities from a two-way result book.

    `hcap` is the handicap applied to the home score (negative when the home
    side gives goals). A log-odds shift of `scale·hcap` is a bounded, monotone
    stand-in for a full goal-difference model: a bigger give shortens the home
    price, never inverts it.
    """
    total = p_home + p_away
    base = (p_home / total) if total > 0 else 0.5
    base = min(0.97, max(0.03, base))
    shifted = math.log(base / (1.0 - base)) + scale * hcap
    ph = 1.0 / (1.0 + math.exp(-shifted))
    return ph, 1.0 - ph


def inplay_probs(kind: str, probs, home_score, away_score, minute: float,
                 cap: float = 90.0) -> list[float]:
    """Live adjustment: shift a result book toward the current leader, or —
    level and late — toward the draw. Deterministic and bounded; the pre-match
    model is the base, the score only tilts it."""
    p = normalize(probs)
    if len(p) < 2 or home_score is None or away_score is None:
        return p
    frac = (max(0.0, min(1.0, float(minute) / float(cap)))
            if cap and cap > 0 else 0.0)
    if frac <= 0.0:
        return p
    try:
        diff = int(home_score) - int(away_score)
    except (TypeError, ValueError):
        return p
    boost = min(6.0, 1.0 + 0.9 * abs(diff) * frac)
    if len(p) == 3:
        home, draw, away = p
        if diff > 0:
            home *= boost
        elif diff < 0:
            away *= boost
        else:
            draw *= 1.0 + 1.2 * frac
        return normalize([home, draw, away])
    line = list(p)
    if diff > 0:
        line[0] *= boost
    elif diff < 0:
        line[-1] *= boost
    return normalize(line)
