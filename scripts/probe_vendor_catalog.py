"""Probe public, keyless vendor catalog endpoints. Read-only single GETs, no
auth, no bypass. Records what a casino catalog could actually consume from
this machine without a signed aggregator. Writes probes/vendor-catalog.json.

Anything keyless and official becomes a candidate source for non-launchable
vendor rows (provenance-stamped, never launchable before BR certs). Anything
key-gated stays a contract blocker, documented with its response.
"""
import json
import os
import re
import ssl
import urllib.request
from datetime import datetime, timezone

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/126.0",
      "Accept": "text/html,application/json,*/*",
      "Accept-Language": "pt-BR,pt;q=0.9"}

TARGETS = [
    # Provider game-fact pages: verify the stub's three fixture rows.
    ("pragmatic-games", "https://www.pragmaticplay.com/en/games/"),
    ("pragmatic-demo-lobby", "https://demogamesfree.pragmaticplay.net/"),
    ("evolution-lightning-roulette", "https://www.evolution.com/games/lightning-roulette/"),
    ("pgsoft-games", "https://www.pgsoft.com/en/games/"),
    # Aggregator public surface: is there any keyless catalog at all?
    ("everymatrix-casinoengine", "https://everymatrix.com/casinoengine/"),
    ("softswiss-aggregator", "https://www.softswiss.com/game-aggregator/"),
    ("hub88", "https://hub88.io/"),
]

# Figures the stub currently claims. A match here is evidence, citable in the
# transcript; a miss means the figure stays an unverified fixture value.
FIGURE_PATTERNS = ["96.50", "96,50", "96.5", "97.30", "97,30", "97.00",
                   "888", "Gates of Olympus", "Lightning Roulette",
                   "RTP", "RTP:"]

ctx = ssl.create_default_context()
out = {"probed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
       "note": "single GET each, no auth, no bypass; HTML shells noted, not crawled",
       "results": {}}

for name, url in TARGETS:
    row = {"url": url}
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            raw = r.read()
            final = r.geturl()
            row["status"] = r.status
            row["final_url"] = final
            row["bytes"] = len(raw)
            ctype = r.headers.get("Content-Type", "")
            row["content_type"] = ctype
            body = raw[:500000].decode("utf-8", "replace")
            row["json_ok"] = False
            try:
                data = json.loads(body)
                row["json_ok"] = True
                if isinstance(data, dict):
                    row["top_keys"] = sorted(data.keys())[:12]
                else:
                    row["list_len"] = len(data) if isinstance(data, list) else None
            except ValueError:
                pass
            if not row["json_ok"]:
                title = re.search(r"<title>(.*?)</title>", body, re.S | re.I)
                row["title"] = (title.group(1).strip()[:120]
                                if title else None)
                low = body.lower()
                row["looks_js_shell"] = ("<div id=\"root\"" in body or "id=\"app\"" in body
                                         or "__NEXT_DATA__" in body or "ng-app" in body
                                         or len(body) < 15000)
                hits = {}
                for pat in FIGURE_PATTERNS:
                    n = low.count(pat.lower())
                    if n:
                        hits[pat] = n
                row["figure_hits"] = hits
        row["ok"] = True
    except Exception as exc:
        row["ok"] = False
        row["error"] = f"{type(exc).__name__}: {exc}"
    out["results"][name] = row
    print(("OK " if row.get("ok") else "-- ") + name + " " +
          str(row.get("status", row.get("error", "")))[:80])

os.makedirs("probes", exist_ok=True)
with open("probes/vendor-catalog.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
print("wrote probes/vendor-catalog.json")
