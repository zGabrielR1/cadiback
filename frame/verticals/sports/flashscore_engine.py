"""FlashscoreSportsEngine: real fixtures, leagues, in-play status and live
scores from Flashscore's public match feed, priced by the shared in-house
market board (`marketboard.py`).

Flashscore is the primary real source because one keyless feed format
covers every sport it carries (`f_<sport>_<day>_3_en_1`, no key, only an
`x-fsign` header), reaches the datacenter egress Render needs, and ships the
facts a real board prints: country, league, kickoff, status and the running
score. Flashscore's own prices are NOT served — several sports it carries
have no draw (tennis) or a different money shape, and delivery must never
depend on a bookmaker's payload, so every quote comes from our own model.

Cache-first, fail-open to the last good snapshot, fail-closed (ProviderError)
when nothing is on disk.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .contract import BetReceipt, Fixture, Market, Quote
from . import marketboard as MB
from . import locale_pt as PT
from . import stats_engine as SE

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
CACHE_PATH = os.path.join(REPO, "probes", "flashscore-cache.json")

BASE = "https://global.flashscore.ninja/2/x/feed/f_{sport}_{day}_3_en_1"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "*/*",
           "x-fsign": "SW9D1eZo", "Referer": "https://www.flashscore.com/"}
TTL = 120
MAX_FIXTURES = 320

# sport id -> canonical key. Bushiest sports (soccer, then the racket/ball
# sports) also pull tomorrow so the "Esportes" board is not today-only.
SPORTS = {1: "soccer", 2: "tennis", 3: "basketball", 4: "hockey",
          6: "baseball", 7: "handball", 8: "rugby", 9: "volleyball",
          12: "esports", 36: "futsal"}
EXTRA_DAYS = {1: (1,), 2: (1,), 3: (1,)}

# Flashscore's status code -> our vocabulary
FS_STATUS = {"1": "STATUS_SCHEDULED", "2": "IN_PROGRESS", "3": "STATUS_FINAL"}
# the in-play clock only means minutes for the clock sports; a set- or
# innings-based sport shows the live dot without a misleading minute
LIVE_CAP = {"soccer": 90, "futsal": 40, "handball": 60, "basketball": 48,
            "hockey": 60, "rugby": 80, "football": 60}
RANK = {"IN_PROGRESS": 0, "STATUS_SCHEDULED": 1, "STATUS_FINAL": 2}

# Sports whose per-match stats feed we read (cards, corners, fouls). A sport
# without a stats feed simply never carries those markets.
STATS_SPORTS = {"soccer", "futsal"}

# settlement's archive: yesterday's finals, pulled lazily with its own cache
# so the board never pays ten extra requests for a lookup it rarely needs
RESULTS_TTL = 900
RESULTS_CACHE = "probes/flashscore-results-cache.json"


class ProviderError(RuntimeError):
    pass


def _http(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15,
                                    context=ssl.create_default_context()) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        exc.close()
        raise


def _entities(raw: str) -> list[dict]:
    """The feed is `~`-prefixed record groups separated by `¬`; a stage's
    following records accumulate onto it, each match starts a new group."""
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


def _int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc) \
        .isoformat(timespec="seconds").replace("+00:00", "Z")


def _league_name(raw: str, country: str) -> str:
    """Flashscore spells a stage `COUNTRY: League`; the country is already a
    separate field, so drop the redundant all-caps prefix."""
    if ": " in raw:
        head, tail = raw.split(": ", 1)
        if tail.strip() and head == head.upper():
            return tail.strip()
    return raw or country or "Outros"


def _parse(raw: str, sport: str) -> list[dict]:
    rows: list[dict] = []
    league = country = ""
    for ent in _entities(raw):
        if "ZA" in ent:
            league = str(ent.get("ZA") or "").strip()
            country = PT.pt(str(ent.get("ZY") or "").strip())
            continue
        if "AA" not in ent:
            continue
        home = str(ent.get("AE") or "").strip()
        away = str(ent.get("AF") or "").strip()
        if not home or not away:
            continue
        status = FS_STATUS.get(str(ent.get("AB") or "").strip(),
                                "STATUS_SCHEDULED")
        played = status != "STATUS_SCHEDULED"
        stamp = _int(ent.get("AD"))
        rows.append({
            "key": str(ent.get("AA") or ""),
            "sport": sport,
            "country": country,
            "competition": _league_name(league, country),
            "home": home,
            "away": away,
            "kickoff": _iso(stamp) if stamp else "",
            "status": status,
            "home_score": _int(ent.get("AG")) if played else None,
            "away_score": _int(ent.get("AH")) if played else None,
        })
    return rows


@dataclass
class FlashscoreSportsEngine:
    cache_path: str = CACHE_PATH
    ttl_seconds: int = TTL
    limit: int = MAX_FIXTURES
    fetcher: object = None
    results_cache: str = RESULTS_CACHE
    sports: dict = field(default_factory=lambda: dict(SPORTS))
    # the per-match stats reader (cards/corners/fouls + the stats panel); its
    # own bounded, cached transport, lazily built so a board that never asks
    # for stats never constructs it
    stats_engine: object = None
    _events: list[dict] = field(default_factory=list)
    _fetched_at: float = 0.0
    _results: list[dict] = field(default_factory=list)
    _results_at: float = 0.0
    accepted: dict[str, BetReceipt] = field(default_factory=dict)
    settled: dict[str, str] = field(default_factory=dict)

    def _url(self, sport_id: int, day: int) -> str:
        return BASE.format(sport=sport_id, day=day)

    def _jobs(self) -> list[tuple[int, int, str]]:
        jobs = []
        for sport_id, sport in self.sports.items():
            days = (0,) + tuple(EXTRA_DAYS.get(sport_id, ()))
            for day in days:
                jobs.append((sport_id, day, sport))
        return jobs

    def _refresh(self) -> None:
        now = time.time()
        cached = None
        try:
            with open(self.cache_path, "r", encoding="utf-8") as handle:
                cached = json.load(handle)
            if now - float(cached.get("fetched_at", 0)) < self.ttl_seconds \
                    and cached.get("events"):
                self._events = cached["events"]
                self._fetched_at = float(cached["fetched_at"])
                return
        except (ValueError, OSError, KeyError):
            pass
        fetch = self.fetcher or _http

        def one(job):
            sport_id, day, sport = job
            return _parse(fetch(self._url(sport_id, day)), sport)

        events, errors = [], []
        jobs = self._jobs()
        try:
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(one, jobs))
            for chunk in results:
                events.extend(chunk)
            if not events:
                raise ProviderError("no events")
            events.sort(key=lambda r: (RANK.get(r["status"], 3),
                                       r["kickoff"]))
            self._events = events[:self.limit]
            self._fetched_at = now
            try:
                os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
                with open(self.cache_path, "w", encoding="utf-8") as handle:
                    json.dump({"fetched_at": now, "source": "flashscore feed",
                               "errors": errors, "events": self._events},
                              handle)
            except OSError:
                pass  # a read-only probes/ must not cost the board its data
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            if cached and cached.get("events"):
                self._events = cached["events"]
                self._fetched_at = float(cached.get("fetched_at", 0))
                return
            if self._events:
                return
            raise ProviderError("Flashscore unreachable and no cache")

    def _minute(self, row: dict) -> float:
        if not row.get("kickoff"):
            return 0.0
        try:
            kickoff = datetime.fromisoformat(
                str(row["kickoff"]).replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        return max(0.0, (datetime.now(timezone.utc) - kickoff).total_seconds() / 60.0)

    def _progress(self, row: dict) -> str:
        if row.get("status") != "IN_PROGRESS":
            return ""
        cap = LIVE_CAP.get(str(row.get("sport") or ""))
        if cap is None:
            return ""
        minute = self._minute(row)
        if minute <= 0:
            return ""
        if minute >= cap:
            return f"{cap}+'"
        return f"{int(minute)}'"

    def fixtures(self) -> list[Fixture]:
        self._refresh()
        return [Fixture(key=f"fs:{r['key']}", sport=r["sport"],
                        competition=r["competition"], country=r["country"],
                        home=r["home"], away=r["away"],
                        kickoff_date=r["kickoff"], status=r["status"],
                        home_score=r["home_score"], away_score=r["away_score"],
                        progress=self._progress(r),
                        stats=self._stats_for(r)) for r in self._events]

    def _stats_reader(self):
        if self.stats_engine is None:
            self.stats_engine = SE.MatchStatsEngine()
        return self.stats_engine

    def _stats_for(self, row: dict) -> dict:
        """The Match-section stats for one fixture, or `{}`. A scheduled match
        has no stats yet and a sport with no stats feed is never asked, so the
        budget is spent only on the fixtures the panel can actually show."""
        if row.get("status") == "STATUS_SCHEDULED":
            return {}
        if str(row.get("sport") or "") not in STATS_SPORTS:
            return {}
        return self._stats_reader().match_stats(str(row["key"]))

    def _row(self, fixture_key: str) -> dict | None:
        self._refresh()
        for row in self._events:
            if f"fs:{row['key']}" == fixture_key:
                return row
        return None

    def results(self) -> dict[str, dict]:
        """Real finals keyed `fs:<id>` — yesterday's archive *and* today's
        full feed, since the board keeps only its 320 most-relevant rows and
        a morning final can legitimately drop off it. A separate, lazily
        pulled fetch with its own cache: `fixtures()` stays untouched, so
        nothing extra shows up on the board. It fails quiet — settlement
        prefers staying pending to inventing a verdict."""
        self._refresh_results()
        return {f"fs:{r['key']}": dict(r) for r in self._results}

    def _refresh_results(self) -> None:
        now = time.time()
        if self._results and now - self._results_at < RESULTS_TTL:
            return
        try:
            with open(self.results_cache, "r", encoding="utf-8") as handle:
                cached = json.load(handle)
            if now - float(cached.get("fetched_at", 0)) < RESULTS_TTL \
                    and cached.get("rows"):
                self._results = cached["rows"]
                self._results_at = float(cached["fetched_at"])
                return
        except (ValueError, OSError):
            pass
        if self._results:
            return  # keep what we have; pending beats an invented verdict
        fetch = self.fetcher or _http
        rows: list[dict] = []

        def one(job):
            sport_id, day, sport = job
            return _parse(fetch(self._url(sport_id, day)), sport)

        try:
            with ThreadPoolExecutor(max_workers=6) as pool:
                for chunk in pool.map(
                        one, [(sid, -1, sport) for sid, sport in
                              self.sports.items()]
                        + [(sid, 0, sport) for sid, sport in
                           self.sports.items()]):
                    rows.extend(chunk)
            finals: dict[str, dict] = {}
            for row in rows:  # day 0 feeds second: today's live truth wins
                if row["status"] == "STATUS_FINAL":
                    finals[f"fs:{row['key']}"] = row
            self._results = list(finals.values())
        except Exception:
            return  # settlement stays pending rather than inventing results
        self._results_at = now
        self._save_results()

    def _save_results(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.results_cache), exist_ok=True)
            with open(self.results_cache, "w", encoding="utf-8") as handle:
                json.dump({"fetched_at": self._results_at, "rows": self._results},
                          handle)
        except OSError:
            pass  # a read-only probes/ must not cost settlement its archive

    def markets(self, fixture_key: str) -> list[Market]:
        row = self._row(fixture_key)
        if row is None:
            return []
        live = row.get("status") == "IN_PROGRESS"
        minute = self._minute(row) if live else 0.0
        return MB.quote_markets(fixture_key, str(row["sport"]), row["home"],
                                row["away"], live=live, minute=minute,
                                home_score=row.get("home_score"),
                                away_score=row.get("away_score"),
                                stats=self._stats_for(row))

    def quote(self, market_key: str) -> Quote | None:
        fixture_key = market_key.rsplit(":", 1)[0]
        markets = {m.key: m for m in self.markets(fixture_key)}
        market = markets.get(market_key)
        if market is None:
            return None
        return Quote(market_key=market_key, prices=market.prices,
                     offered_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     version=int(time.time()) // 30)

    def accept(self, bet_key: str, market_key: str, stake_minor: int) -> BetReceipt:
        quote = self.quote(market_key)
        if quote is None:
            raise ProviderError(f"no quote for {market_key}")
        if bet_key in self.accepted:
            raise ProviderError(f"bet already accepted: {bet_key}")
        if stake_minor <= 0:
            raise ProviderError("stake must be positive")
        receipt = BetReceipt(bet_key=bet_key, market_key=market_key,
                             stake_minor=stake_minor, decimal_odds=quote.prices[0],
                             accepted_version=quote.version)
        self.accepted[bet_key] = receipt
        return receipt

    def settle(self, bet_key: str, result: dict[str, str]) -> str:
        if bet_key not in self.accepted:
            raise ProviderError(f"unknown bet: {bet_key}")
        if bet_key in self.settled:
            raise ProviderError(f"bet already settled: {bet_key}")
        selection = result.get("selection")
        if not selection:
            raise ProviderError("result selection required")
        state = "lost" if selection in ("away", "under") else "won"
        self.settled[bet_key] = state
        return state

    def void(self, bet_key: str, reason: str) -> str:
        if bet_key in self.settled:
            raise ProviderError(f"cannot void a settled bet: {bet_key}")
        self.settled[bet_key] = f"void:{reason}"
        return self.settled[bet_key]
