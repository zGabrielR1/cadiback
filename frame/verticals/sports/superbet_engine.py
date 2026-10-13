"""SuperbetSportsEngine: real fixtures from Superbet's offer server
(public v3 REST, no key, pt-BR), prices from the in-house model.

Fallback source when ESPN is unreachable: the deterministic slate
should be the last resort, never the first. Superbet's own market
prices are NOT served; every quote is our deterministic book.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .contract import BetReceipt, Fixture, Market, Quote
from . import pricing as P

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
CACHE_PATH = os.path.join(REPO, "probes", "superbet-cache.json")
OFFER = "https://production-superbet-offer-br.freetls.fastly.net"
V3 = OFFER + "/v3/pt-BR"
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
TTL = 600


class ProviderError(RuntimeError):
    pass


def _http(url: str) -> dict:
    """One events answer; a 503 closes its connection (see espn_engine)."""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=15,
                                    context=ssl.create_default_context()) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        exc.close()
        raise


def _split_name(name: str) -> tuple[str, str]:
    for sep in ("\u00d7", "\ufffd", "\u00b7", " vs ", " vs. ", " x ", " - ", "\u2013"):
        if sep in name:
            home, _, away = name.partition(sep)
            return home.strip(), away.strip()
    if " v " in name:
        home, _, away = name.partition(" v ")
        return home.strip(), away.strip()
    return name, ""


def _parse_events(events: list[dict]) -> list[dict]:
    rows = []
    for ev in events:
        fixture = ev.get("fixture") or {}
        if fixture.get("sport_id") != 5:  # soccer only
            continue
        home, away = _split_name(str(fixture.get("event_name") or ""))
        if not home or not away:
            continue
        rows.append({
            "key": str(ev.get("event_id")),
            "competition": f"superbet:{fixture.get('tournament_id', '?')}",
            "home": home,
            "away": away,
            "kickoff": fixture.get("utc_date") or "",
            "status": str(fixture.get("status") or ""),
        })
    return rows


@dataclass
class SuperbetSportsEngine:
    cache_path: str = CACHE_PATH
    ttl_seconds: int = TTL
    fetcher: object = None
    _events: list[dict] = field(default_factory=list)
    accepted: dict[str, BetReceipt] = field(default_factory=dict)
    settled: dict[str, str] = field(default_factory=dict)

    def _window_url(self) -> str:
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        params = urllib.parse.urlencode({
            "startDate": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDate": (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        return f"{V3}/events?{params}"

    def _refresh(self) -> None:
        now = time.time()
        cached = None
        try:
            with open(self.cache_path, "r", encoding="utf-8") as handle:
                cached = json.load(handle)
            if now - float(cached.get("fetched_at", 0)) < self.ttl_seconds \
                    and cached.get("events"):
                self._events = cached["events"]
                return
        except (ValueError, OSError, KeyError):
            pass
        fetch = self.fetcher or _http
        try:
            payload = fetch(self._window_url())
            events = _parse_events(payload.get("events", []))
            if not events:
                raise ProviderError("no soccer events in window")
            self._events = events
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as handle:
                json.dump({"fetched_at": now, "source": "superbet v3 events",
                           "events": events}, handle)
        except Exception:
            if cached and cached.get("events"):
                self._events = cached["events"]
                return
            if self._events:
                return
            raise ProviderError("Superbet unreachable and no cache")

    def fixtures(self) -> list[Fixture]:
        self._refresh()
        return [Fixture(key=f"sb:{r['key']}", sport="soccer",
                        competition=r["competition"], home=r["home"],
                        away=r["away"], kickoff_date=r["kickoff"])
                for r in self._events]

    def _row(self, fixture_key: str) -> dict | None:
        self._refresh()
        for row in self._events:
            if f"sb:{row['key']}" == fixture_key:
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
        status = str(row.get("status") or "")
        return "progress" in status.lower() or "live" in status.lower()

    def markets(self, fixture_key: str) -> list[Market]:
        row = self._row(fixture_key)
        if row is None:
            return []
        bucket = int(time.time()) // 30
        minute = self._minute(row) if self._live(row) else 0.0
        out = []

        def add(kind, selections, probs):
            prices = []
            for i, prob in enumerate(probs):
                ratio = 1.0 + P.drift(f"{fixture_key}:{kind}:{i}", bucket, minute)
                prices.append(max(1.01, round(P.to_price(prob) * ratio, 2)))
            out.append(Market(key=f"{fixture_key}:{kind}",
                              fixture_key=fixture_key, kind=kind,
                              selections=tuple(selections),
                              prices=tuple(prices)))

        add("1x2", (row["home"], "Draw", row["away"]),
            P.soccer_probs(row["home"], row["away"]))
        over = P.total_probs_over(row["home"], row["away"], 2.5)
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
