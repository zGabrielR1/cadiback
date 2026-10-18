"""Throwaway sweep: open one game per provider through the proxy, report.

    python demo/_sweep.py

Not part of the suite — it talks to five publishers over the network. This is
how the proxy's breakage is *found* rather than guessed at: each row is a real
launcher fetched through `/g/`, and the status and byte count say whether the
publisher's page still comes back through us intact.
"""
import collections
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import demo.server as S
from demo import provider_demos

tmp = tempfile.mkdtemp(prefix="sweep-")
S.DEMO = S.Demo(data_dir=tmp)
SEEN = []
_real = S.game_proxy.fetch


def spy(url, *a, **kw):
    SEEN.append(url)
    return _real(url, *a, **kw)


S.game_proxy.fetch = spy
httpd = ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d" % httpd.server_address[1]

demos = provider_demos.load()["demos"]
by_provider = collections.defaultdict(list)
for row in demos:
    by_provider[row["provider"]].append(row)

# pg rows need a minted session, which the catalog URL alone does not carry
player = S.DEMO.upsert_player({
    "name": "Ana Souza", "cpf": "529.982.247-25",
    "pix_key": "ana.souza@example.com",
    "bank": {"bank_code": "001", "agency": "1234",
             "account": "56789-0", "holder_name": "Ana Souza"},
})["player_id"]
S.DEMO.deposit({"player": player, "amount_minor": 100000, "method": "pix"})
launch = S.DEMO.wallet_launch({"player": player, "game_id": "pg:fortune-tiger"})

results = []
for provider, rows in sorted(by_provider.items()):
    sample = rows[:2] if provider != "pg_soft" else rows[:6]
    for row in sample:
        gid = row["game_id"]
        if provider == "pg_soft":
            # each PG launch mints its own session, so the URL has to be built
            # per game rather than reused from a single launch
            path = S.DEMO.interposed_launch(gid, "tok", B).replace(B, "")
            if not path:
                results.append((gid, provider, "no-launch", 0))
                continue
        else:
            path = "/g/%s/?token=x" % gid
        before = len(SEEN)
        try:
            req = urllib.request.Request(B + path)
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
            results.append((gid, provider, r.status, len(body)))
        except urllib.error.HTTPError as e:
            results.append((gid, provider, e.code, len(e.read())))
        except Exception as e:
            results.append((gid, provider, type(e).__name__, 0))

print("%-26s %-14s %-8s %s" % ("game_id", "provider", "status", "bytes"))
print("-" * 64)
bad = 0
for gid, provider, status, size in results:
    ok = status == 200 and size > 0
    if not ok:
        bad += 1
    print("%-26s %-14s %-8s %-9s %s" % (gid, provider, status, size,
                                       "" if ok else "  <-- BROKEN"))
print("-" * 64)
print("%d/%d ok" % (len(results) - bad, len(results)))
print("proxy:", S.game_proxy.stats())

httpd.shutdown()
shutil.rmtree(tmp, ignore_errors=True)
