"""LivescoreSportsEngine: real fixtures and live scores from Livescore's
public match API, prices from the in-house deterministic model
(`frame.verticals.sports.pricing`).

This is the primary real source because it is reachable from ordinary
hosts *and* from datacenter egress (Render), where ESPN's scoreboard
answers 403: its payload carries the day's fixtures across every
competition it covers, with an in-play status and running score. Livescore's
own prices are NOT served; the engine quotes its own book, so delivery never
depends on a bookmaker's payload. Cache-first, fail-open to the last good
snapshot, fail-closed (ProviderError) when nothing is on disk.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .contract import BetReceipt, Fixture, Market, Quote
from . import marketboard as MB
from . import locale_pt as PT

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
CACHE_PATH = os.path.join(REPO, "probes", "livescore-cache.json")

API = "https://prod-public-api.livescore.com/v1/api/app/date/soccer/{day}/0"
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
TTL = 120
# Today's card runs to a few hundred games; keep the board generous but
# bounded so one refresh stays small on the wire and in the response.
MAX_FIXTURES = 240
# Live games first, then what is still to come, then what already finished.
RANK = {"IN_PROGRESS": 0, "STATUS_SCHEDULED": 1, "STATUS_FINAL": 2}


class ProviderError(RuntimeError):
    pass


def _http(url: str) -> dict:
    """One day's answer.

    A provider that answers 503 is an answer too, and its response holds the
    connection open until the collector gets round to it — on a feed polled
    every 30 seconds that is a slow, silent leak. Close it and let the error
    travel on unchanged, so the caller still names the real failure.
    """
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=12,
                                    context=ssl.create_default_context()) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        exc.close()
        raise


def _team(side: object) -> str:
    """A side is a one-element list of team records; be tolerant of both."""
    if isinstance(side, list) and side:
        side = side[0]
    if isinstance(side, dict):
        return str(side.get("Nm") or "").strip()
    return ""


def _iso(esd: object) -> str:
    """``20261016190000`` (UTC, no separators) -> ISO 8601 with a ``Z``."""
    text = str(esd or "").strip()
    if len(text) < 14 or not text[:14].isdigit():
        return ""
    try:
        started = datetime.strptime(text[:14], "%Y%m%d%H%M%S")
    except ValueError:
        return ""
    return started.replace(tzinfo=timezone.utc) \
        .isoformat(timespec="seconds").replace("+00:00", "Z")


def _status(eps: object) -> str:
    """Livescore's in-play code -> our status vocabulary.

    ``NS``/``TBD`` never started, ``FT``/``AET``/``Pen.`` are over, the
    postponement family carries no game, and everything else — ``HT`` and the
    running minute (``24'``, ``90+3'``) — is in play.
    """
    code = str(eps or "").strip().lower()
    if code in ("", "ns", "tbd"):
        return "STATUS_SCHEDULED"
    if code.startswith(("ft", "aet", "pen", "awd", "awarded")):
        return "STATUS_FINAL"
    if code.rstrip(".") in ("postp", "postponed", "canc", "cancelled",
                            "canceled", "susp", "suspended", "aband",
                            "abandoned"):
        return "STATUS_POSTPONED"
    return "IN_PROGRESS"


def _parse_stages(data: dict) -> list[dict]:
    rows = []
    for stage in data.get("Stages") or []:
        if not isinstance(stage, dict):
            continue
        league = str(stage.get("Snm") or stage.get("CompN") or "Futebol")
        country = PT.pt(str(stage.get("Cnm") or "").strip())
        for event in stage.get("Events") or []:
            if not isinstance(event, dict):
                continue
            home, away = _team(event.get("T1")), _team(event.get("T2"))
            if not home or not away:
                continue
            rows.append({
                "key": str(event.get("Eid") or ""),
                "competition": league,
                "country": country,
                "home": home,
                "away": away,
                "kickoff": _iso(event.get("Esd")),
                "status": _status(event.get("Eps")),
                "home_score": _score(event.get("Tr1")),
                "away_score": _score(event.get("Tr2")),
                "progress": str(event.get("Eps") or "").strip(),
            })
    return rows


def _score(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


@dataclass
class LivescoreSportsEngine:
    cache_path: str = CACHE_PATH
    ttl_seconds: int = TTL
    days: int = 2
    limit: int = MAX_FIXTURES
    fetcher: object = None
    _events: list[dict] = field(default_factory=list)
    _fetched_at: float = 0.0
    accepted: dict[str, BetReceipt] = field(default_factory=dict)
    settled: dict[str, str] = field(default_factory=dict)

    def _url(self, day: datetime) -> str:
        return API.format(day=day.strftime("%Y%m%d"))

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
        try:
            events, errors = [], []
            start = datetime.now(timezone.utc).replace(hour=0, minute=0,
                                                       second=0, microsecond=0)
            for offset in range(self.days):
                try:
                    events.extend(_parse_stages(fetch(self._url(start + timedelta(days=offset)))))
                except Exception as exc:
                    errors.append(f"{offset}: {type(exc).__name__}")
            events.sort(key=lambda r: (RANK.get(r["status"], 3), r["kickoff"]))
            events = events[:self.limit]
            if not events:
                raise ProviderError("; ".join(errors) or "no events")
            self._events = events
            self._fetched_at = now
            try:
                os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
                with open(self.cache_path, "w", encoding="utf-8") as handle:
                    json.dump({"fetched_at": now, "source": "livescore public api",
                               "errors": errors, "events": events}, handle)
            except OSError:
                pass  # a read-only probes/ must not cost the board its data
        except Exception:
            if cached and cached.get("events"):
                self._events = cached["events"]
                self._fetched_at = float(cached.get("fetched_at", 0))
                return
            if self._events:
                return
            raise ProviderError("Livescore unreachable and no cache")

    def fixtures(self) -> list[Fixture]:
        self._refresh()
        return [Fixture(key=f"ls:{r['key']}", sport="soccer",
                        competition=r["competition"], country=r["country"],
                        home=r["home"], away=r["away"],
                        kickoff_date=r["kickoff"], status=r["status"],
                        home_score=r.get("home_score"),
                        away_score=r.get("away_score"),
                        progress=(r.get("progress") or "")
                        if r["status"] == "IN_PROGRESS" else "")
                for r in self._events]

    def _row(self, fixture_key: str) -> dict | None:
        self._refresh()
        for row in self._events:
            if f"ls:{row['key']}" == fixture_key:
                return row
        return None

    def _minute(self, row: dict) -> float:
        try:
            kickoff = datetime.fromisoformat(
                str(row["kickoff"]).replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        return max(0.0, (datetime.now(timezone.utc) - kickoff).total_seconds() / 60.0)

    def _live(self, row: dict) -> bool:
        return str(row.get("status") or "") == "IN_PROGRESS"

    def markets(self, fixture_key: str) -> list[Market]:
        row = self._row(fixture_key)
        if row is None:
            return []
        live = self._live(row)
        minute = self._minute(row) if live else 0.0
        return MB.quote_markets(fixture_key, "soccer", row["home"],
                                row["away"], live=live, minute=minute)

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
