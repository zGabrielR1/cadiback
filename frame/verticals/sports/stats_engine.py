"""Per-match statistics and incidents from Flashscore's match feeds.

The fixtures feed (`f_<sport>_<day>_3_en_1`, see `flashscore_engine`) carries
who plays and the running score; these two feeds carry *what happened*:

    stats      df_st_1_<matchId>   possession, shots, corners, cards, fouls
    incidents  df_sui_1_<matchId>  goals, bookings and substitutions, with the
                                   player's name, id, side and minute

Both are keyless and share the fixtures feed's `x-fsign` header. They are read
only to *describe* a live match (a stats panel) and to *settle* the count
markets the board quotes (`cards`, `corners`, `fouls`) — never to invent a
price. Cache-first and fail-open to the last good snapshot, like every other
engine here: an unreachable feed costs nothing but freshness.

The whole surface is stdlib and the transport is injectable, so the parsers are
testable against the real field shapes without a network.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
CACHE_PATH = os.path.join(REPO, "probes", "flashscore-stats-cache.json")

BASE = "https://global.flashscore.ninja/2/x/feed/{kind}{match_id}"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "*/*",
           "x-fsign": "SW9D1eZo", "Referer": "https://www.flashscore.com/"}
STATS_KIND = "df_st_1_"
INCIDENTS_KIND = "df_sui_1_"
TTL = 90
# a stats read is one request per match, so a board of 160 fixtures cannot ask
# for all of them: the engine spends a bounded budget per TTL window and then
# serves cache-only until the window rolls
DEFAULT_BUDGET = 24

# Flashscore names a stat in `SG`; this maps the ones we show/quote. A stat we
# do not map is still parsed (the caller can read it) but is not surfaced.
STAT_NAMES = {
    "ball possession": "possession",
    "total shots": "shots",
    "shots on target": "shots_on_target",
    "shots off target": "shots_off_target",
    "corner kicks": "corners",
    "yellow cards": "yellow_cards",
    "red cards": "red_cards",
    "fouls": "fouls",
}
SECTIONS = {"match": "match", "1st half": "h1", "2nd half": "h2"}


class StatsError(RuntimeError):
    pass


def _num(value: object) -> float | None:
    text = str(value if value is not None else "").strip().replace("%", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number == int(number) else number


def _section(raw: str) -> str:
    return SECTIONS.get(str(raw or "").strip().lower(), "match")


def parse_stats(raw: str) -> dict:
    """`{section: {stat_key: (home, away)}}` from the `df_st_1_` feed.

    The feed is a flat `¬`-separated stream: `SE` opens a section (Match, 1st
    Half, 2nd Half), `SF` opens a subgroup we ignore, and a stat is the run
    `SD` (id) → `SG` (name) → `SH`/`SI` (the two sides). A stat row ends when
    the next `SD` starts, so the parser flushes on each one.
    """
    out: dict[str, dict[str, tuple]] = {}
    section = "match"
    pending: dict[str, str] = {}

    def flush() -> None:
        key = STAT_NAMES.get(str(pending.get("SG") or "").strip().lower())
        if key:
            out.setdefault(section, {})[key] = (_num(pending.get("SH")),
                                                _num(pending.get("SI")))

    for record in raw.split("\u00ac"):
        if record.startswith("~"):
            record = record[1:]
        parts = record.split("\u00f7")
        if len(parts) < 2:
            continue
        name, value = parts[0], "\u00f7".join(parts[1:])
        if name == "SE":
            flush()
            pending = {}
            section = _section(value)
        elif name == "SD":
            flush()
            pending = {"SD": value}
        elif name in ("SG", "SH", "SI"):
            pending[name] = value
    flush()
    return out


def _records(raw: str) -> list[dict]:
    """The `~`-grouped shape the incidents feed shares with the fixtures feed."""
    out: list[dict] = []
    cur: dict | None = None
    for record in raw.split("\u00ac"):
        if record.startswith("~"):
            cur = {}
            out.append(cur)
            record = record[1:]
        if cur is None:
            cur = {}
            out.append(cur)
        parts = record.split("\u00f7")
        if len(parts) >= 2:
            cur[parts[0]] = "\u00f7".join(parts[1:])
    return out


def parse_incidents(raw: str) -> list[dict]:
    """Goals, bookings and substitutions, each with the acting side.

    `IA` is Flashscore's side flag (1 = home, 2 = away); `IK` the incident kind
    and `IF`/`IM` the player's name and id. Substitutions appear twice (out and
    in) and are kept both — a caller wanting only goals filters on `is_goal`.
    """
    out: list[dict] = []
    for ent in _records(raw):
        kind = str(ent.get("IK") or "").strip()
        name = str(ent.get("IF") or "").strip()
        if not kind or not name:
            continue
        side = "home" if str(ent.get("IA") or "").strip() == "1" else "away"
        out.append({
            "kind": kind,
            "is_goal": "goal" in kind.lower() and "own" not in kind.lower(),
            "is_own_goal": "own goal" in kind.lower(),
            "is_card": "card" in kind.lower(),
            "player": name,
            "player_id": str(ent.get("IM") or "").strip(),
            "side": side,
            "minute": str(ent.get("IB") or "").strip(),
        })
    return out


# field name -> (feed kind, parser, empty value). The two feeds are fetched
# independently so a board that only needs the stats (the count markets) never
# pays for the incidents feed, and vice versa.
FIELDS = {
    "stats": (STATS_KIND, parse_stats, dict),
    "incidents": (INCIDENTS_KIND, parse_incidents, list),
}


def _http(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=12,
                                    context=ssl.create_default_context()) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        exc.close()
        raise


def _url(kind: str, match_id: str) -> str:
    return BASE.format(kind=kind, match_id=match_id)


class MatchStatsEngine:
    """A bounded, cached reader of the two per-match feeds."""

    def __init__(self, cache_path: str = CACHE_PATH, ttl_seconds: int = TTL,
                 fetcher: object = None, budget: int = DEFAULT_BUDGET) -> None:
        self.cache_path = cache_path
        self.ttl_seconds = ttl_seconds
        self.fetcher = fetcher or _http
        self.budget = budget
        self._matches: dict[str, dict] = {}
        self._fetched_at: float = 0.0
        self._window_at: float = 0.0
        self._spent: int = 0

    def _load(self) -> None:
        if self._matches:
            return
        try:
            with open(self.cache_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self._matches = payload.get("matches") or {}
            self._fetched_at = float(payload.get("fetched_at") or 0)
        except (ValueError, OSError, KeyError):
            self._matches = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as handle:
                json.dump({"fetched_at": self._fetched_at, "matches": self._matches},
                          handle)
        except OSError:
            pass  # a read-only probes/ must not cost the panel its data

    def _fresh(self, slot: dict | None) -> bool:
        return bool(slot) and \
            time.time() - float(slot.get("at") or 0) < self.ttl_seconds

    def _may_spend(self) -> bool:
        now = time.time()
        if now - self._window_at >= self.ttl_seconds:
            self._window_at = now
            self._spent = 0
        if self._spent >= self.budget:
            return False
        self._spent += 1
        return True

    def _field(self, match_id: str, name: str):
        """One cached field (`stats` or `incidents`) for one match.

        Each feed is fetched on its own: a caller that only needs the stats
        never pays for the incidents feed, and a fetch that fails or is beyond
        the budget serves the last good snapshot (fail-open) rather than
        raising or inventing an empty board.
        """
        self._load()
        entry = self._matches.setdefault(str(match_id), {})
        slot = entry.get(name)
        if self._fresh(slot):
            return slot["value"]
        stale = slot["value"] if slot else None
        if not self._may_spend():
            return stale if stale is not None else FIELDS[name][2]()
        kind, parser, empty = FIELDS[name]
        try:
            value = parser(self.fetcher(_url(kind, match_id)))
        except Exception:
            return stale if stale is not None else empty()
        entry[name] = {"value": value, "at": time.time()}
        self._fetched_at = time.time()
        self._save()
        return value

    def stats(self, match_id: str) -> dict:
        """The parsed stat sections for one match — `{}` when unknown."""
        return dict(self._field(match_id, "stats") or {})

    def incidents(self, match_id: str) -> list[dict]:
        return list(self._field(match_id, "incidents") or [])

    def match_stats(self, match_id: str) -> dict:
        """The Match (full-time) section alone — the shape `settlement` reads."""
        return dict(self.stats(match_id).get("match") or {})

    def snapshot(self) -> dict:
        self._load()
        return {"fetched_at": self._fetched_at, "matches": len(self._matches)}
