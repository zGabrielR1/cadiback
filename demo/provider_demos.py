"""Real provider-demo catalog: the publisher's own bytes, on the publisher's own host.

The lobby's official content is not ours to rehost. Each row points at a URL the
publisher serves itself for free play (Pragmatic Play, PG Soft, Hacksaw Gaming,
Play'n GO, Evolution). We scrape the *facts* (title, provider, demo URL) and open
the publisher's page; the game bytes, artwork, and RNG stay on their server.

Two hard rules, both enforced here rather than trusted to the file:

1. https only. A plain-http demo URL would be trivially hijackable.
2. Host allowlist. A row that points anywhere except a known publisher demo host
   is dropped, so a re-upload or a look-alike can never enter the lobby through
   this path.

Wallet isolation is structural: these rows are non-launchable against our books
and carry `wallet_isolated: true`, so no stake or payout can route through them.
"""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ROOT)
DEFAULT_PATH = os.path.join(REPO, "probes", "provider-demos.json")

# Publisher free-play hosts, verified 2026-10-04. Only these may appear.
DEMO_HOSTS: frozenset[str] = frozenset({
    "demogamesfree.pragmaticplay.net",
    "demogamesfree-asia.pragmaticplay.net",
    "m.pgsoft-games.com",
    "static.pgsoft-games.com",
    "public.pg-demo.com",
    "static-live.hacksawgaming.com",
    "asccw.playngonetwork.com",
    "released.playngonetwork.com",
    "games.evolution.com",
    "demo.spribe.io",
    "spribe.co",
})


def _accept(row: object) -> dict | None:
    """One validated lobby row, or None if it fails a hard rule."""
    if not isinstance(row, dict):
        return None
    game_id = str(row.get("game_id") or "").strip()
    provider = str(row.get("provider") or "").strip()
    title = str(row.get("title") or "").strip()
    demo_url = str(row.get("demo_url") or "").strip()
    if not (game_id and provider and title and demo_url):
        return None
    parsed = urlparse(demo_url)
    if parsed.scheme != "https":
        return None  # never ship a cleartext launch URL
    if parsed.hostname not in DEMO_HOSTS:
        return None  # not a publisher demo host: refuse to list it
    return {
        "game_id": game_id,
        "provider": provider,
        "title": title,
        "category": str(row.get("category") or "Slots"),
        "demo_url": demo_url,
        "host": parsed.hostname,
        "verification": row.get("verification"),
        "note": row.get("note"),
        "cover": row.get("cover"),
        "launchable": False,       # never against our books
        "wallet_isolated": True,   # the publisher's server holds the money
        "embed": True,             # embedded in site iframe player
        "source": "provider",
    }


def load(path: str | None = None) -> dict:
    """Return the provider-demo block. A bad file degrades to an error status."""
    target = path or DEFAULT_PATH
    if not os.path.isfile(target):
        return {"status": "no provider-demo catalog on disk", "demos": []}
    try:
        with open(target, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        return {"status": f"catalog error: {exc}", "demos": []}
    rows = payload.get("demos") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {"status": "catalog error: no demos list", "demos": []}
    demos = [row for row in (_accept(r) for r in rows) if row is not None]
    dropped = len(rows) - len(demos)
    status = f"{len(demos)} publisher-hosted demos (wallet-isolated)"
    if dropped:
        status += f"; {dropped} row(s) dropped (not https or unknown host)"
    return {"status": status, "demos": demos}
