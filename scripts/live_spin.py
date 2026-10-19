"""One real spin through our own proxy, in a browser that actually runs here.

    python scripts/live_spin.py --game pg:fortune-tiger
    python scripts/live_spin.py --game pp:gates-of-olympus --headed
    python scripts/live_spin.py --game pg:fortune-tiger --no-browser

Why this exists: `scripts/live_providers.py` proves the launcher renders and
OUR wallet answers, but not that the game's own spin reaches it — that needs a
browser. The old captures were driven from Linux with a Chromium AppImage;
this harness starts a throwaway local server, mints a wallet session, and hands
the launch URL to `scripts/drive_game.mjs`, which drives Chrome/Edge over the
DevTools Protocol (Windows or Linux, no AppImage).

The verdict is read in three places, never from the page's word alone:

    wallet   /api/wallet/status moved by the spin
    history  a publisher round row exists for the player
    tap      the provider's own tap log (Pragmatic's saldo ring buffer)

`--no-browser` skips the driver and just prints the launch URL, which is what
you want when a human intends to press spin in a visible window.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import ssl
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import demo.server as S  # noqa: E402
from demo import game_proxy  # noqa: E402

DRIVER = os.path.join(ROOT, "scripts", "drive_game.mjs")
PLAYER = {
    "name": "Ana Souza",
    "username": "anaspin",
    "email": "ana.spin@example.com",
    "cpf": "529.982.247-25",
    "pix_key": "ana.spin@example.com",
    "bank": {"bank_code": "001", "agency": "1234",
             "account": "56789-0", "holder_name": "Ana Souza"},
}
DEPOSIT_MINOR = 500_000


_SSL_CONTEXT = None
_CONTROL_HOST = ""


def _call(base: str, path: str, payload: dict | None = None, method: str = "POST"):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    if _CONTROL_HOST:
        # connect to loopback, but let the server see the browser's Host: the
        # launch URL it builds (and the PG document origin) must be the name
        # the browser resolves through its resolver rule, not 127.0.0.1.
        headers["Host"] = _CONTROL_HOST
        headers["X-Forwarded-Host"] = _CONTROL_HOST
    if _SSL_CONTEXT is not None:
        # The connection already runs over TLS, but `_our_origin()` only learns
        # the scheme from a forward header. Without it the launch URL comes
        # back `http://` while the page is served `https://`, and the browser
        # resets the navigations that follow.
        headers["X-Forwarded-Proto"] = "https"
    req = urllib.request.Request(
        base + path, data=data, method=method if data is not None else "GET",
        headers=headers)
    extra = {"context": _SSL_CONTEXT} if _SSL_CONTEXT is not None else {}
    try:
        with urllib.request.urlopen(req, timeout=60, **extra) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw.decode("utf-8", "replace")


def _amounts(view: dict) -> str:
    return "available %s  bonus %s" % (
        view.get("available_minor", view.get("balance_minor")),
        view.get("bonus_minor", 0))


def _self_signed(cert_path: str, key_path: str,
                 hosts: tuple[str, ...] = ()) -> tuple[str, str]:
    """A throwaway localhost certificate for the local test server.

    Several publisher clients hardcode `https://` in front of the document
    host (Pragmatic's Unity client does), so a plain-http local run is an
    unreachable TLS target: the boot never gets past its splash. The browser
    is told to accept this one certificate (`--ignore-cert-errors`), and it
    only ever exists in a temp directory.
    """
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=30))
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                *[x509.DNSName(h) for h in hosts if h],
                x509.IPAddress(__import__("ipaddress").ip_address("127.0.0.1")),
            ]), critical=False)
            .sign(key, hashes.SHA256()))
    with open(key_path, "wb") as handle:
        handle.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
    with open(cert_path, "wb") as handle:
        handle.write(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", default="pg:fortune-tiger")
    parser.add_argument("--press", type=int, default=3,
                        help="trusted key presses after the first click")
    parser.add_argument("--gap", type=int, default=2200,
                        help="milliseconds between presses")
    parser.add_argument("--settle", type=int, default=8000,
                        help="milliseconds to wait after the last press")
    parser.add_argument("--key", default="Space")
    parser.add_argument("--wait", type=int, default=25000,
                        help="how long the driver waits for the canvas")
    parser.add_argument("--boot", type=int, default=2500,
                        help="milliseconds to settle after the canvas appears "
                             "(PG's splash needs ~8s)")
    parser.add_argument("--tap", default="",
                        help="x,y@selector for a trusted click per press")
    parser.add_argument("--start", default="",
                        help="x,y trusted click once after boot (splash's "
                             "INICIAR button), before any spin")
    parser.add_argument("--tap-only", action="store_true",
                        help="use --tap clicks as the spin input instead of "
                             "the keyboard")
    parser.add_argument("--click", default="", help="css selector to click")
    parser.add_argument("--eval", dest="eval_js", default="",
                        help="read-only js to evaluate after boot and report")
    parser.add_argument("--bodies", action="store_true",
                        help="capture plaintext response bodies for the "
                             "handshake/wallet/spin calls (diagnostics)")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--ua", default="",
                        help="'none' keeps the browser's real UA "
                             "(Pragmatic's 0062 pin needs that)")
    parser.add_argument("--shot", default="",
                        help="screenshot path (default probes/live-spin.png)")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--tls", action="store_true",
                        help="serve over https with a self-signed cert "
                             "(Pragmatic hardcodes https:// + document host)")
    parser.add_argument("--host", default="",
                        help="serve the page under this hostname via Chrome's "
                             "resolver (test-only; PG's money host only allows "
                             "*.pg-demo.com origins)")
    parser.add_argument("--steer", action="store_true",
                        help="point PG's `ao` (money host) at this server so "
                             "verifySession/Spin land here (same-origin); "
                             "requires --host api.<domain> (the client prefixes "
                             "`api.` to the registrable domain)")
    parser.add_argument("--stake-hint", type=int, default=0,
                        help="only for the report: expected stake in minor units")
    args = parser.parse_args()

    if args.steer and args.host:
        # PG reads its money host off the launch's mangled `ao`; naming the
        # server here makes every verifySession/Spin call same-origin, so the
        # proxy sees them instead of the publisher's CORS wall. The client
        # does not use `ao` verbatim: it takes the registrable domain and
        # prefixes `api.` (measured: `ao=demo.pg-demo.com` →
        # `https://api.pg-demo.com`). Steering only lands on this server when
        # the document itself is served from that same `api.<domain>` host.
        labels = args.host.split(".")
        expected = "api." + ".".join(labels[-2:]) if len(labels) >= 2 else ""
        if args.host != expected:
            print("--steer needs the document on %s, not %s: the client "
                  "rewrites `ao` to `api.<registrable>`."
                  % (expected, args.host), file=sys.stderr)
            return 2

    tmp = tempfile.mkdtemp(prefix="live-spin-")
    S.DEMO = S.Demo(data_dir=tmp)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
    scheme = "http"
    if args.tls:
        cert, key = _self_signed(os.path.join(tmp, "cert.pem"),
                                 os.path.join(tmp, "key.pem"),
                                 hosts=(args.host,))
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        global _SSL_CONTEXT
        _SSL_CONTEXT = ssl.create_default_context(cafile=cert)
        scheme = "https"
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    # Python talks to loopback; when a test hostname is asked for, the Host
    # header carries it so the launch URL the server builds names the host the
    # browser resolves (Chrome's --host-resolver-rules), not 127.0.0.1.
    base = "%s://127.0.0.1:%d" % (scheme, port)
    public_origin = ("%s://%s:%d" % (scheme, args.host, port)
                     if args.host else base)
    global _CONTROL_HOST
    if args.host:
        _CONTROL_HOST = "%s:%d" % (args.host, port)
    if args.steer:
        os.environ["PG_AO_HOST"] = public_origin.split("://", 1)[1]
    shot = args.shot or os.path.join(ROOT, "probes", "live-spin.png")

    try:
        player = S.DEMO.upsert_player(PLAYER)["player_id"]
        S.DEMO.deposit({"player": player, "amount_minor": DEPOSIT_MINOR,
                        "method": "pix", "deposit_id": "live-spin"})

        status, launch = _call(base, "/api/wallet/launch",
                               {"player": player, "game_id": args.game})
        if status != 200:
            print("launch failed:", status, launch)
            return 1
        token = launch.get("token") or ""
        url = launch.get("interposed_url") or ""
        if not url:
            url = public_origin + "/g/%s/?wallet_token=%s" % (
                urllib.parse.quote(args.game), token)
        _, before = _call(base, "/api/wallet/status?token="
                          + urllib.parse.quote(token), method="GET")
        print("game    :", args.game)
        print("player  :", player)
        print("url     :", url[:160])
        print("before  :", _amounts(before))

        if args.no_browser:
            print("\nbrowser : skipped (--no-browser). Open the URL above and")
            print("          press spin; the server stays up for this process")
            input("press Enter to stop the server…")
            _, after = _call(base, "/api/wallet/status?token="
                             + urllib.parse.quote(token), method="GET")
            print("after   :", _amounts(after))
            return 0

        cmd = ["node", DRIVER, url,
               "--wait", str(args.wait),
               "--boot", str(args.boot),
               "--press", str(args.press),
               "--gap", str(args.gap),
               "--settle", str(args.settle),
               "--key", args.key,
               "--shot", shot,
               "--out", os.path.join(ROOT, "probes", "live-spin.json")]
        if args.tap:
            cmd += ["--tap", args.tap]
        if args.tap_only:
            cmd += ["--tap-only"]
        if args.start:
            cmd += ["--start", args.start]
        if args.click:
            cmd += ["--click", args.click]
        if args.eval_js:
            cmd += ["--eval", args.eval_js]
        if args.bodies:
            cmd += ["--bodies"]
        if args.headed:
            cmd += ["--headed"]
        if args.ua:
            cmd += ["--ua", args.ua]
        if args.tls:
            cmd += ["--ignore-cert-errors"]
        if args.host:
            cmd += ["--host-resolver-rules",
                    "MAP %s 127.0.0.1:%d" % (args.host, port)]
        print("\ndriving :", " ".join(cmd[:3]), "…")
        proc = subprocess.run(cmd, cwd=ROOT)
        if proc.returncode != 0:
            print("driver failed with", proc.returncode)

        _, after = _call(base, "/api/wallet/status?token="
                         + urllib.parse.quote(token), method="GET")
        rows = S.DEMO.history(player, limit=10)
        rounds = [r for r in rows if r.get("type") == "publisher"]
        print("\nafter   :", _amounts(after))
        print("rounds  :", len(rounds))
        for row in rounds[-6:]:
            print("  %s stake=%s payout=%s %s" % (
                row.get("game_title") or row.get("game_id"),
                row.get("stake_minor"), row.get("payout_minor"),
                row.get("settled_at") or ""))
        wins = [r for r in rounds
                if int(r.get("payout_minor") or 0)
                > int(r.get("stake_minor") or 0)]
        print("wins    :", len(wins),
              "best payout %s" % max(
                  [int(r.get("payout_minor") or 0) for r in rounds] or [0]))
        print("net     :", sum(int(r.get("payout_minor") or 0)
                              - int(r.get("stake_minor") or 0)
                              for r in rounds), "minor")
        print("proxy   :", game_proxy.stats())
        if args.game.startswith("pp:"):
            print("pragmatic tap:")
            for line in list(S.DEMO.pragmatic_tap)[-6:]:
                print("  ", json.dumps(line, ensure_ascii=False)[:180])

        moved = (int(before.get("balance_minor", 0))
                 != int(after.get("balance_minor", 0)))
        print("\nVERDICT :", "wallet moved" if moved else "WALLET DID NOT MOVE")
        return 0 if moved else 2
    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
