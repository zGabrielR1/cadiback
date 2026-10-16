"""In-house odds delivery engine. Dog food: the house prices its own
book instead of depending on a third-party feed. Deterministic per 30s
bucket so every request in the same bucket returns identical prices,
while a live fixture's prices breathe on the bucket clock.

Model: per-team deterministic strength -> Poisson win/draw/loss and
totals probabilities -> uniform-margin book prices. Live fixtures add a
minute-scaled drift on top. Provenance is explicit: nothing here is
licensed or third-party data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from frame.verticals.sports import pricing as P

ENGINE = "in-house odds engine (deterministic)"
NOTE = ("cotações geradas internamente (motor próprio); vitrine "
        "read-only — não é direito oficial de dados esportivos")

COMPS = {
    "bra.1": {"sport": "soccer", "country": "Brasil",
              "label": "Brasileir\u00e3o S\u00e9rie A",
              "hours": (16, 18, 21), "duration": 105},
    "ita.1": {"sport": "soccer", "country": "It\u00e1lia", "label": "Serie A",
              "hours": (13, 16, 19), "duration": 105},
    "nfl": {"sport": "football", "country": "EUA", "label": "NFL",
            "hours": (13, 17, 21), "duration": 195},
}

TEAMS = {
    "bra.1": ["São Paulo", "Santos", "Fluminense", "Flamengo", "Corinthians",
              "Palmeiras", "Vasco", "Grêmio", "Internacional", "Atlético-MG"],
    "ita.1": ["Genoa", "Fiorentina", "Internazionale", "Parma", "Napoli",
              "Frosinone", "Juventus", "Milan", "Roma", "Lazio"],
    "nfl": ["Cleveland Browns", "Pittsburgh Steelers", "Washington Commanders",
            "Indianapolis Colts", "Buffalo Bills", "New England Patriots",
            "Chicago Bears", "New York Jets", "Cincinnati Bengals",
            "Jacksonville Jaguars", "New York Giants", "Arizona Cardinals",
            "Philadelphia Eagles", "Los Angeles Rams", "Tampa Bay Buccaneers",
            "Green Bay Packers"],
}

MARGIN = P.MARGIN

_hash = P._hash
_poisson = P._poisson
team_strength = P.team_strength
soccer_probs = P.soccer_probs
total_probs_over = P.total_probs_over
nfl_probs = P.nfl_probs
nfl_total = P.nfl_total
_to_price = P.to_price


def _drift(seed_key: str, bucket: int, minute: float) -> float:
    return P.drift(seed_key, bucket, minute)


def _status(kickoff: datetime, now: datetime, duration: int) -> str:
    if now < kickoff:
        return "STATUS_SCHEDULED"
    if now < kickoff + timedelta(minutes=duration):
        return "IN_PROGRESS"
    return "STATUS_FINAL"


def _pairings(comp: str, day: str) -> list[tuple[str, str]]:
    teams = sorted(TEAMS[comp], key=lambda t: _hash(f"{day}|{comp}|{t}"))
    return [(teams[i], teams[i + 1]) for i in range(0, len(teams) - 1, 2)]


def _fixture(comp: str, home: str, away: str, date: str, hour: int,
             now: datetime) -> dict | None:
    kickoff = datetime.strptime(date, "%Y-%m-%d").replace(
        hour=hour, tzinfo=timezone.utc)
    if kickoff + timedelta(minutes=COMPS[comp]["duration"]) <= now:
        return None  # finished games leave the board
    minute = max(0.0, (now - kickoff).total_seconds() / 60.0)
    status = _status(kickoff, now, COMPS[comp]["duration"])
    markets = []

    def add(kind, selections, probs, line=None):
        prices = []
        for i, prob in enumerate(probs):
            ratio = 1.0 + _drift(f"{comp}:{home}:{away}:{kind}:{i}",
                                 int(now.timestamp()) // 30,
                                 minute if status == "IN_PROGRESS" else 0.0)
            prices.append(max(1.01, round(_to_price(prob) * ratio, 2)))
        markets.append({
            "key": f"{comp}:{date}:{home}-{away}:{kind}",
            "kind": kind,
            "selections": list(selections),
            "prices": prices,
            "provider": ENGINE,
            "line": line,
        })

    if COMPS[comp]["sport"] == "soccer":
        add("1x2", (home, "Draw", away), soccer_probs(home, away))
        add("total", ("Over", "Under"),
            (total_probs_over(home, away, 2.5),
             1.0 - total_probs_over(home, away, 2.5)), line=2.5)
    else:
        hp = nfl_probs(home, away)
        add("moneyline", (home, away), (hp, 1.0 - hp))
        over = nfl_total(home, away)
        add("total", ("Over", "Under"), (over, 1.0 - over), line=44.5)

    return {
        "key": f"{comp}:{date}:{home}-{away}",
        "sport": COMPS[comp]["sport"],
        "country": COMPS[comp]["country"],
        "competition": COMPS[comp]["label"],
        "home": home,
        "away": away,
        "kickoff": kickoff.isoformat(timespec="minutes").replace("+00:00", "Z"),
        "status": status,
        "home_score": None,
        "away_score": None,
        "progress": "",
        "markets": markets,
    }


def build(now: datetime | None = None) -> dict:
    """The full delivery payload, same envelope as /api/sports."""
    now = now or datetime.now(timezone.utc)
    fixtures = []
    for offset in (0, 1, 2):
        day = (now - timedelta(days=1) + timedelta(days=offset)).strftime("%Y-%m-%d")
        # one day back, today, tomorrow: the board always has a game on
        for comp, cfg in COMPS.items():
            pairings = _pairings(comp, day)
            for i, (home, away) in enumerate(pairings):
                hour = cfg["hours"][i % len(cfg["hours"])]
                fix = _fixture(comp, home, away, day, hour, now)
                if fix:
                    fixtures.append(fix)
    fixtures.sort(key=lambda f: f["kickoff"])
    return {
        "fixtures": fixtures,
        "source": "inhouse",
        "provider": ENGINE,
        "licensed_feed": False,
        "fetched_at": now.isoformat(timespec="seconds"),
        "errors": [],
        "note": NOTE,
    }
