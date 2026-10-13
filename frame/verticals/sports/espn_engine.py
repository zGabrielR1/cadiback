"""EspnSportsEngine: real fixtures from ESPN scoreboards, prices from
the in-house deterministic model (`frame.verticals.sports.pricing`).

Same source as cleanSheet's edgewatch: public scoreboard endpoints,
soccer comps + NFL. ESPN's own DraftKings prices are NOT served; the
engine quotes its own book so the delivery never depends on a
bookmaker's payload. Cache-first, fail-open to the last good snapshot,
fail-closed (ProviderError) when nothing is on disk.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .contract import BetReceipt, Fixture, Market, Quote
from . import pricing as P

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
CACHE_PATH = os.path.join(REPO, "probes", "espn-cache.json")

FEEDS = {
    "bra.1": ("https://site.web.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard", "soccer"),
    "ita.1": ("https://site.web.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard", "soccer"),
    "eng.1": ("https://site.web.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard", "soccer"),
    "esp.1": ("https://site.web.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard", "soccer"),
    "ger.1": ("https://site.web.api.espn.com/apis/site/v2/sports/soccer/ger.1/scoreboard", "soccer"),
    "fra.1": ("https://site.web.api.espn.com/apis/site/v2/sports/soccer/fra.1/scoreboard", "soccer"),
    "uefa.champions": ("https://site.web.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard", "soccer"),
    "nfl": ("https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard", "nfl"),
    "nba": ("https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard", "nba"),
    "mlb": ("https://site.web.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard", "mlb"),
    "nhl": ("https://site.web.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard", "nhl"),
}

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
SPORT = {comp_id: kind for comp_id, (_, kind) in FEEDS.items()}
STATUS_DURATION = {"soccer": 105, "nfl": 195, "nba": 150, "mlb": 180, "nhl": 150}


class ProviderError(RuntimeError):
    pass


def _http(url: str) -> dict:
    """One scoreboard answer.

    A provider that answers 503 is an answer too, and its response holds the
    connection open until the collector gets round to it — on a feed polled
    every 30 seconds that is a slow, silent leak. Close it and let the error
    travel on unchanged, so the caller still names the real failure.
    """
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=8,
                                    context=ssl.create_default_context()) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        exc.close()
        raise


def _parse_events(comp_id: str, data: dict) -> list[dict]:
    rows = []
    for event in data.get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        teams = {}
        for competitor in comp.get("competitors") or []:
            teams[competitor.get("homeAway")] = (
                (competitor.get("team") or {}).get("displayName"))
        if not teams.get("home") or not teams.get("away"):
            continue
        status = ((event.get("status") or {}).get("type") or {}).get("name") or ""
        rows.append({
            "key": str(event.get("id")),
            "competition": comp_id,
            "home": teams["home"],
            "away": teams["away"],
            "kickoff": event.get("date") or "",
            "status": status,
        })
    return rows


@dataclass
class EspnSportsEngine:
    cache_path: str = CACHE_PATH
    ttl_seconds: int = 120
    fetcher: object = None
    _events: list[dict] = field(default_factory=list)
    _fetched_at: float = 0.0
    accepted: dict[str, BetReceipt] = field(default_factory=dict)
    settled: dict[str, str] = field(default_factory=dict)

    def _refresh(self) -> None:
        now = time.time()
        try:
            with open(self.cache_path, "r", encoding="utf-8") as handle:
                cached = json.load(handle)
            if now - float(cached.get("fetched_at", 0)) < self.ttl_seconds \
                    and cached.get("events"):
                self._events = cached["events"]
                self._fetched_at = float(cached["fetched_at"])
                return
        except (ValueError, OSError, KeyError):
            cached = None
        fetch = self.fetcher or _http
        try:
            events = []
            errors = []
            for comp_id, (url, _kind) in FEEDS.items():
                try:
                    events.extend(_parse_events(comp_id, fetch(url)))
                except Exception as exc:
                    errors.append(f"{comp_id}: {type(exc).__name__}")
            if not events:
                raise ProviderError("; ".join(errors) or "no events")
            self._events = events
            self._fetched_at = now
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as handle:
                json.dump({"fetched_at": now, "source": "espn scoreboard",
                           "errors": errors, "events": events}, handle)
        except Exception:
            if cached and cached.get("events"):
                self._events = cached["events"]
                self._fetched_at = float(cached.get("fetched_at", 0))
                return
            if self._events:
                return
            raise ProviderError("ESPN unreachable and no cache")

    def fixtures(self) -> list[Fixture]:
        self._refresh()
        out = []
        for row in self._events:
            out.append(Fixture(
                key=f"{row['competition']}:{row['key']}",
                sport=SPORT[row["competition"]],
                competition=row["competition"],
                home=row["home"],
                away=row["away"],
                kickoff_date=row["kickoff"],
            ))
        return out

    def _row(self, fixture_key: str) -> dict | None:
        self._refresh()
        for row in self._events:
            if f"{row['competition']}:{row['key']}" == fixture_key:
                return row
        return None

    def _minute(self, row: dict) -> float:
        if not row.get("kickoff"):
            return 0.0
        try:
            kickoff = datetime.fromisoformat(
                str(row["kickoff"]).replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        return max(0.0, (datetime.now(timezone.utc) - kickoff).total_seconds() / 60.0)

    def _live(self, row: dict) -> bool:
        status = str(row.get("status") or "")
        return "IN_PROGRESS" in status or "LIVE" in status

    def markets(self, fixture_key: str) -> list[Market]:
        row = self._row(fixture_key)
        if row is None:
            return []
        bucket = int(time.time()) // 30
        minute = self._minute(row) if self._live(row) else 0.0
        sport = SPORT[row["competition"]]
        out = []

        def add(kind, selections, probs):
            prices = []
            for i, prob in enumerate(probs):
                ratio = 1.0 + P.drift(f"{fixture_key}:{kind}:{i}", bucket, minute)
                prices.append(max(1.01, round(P.to_price(prob) * ratio, 2)))
            out.append(Market(
                key=f"{fixture_key}:{kind}",
                fixture_key=fixture_key,
                kind=kind,
                selections=tuple(selections),
                prices=tuple(prices),
            ))

        if sport == "soccer":
            add("1x2", (row["home"], "Draw", row["away"]),
                P.soccer_probs(row["home"], row["away"]))
            over = P.total_probs_over(row["home"], row["away"], 2.5)
            add("total", ("Over", "Under"), (over, 1.0 - over))
        elif sport == "nfl":
            home_p = P.nfl_probs(row["home"], row["away"])
            add("moneyline", (row["home"], row["away"]), (home_p, 1.0 - home_p))
            over = P.nfl_total(row["home"], row["away"])
            add("total", ("Over", "Under"), (over, 1.0 - over))
        else:
            home_p = P.nfl_probs(row["home"], row["away"])
            add("moneyline", (row["home"], row["away"]), (home_p, 1.0 - home_p))
            base, scale, line = {
                "nba": (222.0, 12.0, 215.5),
                "mlb": (8.6, 1.6, 8.5),
                "nhl": (6.2, 1.2, 5.5),
            }[sport]
            over = P.points_total_over(row["home"], row["away"], base, scale, line)
            add("total", ("Over", "Under"), (over, 1.0 - over))
        return out

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
