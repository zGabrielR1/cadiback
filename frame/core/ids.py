from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime


def canonical_day(value: date | str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        day = normalize(text)
        if not day:
            raise IdentityError("fixture needs a kickoff date")
        return day

QUALIFIERS = frozenset(
    {
        "fc", "cf", "sc", "ac", "ec", "if", "as", "sv", "vfl",
        "vfb", "tsv", "bsc", "ssc", "us",
        "de", "do", "da", "dos", "das", "e", "the",
    }
)

EXACT = "EXACT"
QUALIFIED = "QUALIFIED"
AMBIGUOUS = "AMBIGUOUS"
DIFFERENT = "DIFFERENT"


class IdentityError(ValueError):
    pass


def normalize(text: str) -> str:
    if not isinstance(text, str):
        raise IdentityError(f"expected str, got {type(text).__name__}")
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = stripped.casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", lowered).split())


def tokens(text: str) -> frozenset[str]:
    return frozenset(normalize(text).split())


def digest(*parts: str) -> str:
    joined = "\x1f".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def slug(*parts: str) -> str:
    return digest(*parts)[:32]


def fixture_key(
    sport: str,
    competition: str,
    home: str,
    away: str,
    kickoff_date: date | str,
) -> str:
    home_norm = normalize(home)
    away_norm = normalize(away)
    if not home_norm or not away_norm:
        raise IdentityError(f"fixture needs both teams: {home!r} vs {away!r}")
    if home_norm == away_norm:
        raise IdentityError(f"fixture cannot be a team against itself: {home_norm}")
    kick = canonical_day(kickoff_date)
    ordered = sorted([home_norm, away_norm])
    return slug(sport, normalize(competition), ordered[0], ordered[1], kick)


@dataclass(frozen=True)
class TeamPair:
    left: str
    right: str


@dataclass(frozen=True)
class MatchResult:
    status: str
    qualifier: str | None = None
    closest: TeamPair | None = None
    jaccard: float = 0.0

    @property
    def resolved(self) -> bool:
        return self.status in (EXACT, QUALIFIED)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def match_teams(left: str, right: str, candidates: list[str]) -> MatchResult:
    """Refuse to guess. Returns AMBIGUOUS with the closest name pair instead of a pick."""
    left_norm = normalize(left)
    right_norm = normalize(right)
    if not left_norm or not right_norm:
        return MatchResult(status=DIFFERENT)
    if left_norm == right_norm:
        return MatchResult(status=EXACT)
    left_tokens = tokens(left)
    right_tokens = tokens(right)
    extras = (left_tokens | right_tokens) - (left_tokens & right_tokens)
    subset = left_tokens <= right_tokens or right_tokens <= left_tokens
    if subset and extras and extras <= QUALIFIERS:
        return MatchResult(status=QUALIFIED, qualifier=" ".join(sorted(extras)))
    known = {normalize(c) for c in candidates}
    for side in (left_norm, right_norm):
        if side in known:
            other = right_norm if side == left_norm else left_norm
            return MatchResult(status=AMBIGUOUS, closest=TeamPair(left=side, right=other))
    if candidates:
        union = left_tokens | right_tokens
        best = max(candidates, key=lambda c: _jaccard(tokens(c), union))
        return MatchResult(
            status=AMBIGUOUS,
            closest=TeamPair(left=best, right=left_norm),
            jaccard=round(_jaccard(tokens(best), union), 4),
        )
    return MatchResult(status=AMBIGUOUS, closest=TeamPair(left=left_norm, right=right_norm))


def wagering_key(player_id: str, market_ref: str, placed_at: str) -> str:
    if not player_id or not market_ref or not placed_at:
        raise IdentityError("wagering_key needs player_id, market_ref and placed_at")
    return slug("wager", player_id, market_ref, placed_at)


def idempotency_key(*parts: str) -> str:
    if not parts or any(p is None or str(p) == "" for p in parts):
        raise IdentityError("idempotency_key needs non-empty parts")
    return slug(*parts)
