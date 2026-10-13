"""Probe live public sports feeds. Read-only, public endpoints, no keys.
Records what a future sportsbook could actually consume from this machine.
Writes probes/live-feeds.json.
"""
import json, os, ssl, sys, urllib.request
from datetime import datetime, timezone

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0",
      "Accept": "application/json,text/plain,*/*",
      "Accept-Language": "pt-BR,pt;q=0.9"}

TARGETS = [
    ("espn-scoreboard-soccer",
     "https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard?dates=20261003"),
    ("espn-scoreboard-football",
     "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"),
    ("espn-core-soccer",
     "https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard"),
    ("football-data-org",
     "https://api.football-data.org/v4/competitions/BRA1/matches"),
    ("openligadb",
     "https://api.openligadb.de/getmatchdata/bla1"),
    ("thesportsdb",
     "https://www.thesportsdb.com/api/v1/json/3/all_leagues.php"),
    ("pix-api-ping", "https://api.bcb.gov.br/pix/"),
]

ctx = ssl.create_default_context()
out = {"probed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
       "results": {}}

for name, url in TARGETS:
    row = {"url": url}
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            raw = r.read()
            row["status"] = r.status
            row["bytes"] = len(raw)
            ctype = r.headers.get("Content-Type", "")
            row["content_type"] = ctype
            body = raw[:400000].decode("utf-8", "replace")
            row["json_ok"] = False
            try:
                data = json.loads(body)
                row["json_ok"] = True
                if isinstance(data, dict):
                    row["top_keys"] = sorted(data.keys())[:12]
                if isinstance(data, list):
                    row["list_len"] = len(data)
                ev = data.get("events") if isinstance(data, dict) else None
                if ev is not None:
                    row["events"] = len(ev)
                    first = ev[0] if ev else {}
                    comp = (first.get("competitions") or [{}])[0]
                    teams = comp.get("competitors") or []
                    row["first_fixture"] = {
                        "name": first.get("name"),
                        "date": first.get("date"),
                        "teams": [t.get("team", {}).get("displayName") for t in teams],
                        "odds_present": bool(comp.get("odds")),
                        "status": (first.get("status") or {}).get("type", {}).get("name"),
                    }
            except ValueError:
                row["json_ok"] = False
                row["head"] = body[:120].replace("\n", " ")
        row["ok"] = True
    except Exception as exc:
        row["ok"] = False
        row["error"] = f"{type(exc).__name__}: {exc}"
    out["results"][name] = row
    flag = "OK " if row.get("ok") and row.get("json_ok") else "-- "
    detail = ""
    if row.get("events") is not None:
        detail = f" events={row['events']} odds={row.get('first_fixture', {}).get('odds_present')}"
    elif row.get("list_len") is not None:
        detail = f" list={row['list_len']}"
    print(flag + name + " " + str(row.get("status", row.get("error", "")))[:70] + detail)

os.makedirs("probes", exist_ok=True)
with open("probes/live-feeds.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
print("wrote probes/live-feeds.json")