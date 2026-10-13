"""Fetch real fixtures + odds from a public feed into the demo showcase.

Proves the sports surface can run on live data, read-only, no keys, no
vendor contract. Same shape as /api/sports; provenance recorded per fixture
so nothing looks like it came from a licensed feed when it did not.
"""
import json, ssl, urllib.request
from datetime import datetime, timezone

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0",
      "Accept": "application/json,text/plain,*/*"}

FEEDS = {
    "bra.1": "https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard",
    "ita.1": "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard",
    "nfl": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
}

KIND = {"bra.1": "1x2", "ita.1": "1x2", "nfl": "spreads"}

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _decimal(american):
    """American moneyline -> decimal odds: +235 -> 3.35, -140 -> 1.71."""
    if american > 0:
        return round(1.0 + american / 100.0, 4)
    return round(1.0 + 100.0 / abs(american), 4)


def _price(node):
    """Pull a price out of the several shapes ESPN uses.

    Flat `{"moneyLine": 235}`, nested `{"home": {"close": {"odds": "+105"}}}`,
    and bare american strings all appear in the same payloads.
    """
    if node is None:
        return None
    if isinstance(node, dict):
        for key in ("close", "moneyLine", "odds"):
            if key in node:
                found = _price(node[key])
                if found is not None:
                    return found
        return None
    if isinstance(node, str):
        node = node.strip().lstrip("+")
        if not node.lstrip("-").isdigit():
            return None
    try:
        return _decimal(float(node))
    except (TypeError, ValueError):
        return None


def markets_for(book, teams):
    """Extract 1x2 and total markets from one bookmaker payload.

    One bookmaker per market, never mixed: `overUnder` belongs to whichever
    book supplied the prices, so reading it from a different one would
    describe two bookmakers in a single row.
    """
    found = []
    home = teams.get("home") or "home"
    away = teams.get("away") or "away"
    moneyline = book.get("moneyline")
    if isinstance(moneyline, dict):
        legs = [(home, _price(moneyline.get("home"))),
                ("Draw", _price(moneyline.get("draw"))),
                (away, _price(moneyline.get("away")))]
    else:
        legs = [(home, _price(book.get("homeTeamOdds"))),
                ("Draw", _price(book.get("drawOdds"))),
                (away, _price(book.get("awayTeamOdds")))]
    priced = [(name, price) for name, price in legs if price is not None]
    if len(priced) >= 2:
        found.append({"kind": "1x2", "selections": [n for n, _ in priced],
                      "prices": [p for _, p in priced], "line": None})
    total = book.get("overUnder")
    if total is not None:
        over, under = _price(book.get("overOdds")), _price(book.get("underOdds"))
        if over and under:
            found.append({"kind": "total", "selections": ["Over", "Under"],
                          "prices": [over, under], "line": total})
        else:
            # line without prices: carry the line, not a fake 0.00 odd
            found.append({"kind": "total", "selections": ["Over", "Under"],
                          "prices": [], "line": total})
    return found


def parse(comp_id, data):
    """Return [{fixture, markets}] from one scoreboard payload."""
    rows = []
    for event in data.get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        teams = {t.get("homeAway"): (t.get("team") or {}).get("displayName")
                 for t in (comp.get("competitors") or [])}
        markets, provider = [], None
        for book in (comp.get("odds") or []):
            provider = (book.get("provider") or {}).get("name")
            found = markets_for(book, teams)
            if found:
                markets = found
                break
        if not markets:
            for book in (comp.get("odds") or []):
                provider = (book.get("provider") or {}).get("name")
                for det in (book.get("details") or []):
                    if not isinstance(det, str):
                        continue
                    prices = []
                    for piece in det.split(","):
                        bits = piece.rsplit(" ", 1)
                        if len(bits) == 2:
                            try:
                                prices.append((bits[0].strip(),
                                               _decimal(float(bits[1]))))
                            except ValueError:
                                continue
                    if len(prices) >= 2:
                        markets = [{"kind": "1x2",
                                    "selections": [n for n, _ in prices],
                                    "prices": [p for _, p in prices],
                                    "over_under": None}]
                        break
                if markets:
                    break
        fixture = {
            "key": event.get("id"),
            "competition": comp_id,
            "home": teams.get("home"),
            "away": teams.get("away"),
            "kickoff": event.get("date"),
            "status": ((event.get("status") or {}).get("type") or {}).get("name"),
        }
        for market in markets:
            market["provider"] = provider
        rows.append({"fixture": fixture, "markets": markets})
    return rows


def collect():
    out, errors = [], []
    for comp_id, url in FEEDS.items():
        try:
            out.extend(parse(comp_id, fetch(url)))
        except Exception as exc:
            errors.append({"feed": comp_id, "error": f"{type(exc).__name__}: {exc}"})
    return out, errors


if __name__ == "__main__":
    rows, errs = collect()
    stamped = {"provenance": "public ESPN site.api scoreboard, read-only, no key",
               "licensed_feed": False,
               "note": "public aggregation endpoint; NOT a commercial sports data "
                       "rights licence (Portaria 722/2024 requires official data rights)",
               "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "fixtures": rows, "errors": errs}
    with open("probes/live-fixtures.json", "w", encoding="utf-8") as fh:
        json.dump(stamped, fh, ensure_ascii=False, indent=2)
    priced = [r for r in rows if any(m["prices"] for m in r["markets"])]
    print(f"fixtures={len(rows)} with_odds={len(priced)} errors={len(errs)}")
    for r in rows[:6]:
        f = r["fixture"]
        summary = " | ".join(f"{m['kind']}:{m['selections']}={m['prices']}"
                             for m in r["markets"]) or "sem odds"
        print(" ", f["competition"], f["home"], "x", f["away"],
              (f["kickoff"] or "-")[:16], summary)