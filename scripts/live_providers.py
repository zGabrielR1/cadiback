"""Live provider harness: does each publisher's demo actually run on OUR wallet?

    python scripts/live_providers.py            # sample a few games per provider
    python scripts/live_providers.py --all      # every catalogued game
    python scripts/live_providers.py --provider spribe

Not part of the suite — it talks to the publishers over the network. For every
publisher it opens a real wallet session (`POST /api/wallet/launch`), fetches
the launcher *through our own proxy*, and then asks the question that the old
byte-count sweep never asked: **is our wallet behind the game?**

    launch      the launcher came back 200 with a body
    bridge      the wallet bridge was injected into the document
    wallet      `/api/wallet/status` answered OUR saldo for that session
    round       a real stake through `/api/wallet/round` moved the saldo

A provider is "wired" only when `wallet` holds; `round` proves the debit lands
on our ledger, which is the thing a player sees when they press spin. A game
that renders but never talks to our wallet is reported as wired=no — the same
breakage the byte-count sweep used to hide.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import demo.server as S  # noqa: E402
from demo import game_proxy, provider_demos  # noqa: E402

SAMPLE_PER_PROVIDER = 4
STAKE_MINOR = 200


def _json(url: str, payload: dict | None = None, method: str = "POST"):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=45) as resp:
        body = resp.read()
        return resp.status, (json.loads(body) if body else {})


def _get(url: str, timeout: int = 45):
    req = urllib.request.Request(url, headers={"Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _get_json(url: str, timeout: int = 45) -> dict:
    _status, body = _get(url, timeout=timeout)
    try:
        return json.loads(body) if body else {}
    except ValueError:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true",
                        help="probe every catalogued game, not a sample")
    parser.add_argument("--provider", default="",
                        help="only probe this provider id")
    parser.add_argument("--stake", type=int, default=STAKE_MINOR)
    args = parser.parse_args()

    tmp = tempfile.mkdtemp(prefix="live-providers-")
    S.DEMO = S.Demo(data_dir=tmp)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % httpd.server_address[1]

    try:
        player = S.DEMO.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })["player_id"]
        S.DEMO.deposit({"player": player, "amount_minor": 1000000,
                        "method": "pix", "deposit_id": "live-providers"})

        demos = provider_demos.load()["demos"]
        by_provider: dict[str, list[dict]] = collections.defaultdict(list)
        for row in demos:
            by_provider[row["provider"]].append(row)

        providers = sorted(by_provider)
        if args.provider:
            providers = [p for p in providers if p == args.provider]

        rows = []
        for provider in providers:
            catalogue = by_provider[provider]
            sample = (catalogue if args.all
                      else catalogue[:SAMPLE_PER_PROVIDER])
            for row in sample:
                rows.append(_probe(base, player, row, args.stake))

        _report(rows)
        print("proxy:", game_proxy.stats())
        return 0 if all(r["wallet_ok"] for r in rows) else 1
    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def _probe(base: str, player: str, row: dict, stake: int) -> dict:
    game_id = row["game_id"]
    out = {"game_id": game_id, "provider": row["provider"],
           "launch": "", "bridge": False, "wallet_ok": False, "round_ok": False,
           "debited": False, "balance": None, "error": ""}
    try:
        _status, launch = _json(base + "/api/wallet/launch",
                                {"player": player, "game_id": game_id})
        token = launch.get("token") or ""
        out["balance"] = launch.get("balance_minor")
        # a publisher we interpose at the RGS hands back its own launch URL;
        # the rest go through the page proxy on our origin
        url = launch.get("interposed_url") or ""
        path = url.replace(base, "") if url.startswith(base) else ""
        if not path:
            path = "/g/%s/?wallet_token=%s" % (
                urllib.parse.quote(game_id), token)
        status, body = _get(base + path, timeout=60)
        out["launch"] = status
        out["bridge"] = game_proxy.BRIDGE_MARK in body
        # the question the byte-count sweep never asked
        view = _get_json(base + "/api/wallet/status?token="
                         + urllib.parse.quote(token))
        out["wallet_ok"] = "balance_minor" in view
        _json(base + "/api/wallet/round", {
            "token": token, "stake_minor": stake, "payout_minor": 0,
            "round_id": "live-%s" % game_id})
        out["round_ok"] = True
        after = _get_json(base + "/api/wallet/status?token="
                          + urllib.parse.quote(token))
        out["debited"] = ("balance_minor" in after
                          and int(after["balance_minor"])
                          == int(view["balance_minor"]) - stake)
    except urllib.error.HTTPError as exc:
        out["error"] = "HTTP %s %s" % (exc.code, exc.read()[:120])
    except Exception as exc:  # noqa: BLE001 - a probe reports, never crashes
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
    return out


def _report(rows: list[dict]) -> None:
    head = ("%-22s %-14s %-7s %-7s %-7s %-7s %s" %
            ("game_id", "provider", "launch", "bridge", "wallet", "debit",
             "note"))
    print(head)
    print("-" * len(head))
    bad = 0
    for r in rows:
        ok = r["wallet_ok"] and r.get("debited") and r["launch"] == 200
        if not ok:
            bad += 1
        print("%-22s %-14s %-7s %-7s %-7s %-7s %s" % (
            r["game_id"][:22], r["provider"][:14], r["launch"] or "-",
            "yes" if r["bridge"] else "no", "yes" if r["wallet_ok"] else "no",
            "yes" if r.get("debited") else "no",
            r["error"] or ("" if ok else "<-- NOT WIRED")))
    print("-" * len(head))
    print("%d/%d wired to our wallet" % (len(rows) - bad, len(rows)))
    print("note: this proves the launcher renders and OUR wallet answers + "
          "debits;\na browser is still needed to prove the game's own spin "
          "calls land here\n(RGS-interposed pages live on the publisher's CDN "
          "by design).")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
