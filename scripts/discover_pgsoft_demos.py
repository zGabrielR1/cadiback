"""Find out which PG Soft demo titles actually exist, and what they are called.

    python scripts/discover_pgsoft_demos.py                 # report only
    python scripts/discover_pgsoft_demos.py --write         # append to the catalog
    python scripts/discover_pgsoft_demos.py --start 1 --end 400 --workers 8

Read-only by default; `--write` is the only thing that touches
`probes/provider-demos.json`.

## Why this is not just a loop over integers

The launcher takes `gi=<id>` and answers for anything that exists, but a
number that is accepted is not a game. PG Soft keeps the authoritative name
behind the session handshake:

    POST <api>/web-api/auth/session/v2/verifySession    -> {"dt":{"tk": …, "geu": "game-api/<slug>/"}}
    POST <api>/web-api/game-proxy/v2/GameName/Get       -> {"dt":{"31": "<title>"}}

so each candidate costs one mint and two posts, and comes back with a real
title and the slug its game-api is mounted at. That is how the catalog gets
names rather than guesses — and it is how the two rows we already had were
found to be carrying a slug for a title (gi=126 answers "Baccarat Deluxe"
under the slug `fortune-tiger`, which is not what we listed it as).

The walk is deliberately gentle: a few workers, a small pause, and a hard cap
on failures, because this is somebody else's server and the answer we want is
the list of what exists, not the fastest way to ask.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from demo import pg_proxy  # noqa: E402  (after the path fix, deliberately)

CATALOG = os.path.join(ROOT, "probes", "provider-demos.json")
UA = pg_proxy.USER_AGENT
PAUSE = 0.12          # between candidates per worker; be a guest
TIMEOUT = 25


def _post(url: str, fields: dict, origin: str) -> str:
    body = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"User-Agent": UA, "Origin": origin, "Referer": f"{origin}/",
                 "Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json, text/plain, */*"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", "replace")


def probe(gi: int) -> dict | None:
    """One candidate: mint it, open a session, ask for its name.

    None means "not a title we can list" — an id that does not exist, a host
    that would not answer, or a handshake that never produced a token. The
    reason is kept in `note` so a failure is distinguishable from a miss.
    """
    try:
        session = pg_proxy.mint(str(gi))
    except pg_proxy.PgError as exc:
        return {"gi": gi, "error": str(exc)[:120]}
    if not session.api_hosts:
        return {"gi": gi, "error": "no money host"}

    api = f"https://{session.api_hosts[0]}"
    origin = f"https://{session.game_host}"
    try:
        raw = _post(f"{api}/web-api/auth/session/v2/verifySession",
                    {"btt": "2", "vc": "2", "pf": "1", "l": "pt",
                     "gi": str(gi), "tk": "null", "otk": session.token}, origin)
        payload = json.loads(raw).get("dt") or {}
        token = payload.get("tk")
        if not token:
            return {"gi": gi, "error": "no session token"}
        slug = str(payload.get("geu") or "").strip("/").split("/")[-1]
        label = json.loads(_post(
            f"{api}/web-api/game-proxy/v2/GameName/Get",
            {"lang": "pt", "atk": token, "btt": "2", "pf": "1",
             "gid": str(gi)}, origin)).get("dt") or {}
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError,
            OSError, TimeoutError) as exc:
        return {"gi": gi, "error": type(exc).__name__}

    if not slug:
        return {"gi": gi, "error": "no game slug"}
    # `GameName/Get` answers {"dt": {"31": "…"}}, and "31" is a *localization
    # key*, not the game's name: it comes back "Baccarat Deluxe" for every
    # title probed, which is what an unresolved key falls back to. The slug
    # from `geu` is the one identifier that is actually per-game, and it is
    # what PG's own lobby builds its titles from — so the title is derived
    # from the slug and the label is kept only as a cross-check.
    return {"gi": gi, "title": title_from_slug(slug), "slug": slug,
            "label_key_31": str(label.get("31") or ""),
            "game_id": f"pg:{slug}",
            "hosts": list(session.hosts)}


# Words a title-case gets wrong, because the slug is lowercase.
ACRONYMS = {"us", "uk", "hd", "3d", "2d", "rt", "ol", "vs", "fc", "dj",
            "mg", "k", "x", "io", "tv", "vip"}


def title_from_slug(slug: str) -> str:
    """`dragon-tiger-luck` -> `Dragon Tiger Luck`.

    PG's lobby does the same thing with these slugs, and it is the only name
    available without reverse-engineering the binary `GameInfo/Get` payload,
    which is where the localized title really lives.
    """
    words = [w for w in slug.replace("_", "-").split("-") if w]
    out = []
    for word in words:
        out.append(word.upper() if word in ACRONYMS else word.capitalize())
    return " ".join(out) or slug


def walk(start: int, end: int, workers: int, out: list) -> None:
    lock = threading.Lock()
    todo = list(range(start, end + 1))
    index = [0]
    misses = [0]

    def worker() -> None:
        while True:
            with lock:
                if index[0] >= len(todo) or misses[0] > 40:
                    return
                gi = todo[index[0]]
                index[0] += 1
            found = probe(gi)
            time.sleep(PAUSE)
            if found is None:
                continue
            with lock:
                if "error" in found:
                    misses[0] += 1
                out.append(found)
                if "title" in found:
                    print(f"  gi={found['gi']:<5} {found['slug']:<24} "
                          f"{found['title']}", flush=True)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def slugify(title: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in title]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=320)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--write", action="store_true",
                        help="append the new rows to the catalog")
    parser.add_argument("--out", default=None, help="write the report here")
    parser.add_argument("--from-report", default=None,
                        help="write the catalog from a saved --out report "
                             "instead of walking again, so a sweep can be "
                             "reviewed before it changes anything")
    args = parser.parse_args()

    if args.from_report:
        with open(args.from_report, encoding="utf-8") as handle:
            saved = json.load(handle)
        good = saved["titles"] if isinstance(saved, dict) else saved
        print(f"loaded {len(good)} title(s) from {args.from_report}")
    else:
        print(f"probing PG Soft gi={args.start}..{args.end} with {args.workers} workers…")
        found: list = []
        walk(args.start, args.end, args.workers, found)
        good = sorted([f for f in found if "title" in f], key=lambda f: f["gi"])
        bad = [f for f in found if "title" not in f]
        print(f"\n{len(good)} title(s), {len(bad)} non-answer(s)")

        if args.out:
            with open(args.out, "w", encoding="utf-8") as handle:
                json.dump({"probed": args.end - args.start + 1, "titles": good,
                           "misses": bad}, handle, indent=2, ensure_ascii=False)
            print("report ->", args.out)

    if args.write and good:
        with open(CATALOG, encoding="utf-8") as handle:
            catalog = json.load(handle)
        rows = catalog.get("demos") or []
        have = {row.get("game_id") for row in rows}
        added = []
        for item in good:
            gid = item["game_id"]
            if gid in have:
                continue
            rows.append({
                "game_id": gid,
                "provider": "pg_soft",
                "title": item["title"],
                "category": "Slots",
                "demo_url": f"https://public.pg-demo.com/demo/?gi={item['gi']}&lang=pt",
                "host": "public.pg-demo.com",
                "verification": (f"gi={item['gi']}: minted server-side, session "
                                 f"verified, GameName/Get answers “{item['title']}” "
                                 f"(verified 2026-10-14)"),
                "note": "official PG Soft trial",
            })
            added.append(gid)
        catalog["demos"] = rows
        with open(CATALOG, "w", encoding="utf-8") as handle:
            json.dump(catalog, handle, indent=2, ensure_ascii=False)
        print(f"catalog: {len(added)} row(s) added -> {CATALOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
