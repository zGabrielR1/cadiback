"""Discover and verify Hacksaw free-play demos for the lobby catalog.

The lobby's Hacksaw rows are the real publisher demos. A demo URL is
`static-live.hacksawgaming.com/<gameid>/<version>/index.html?...&mode=2`, so
two facts are needed per title: the product id (from Hacksaw's own games
page) and the build version (from each game's `version.json`) — the launcher
itself resolves the version that way.

Read-only GETs, no auth, no bypass. A row is only reported when both the
launcher and the publisher RGS answer for it.

    python scripts/discover_hacksaw_demos.py            # report
    python scripts/discover_hacksaw_demos.py --write    # append new rows

`--write` adds rows that are not already in probes/provider-demos.json
(matched by game_id); it never edits or removes existing rows.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "probes", "provider-demos.json")

GAMES_PAGE = "https://www.hacksawgaming.com/games/"
STATIC = "https://static-live.hacksawgaming.com"
RGS = "https://rgs-demo.hacksawgaming.com/api/meta/gameInfo"
HOST = "static-live.hacksawgaming.com"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
CTX = ssl.create_default_context()

CARD = re.compile(
    r'<li class="GridListItem" data-gameid="(\d+)" '
    r'aria-label="([^"]*?) \| casino game image"')


def _get(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25, context=CTX) as resp:
        return resp.status, resp.read()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def demo_url(gameid: str, version: str) -> str:
    return (f"{STATIC}/{gameid}/{version}/index.html?language=pt"
            f"&channel=desktop&gameid={gameid}&mode=2&token=demo&lobbyurl="
            f"&env=https://rgs-demo.hacksawgaming.com/api&alwaysredirect=true")


def listed() -> list[dict]:
    _, body = _get(GAMES_PAGE)
    rows, seen = [], set()
    for gameid, title in CARD.findall(body.decode("utf-8", "replace")):
        if gameid in seen:
            continue
        seen.add(gameid)
        rows.append({"gameid": gameid, "title": html.unescape(title).strip()})
    return rows


def verify(row: dict) -> dict:
    try:
        _, body = _get(f"{STATIC}/{row['gameid']}/version.json")
        row["version"] = json.loads(body.decode()).get("version", "")
    except Exception as exc:
        row["version"] = ""
        row["error"] = type(exc).__name__
    if not row["version"]:
        row["ok"] = False
        return row
    row["demo_url"] = demo_url(row["gameid"], row["version"])
    try:
        row["launcher"] = _get(row["demo_url"])[0]
    except Exception as exc:
        row["launcher"] = type(exc).__name__
    try:
        _, body = _get(f"{RGS}?gameId={row['gameid']}&currency=EUR&rm=96"
                       f"&jurisdiction=curacao&partner=demo")
        row["rgs"] = 200
        row["rtp"] = json.loads(body.decode()).get("data", {}).get("rtp")
    except Exception as exc:
        row["rgs"] = type(exc).__name__
    row["ok"] = row["launcher"] == 200 and row["rgs"] == 200
    return row


def catalog_row(row: dict) -> dict:
    return {
        "game_id": "hs:" + slug(row["title"]),
        "provider": "hacksaw_gaming",
        "title": row["title"],
        "category": "Slots",
        "demo_url": row["demo_url"],
        "host": HOST,
        "verification": (f"product id {row['gameid']} and build "
                         f"{row['version']} free-play mode"),
        "note": "official Hacksaw demo",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="append verified new rows to the catalog")
    args = ap.parse_args()

    candidates = listed()
    print(f"listed on the publisher's games page: {len(candidates)}")
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(verify, candidates))
    verified = [r for r in rows if r["ok"]]
    print(f"verified (launcher + RGS answered): {len(verified)} / {len(rows)}")
    for r in rows:
        if not r["ok"]:
            print(f"  skip {r['gameid']:>5} {r['title'][:34]:36} "
                  f"launcher={r['launcher']} rgs={r['rgs']}")

    if not args.write:
        return
    with open(CATALOG, encoding="utf-8") as handle:
        catalog = json.load(handle)
    known = {r["game_id"] for r in catalog["demos"]}
    added = []
    for row in verified:
        entry = catalog_row(row)
        if entry["game_id"] in known:
            continue
        known.add(entry["game_id"])
        added.append(entry)
    catalog["demos"].extend(added)
    catalog["provenance"]["verified_at"] = _today()
    with open(CATALOG, "w", encoding="utf-8") as handle:
        json.dump(catalog, handle, ensure_ascii=False, indent=1)
    print(f"added {len(added)} rows; catalog now {len(catalog['demos'])}")
    print("run `python scripts/make-covers.py` and rebuild web/ afterwards")


def _today() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).date().isoformat()


if __name__ == "__main__":
    main()
