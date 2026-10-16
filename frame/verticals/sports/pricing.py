"""Deterministic pricing model shared by every sports engine.

Team strength is a sha256-derived rating (no external data needed);
probabilities come from independent Poissons for soccer and a logistic
for NFL, then a uniform 5% book margin turns probabilities into decimal
prices. Same input, same price — reproducible under test.
"""

from __future__ import annotations

import hashlib
import math

MARGIN = 0.05


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
    lh = 1.45 * (sh / sa)
    la = 1.20 * (sa / sh)
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


def total_probs_over(home: str, away: str, line: float) -> float:
    sh, sa = team_strength(home), team_strength(away)
    lt = 1.45 * (sh / sa) + 1.20 * (sa / sh)
    return 1.0 - _poisson_cdf(lt, int(line))


def nfl_probs(home: str, away: str) -> float:
    """Home win probability via logistic on the strength gap."""
    gap = team_strength(home) - team_strength(away)
    return 1.0 / (1.0 + math.exp(-6.0 * gap))


def nfl_total(home: str, away: str) -> float:
    sh, sa = team_strength(home), team_strength(away)
    lt = 43.5 + (sh + sa - 2.0) * 8.0
    return 1.0 - _poisson_cdf(lt, 45)


def points_total_over(home: str, away: str, base: float, scale: float,
                      line: float) -> float:
    sh, sa = team_strength(home), team_strength(away)
    lt = base + (sh + sa - 2.0) * scale
    return 1.0 - _poisson_cdf(lt, int(line))


def to_price(prob: float) -> float:
    return max(1.01, round(1.0 / (prob * (1.0 + MARGIN)), 2))


def drift(seed_key: str, bucket: int, minute: float) -> float:
    seed = _hash(f"{seed_key}:{bucket}")
    wobble = ((seed % 200) - 100) / 3333.0  # ±3%
    return wobble * (1.0 + minute / 90.0)
