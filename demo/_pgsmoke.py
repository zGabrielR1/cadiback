"""Throwaway smoke: a PG Soft launch through the whole wallet -> proxy path.

Not part of the suite — it mints a real PG session over the network, which
the unit tests must not do. Run it by hand after changing `pg_proxy` or the
PG branch of `interposed_launch`.
"""
import json
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, r"D:\Downloads\stuff\ppp\pentesting\betting\operator")
import demo.server as S

tmp = tempfile.mkdtemp(prefix="pg-smoke-")
S.DEMO = S.Demo(data_dir=tmp)

# record every URL the proxy asks the publisher for: the leak and signature
# questions are about what leaves this process, not what comes back
SEEN = []
_real_fetch = S.game_proxy.fetch


def spy(url, *a, **kw):
    SEEN.append(url)
    return _real_fetch(url, *a, **kw)


S.game_proxy.fetch = spy

httpd = ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d" % httpd.server_address[1]


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(B + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw)
            except ValueError:
                return r.status, raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw.decode("utf-8", "replace")


s, pl = call("POST", "/api/player", {
    "name": "Ana Souza", "cpf": "529.982.247-25",
    "pix_key": "ana.souza@example.com",
    "bank": {"bank_code": "001", "agency": "1234",
             "account": "56789-0", "holder_name": "Ana Souza"},
})
PLAYER = pl["player_id"]
print("player  :", s, PLAYER)
s, dep = call("POST", "/api/deposit",
              {"player": PLAYER, "amount_minor": 10000, "method": "pix"})
print("deposit :", s, str(dep)[:140])

s, launch = call("POST", "/api/wallet/launch",
                 {"player": PLAYER, "game_id": "pg:fortune-tiger"})
print("launch  :", s, str(launch)[:170])
url = launch.get("interposed_url") or ""
assert "/g/pg:fortune-tiger/pg/" in url, "no minted session launch: " + url

s, body = call("GET", url[len(B):])
print("game doc:", s, (len(body) if isinstance(body, str) else 0), "bytes")
if isinstance(body, str):
    print("  real PG document :", len(body) > 500000)
    print("  bridge injected  :", "wallet" in body.lower())

# the leak surface is what goes UPSTREAM, not what comes back: the bridge we
# inject legitimately carries the token, because the bridge is ours.
sid = url.split("/pg/")[1].split("/")[0]
s, asset = call("GET", "/g/pg:fortune-tiger/pg/%s/loader/06.js?verify=abc%%3D" % sid)
print("asset   :", s, (len(asset) if isinstance(asset, str) else asset))
print()
print("upstream requests:")
for u in SEEN:
    print("   ", u[:130])
leaked = [u for u in SEEN if launch["token"] in u]
print("  wallet token sent to PG:", bool(leaked), "  <- must be False")
kept = [u for u in SEEN if "verify=" in u]
print("  asset signature preserved:", bool(kept), "  <- must be True")

s, health = call("GET", "/api/health")
print("proxy   :", health.get("proxy"))
httpd.shutdown()
shutil.rmtree(tmp, ignore_errors=True)
