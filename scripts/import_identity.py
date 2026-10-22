"""One-time, atomic file -> database identity cutover. Never overwrites rows.

Usage: python -m scripts.import_identity --data-dir demo/data --apply
Apply the SQL migration first. Without --apply this only validates local input.
Stop writes during cutover and keep the signing secret unchanged across deploys.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time


def load_identity(directory):
    directory = Path(directory)

    def read(name):
        path = directory / name
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"invalid identity snapshot: {name}")
        return data

    players = read("players.json")
    links = read("oauth_links.json")
    devices = read("player_sessions.json").get("sessions", {})
    if not isinstance(devices, dict):
        raise ValueError("invalid device snapshot")
    for key, row in players.items():
        if not isinstance(row, dict) or row.get("player_id") != key:
            raise ValueError("invalid player snapshot")
    if any(pid not in players for pid in links.values()):
        raise ValueError("social link references a missing player")
    live = {}
    now = int(time.time())
    for sid, row in devices.items():
        if not isinstance(row, dict):
            raise ValueError("invalid device row")
        player = players.get(row.get("player"))
        if not player or int(row.get("expires", 0)) <= now:
            continue
        if int(row.get("epoch", 0)) != int(player.get("session_epoch", 0)):
            continue
        live[sid] = row
    return players, links, live


def import_identity(factory, players, links, devices):
    from sqlalchemy import select
    from demo.models import IdentityDocument, PlayerDevice

    with factory.begin() as db:
        if db.scalar(select(IdentityDocument.name).limit(1)) is not None or \
                db.scalar(select(PlayerDevice.session_id).limit(1)) is not None:
            raise ValueError("identity database is not empty; import refused")
        db.add_all([
            IdentityDocument(name="players", data=players, revision=0),
            IdentityDocument(name="oauth_links", data=links, revision=0),
            IdentityDocument(name="import_receipt", data={"at": int(time.time())}, revision=0),
        ])
        for sid, row in devices.items():
            db.add(PlayerDevice(session_id=sid, **{
                key: row[key] for key in (
                    "player", "epoch", "created", "seen", "expires", "remember",
                    "user_agent", "ip")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    players, links, devices = load_identity(args.data_dir)
    print(f"Validated: {len(players)} players, {len(links)} links, {len(devices)} live devices")
    if not args.apply:
        print("Dry run; no database connection or writes.")
        return
    from demo.db import database_url, make_engine, make_session_factory, using_postgres
    if not using_postgres():
        raise SystemExit("DATABASE_URL must configure Postgres")
    engine = make_engine(database_url())
    try:
        import_identity(make_session_factory(engine), players, links, devices)
    except Exception as exc:
        # Connection exceptions can include the database DSN; do not print it.
        raise SystemExit(f"Import refused or rolled back ({type(exc).__name__})") from None
    finally:
        engine.dispose()
    print("Committed identity cutover; keep the signing secret unchanged.")


if __name__ == "__main__":
    main()
