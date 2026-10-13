"""Live-sports capture loader. Read-only facts about the probes/ capture
(capture date, fixture count) surface in the news panel and admin.

Pricing moved in-house (decision 0016): see `demo/odds_engine.py`.
"""

from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ROOT)
LIVE_PATH = os.path.join(REPO, "probes", "live-fixtures.json")


def live_available() -> bool:
    return os.path.isfile(LIVE_PATH)


def load_live() -> dict | None:
    if not live_available():
        return None
    try:
        with open(LIVE_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (ValueError, OSError):
        return None
