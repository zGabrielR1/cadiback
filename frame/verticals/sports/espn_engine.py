"""EspnSportsEngine: real fixtures from ESPN scoreboards, priced by the
in-house deterministic model (`frame.verticals.sports.pricing`).

Same source as cleanSheet's edgewatch: public scoreboard endpoints,
soccer comps + NFL. Where ESPN actually publishes a moneyline, that price is
served verbatim and tagged `source="market"` — a real number beats a modelled
one — and the rest of the card (spread line, total, halves) stays our own
book, tagged `source="model"`. The two are never mixed silently: the payload
carries the provenance per market, so a model price is never presented as a
provider's. Cache-first, fail-open to the last good snapshot, fail-closed
(ProviderError) when nothing is on disk.
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
from . import marketboard as MB

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
CANON = {"soccer": "soccer", "nfl": "football", "nba": "basketball",
         "mlb": "baseball", "nhl": "hockey"}
ESPN_COUNTRY = {"bra.1": "Brasil", "ita.1": "Itália", "eng.1": "Inglaterra",
                "esp.1": "Espanha", "ger.1": "Alemanha", "fra.1": "França",
                "uefa.champions": "Europa", "nfl": "EUA", "nba": "EUA",
                "mlb": "EUA", "nhl": "EUA"}


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
    leagues = data.get("leagues") or []
    league_name = (leagues[0] or {}).get("name") if leagues else None
    league_name = league_name or comp_id
    for event in data.get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        teams, scores = {}, {}
        for competitor in comp.get("competitors") or []:
            side = competitor.get("homeAway")
            teams[side] = (competitor.get("team") or {}).get("displayName")
            scores[side] = competitor.get("score")
        if not teams.get("home") or not teams.get("away"):
            continue
        state = event.get("status") or {}
        status = (state.get("type") or {}).get("name") or ""
        rows.append({
            "key": str(event.get("id")),
            "competition": league_name,
            "country": ESPN_COUNTRY.get(comp_id, ""),
            "home": teams["home"],
            "away": teams["away"],
            "kickoff": event.get("date") or "",
            "status": status,
            "home_score": _int(scores.get("home")),
            "away_score": _int(scores.get("away")),
            "progress": str(state.get("displayClock") or "").strip(),
            "odds": _espn_odds(comp),
        })
    return rows


def _int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _decimal_moneyline(value: object) -> float | None:
    """A US moneyline (-160 / +135) as decimal odds, or None."""
    try:
        ml = float(value)
    except (TypeError, ValueError):
        return None
    if ml == 0.0:
        return None
    dec = 1.0 + (100.0 / abs(ml)) if ml < 0 else 1.0 + (ml / 100.0)
    if dec <= 1.0:
        return None
    return round(dec, 2)


def _espn_odds(comp: dict) -> dict | None:
    """The published moneyline (and total line), if ESPN carries one.

    ESPN spells a price three ways depending on the sport and the week
    (`moneyline.home.odds`, `homeTeamOdds.moneyLine`, or nothing at all), so
    every shape is tried and a fixture with no usable price simply gets no
    overlay. Only a two-sided moneyline is usable: one side alone is not a book.
    """
    odds = comp.get("odds") or []
    row = odds[0] if odds and isinstance(odds[0], dict) else None
    if not row:
        return None
    out: dict = {}
    ml = row.get("moneyline") if isinstance(row.get("moneyline"), dict) else {}
    home_ml = (ml.get("home") or {}).get("odds") if isinstance(ml.get("home"), dict) else None
    away_ml = (ml.get("away") or {}).get("odds") if isinstance(ml.get("away"), dict) else None
    if home_ml is None:
        home_ml = (row.get("homeTeamOdds") or {}).get("moneyLine")
    if away_ml is None:
        away_ml = (row.get("awayTeamOdds") or {}).get("moneyLine")
    dh, da = _decimal_moneyline(home_ml), _decimal_moneyline(away_ml)
    if dh and da:
        out["moneyline"] = (dh, da)
    ou = row.get("overUnder")
    if isinstance(ou, (int, float)):
        out["total"] = float(ou)
    return out or None


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
                sport=CANON.get(SPORT.get(row["competition"], "soccer"),
                                "soccer"),
                competition=row["competition"],
                country=row.get("country", ""),
                home=row["home"],
                away=row["away"],
                kickoff_date=row["kickoff"],
                status=row["status"],
                home_score=row.get("home_score"),
                away_score=row.get("away_score"),
                progress=row.get("progress") or "",
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
        live = self._live(row)
        minute = self._minute(row) if live else 0.0
        sport = CANON.get(SPORT.get(row["competition"], "soccer"), "soccer")
        model = MB.quote_markets(fixture_key, sport, row["home"], row["away"],
                                 live=live, minute=minute,
                                 home_score=row.get("home_score"),
                                 away_score=row.get("away_score"))
        odds = row.get("odds") or {}
        published = odds.get("moneyline")
        if not published:
            return model
        # a real published moneyline replaces the modelled one; the rest of the
        # card is still ours, and the provenance rides on each market
        real = Market(key=f"{fixture_key}:moneyline", fixture_key=fixture_key,
                      kind="moneyline", selections=(row["home"], row["away"]),
                      prices=(float(published[0]), float(published[1])),
                      line=None, source="market")
        return [real, *[m for m in model if m.kind != "moneyline"]]

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
