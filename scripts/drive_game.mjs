/**
 * Drive a publisher game in a real browser and report what happened.
 *
 *     node scripts/drive_game.mjs <url> [--wait 20000] [--press 3]
 *                                 [--key Space] [--tap x,y@selector]
 *                                 [--start x,y] [--tap-only] [--click css] [--eval js]
 *                                 [--shot probes/x.png] [--headed]
 *                                 [--browser path] [--out probes/x.json]
 *
 * `capture_session.mjs` answers "what does the page say on the wire". This
 * answers the question after it: *does the game's own spin land on our
 * wallet*. It opens the page, waits for the canvas to have a real size,
 * sends trusted input (the same `Input.dispatch*` a hand produces, not a
 * synthetic DOM event), and reports the money calls plus a screenshot.
 *
 * Why the DevTools Protocol and not Playwright: Node ships a global
 * `WebSocket`, so CDP costs one dependency — the browser already installed.
 * On Windows the candidates are Chrome, Edge and a Playwright Chromium;
 * on Linux the same names are tried. There is no AppImage to chmod here:
 * the appimage era of these captures is over.
 *
 * Read-only in the way that matters: it presses the publisher's own trial
 * UI on the publisher's own trial credits. No money exists in this project.
 */

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { tmpdir } from "node:os";

const args = process.argv.slice(2);
const url = args[0];
if (!url) {
  console.error("usage: node scripts/drive_game.mjs <url> [--wait ms] [--press n] [--key Space] [--tap x,y@sel] [--start x,y] [--click css] [--shot file] [--headed] [--out file]");
  process.exit(2);
}
const flag = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] && !args[i + 1].startsWith("--")
    ? args[i + 1] : fallback;
};
const WAIT_MS = Number(flag("--wait", 20000));
const PRESS = Number(flag("--press", 3));
const GAP = Number(flag("--gap", 2200));
// A round settles after the last press too: PG's bridge polls its wallet for
// up to 12s after a spin, Pragmatic's answer carries the result. Closing the
// browser on the last keypress would cut that settlement off mid-flight —
// which is exactly how a winning spin was once missed.
const SETTLE = Number(flag("--settle", 8000));
const KEY = flag("--key", "Space");
const TAP = flag("--tap", null);
const TAP_ONLY = args.includes("--tap-only");
// Some clients (PG Soft among them) open on a splash with an INICIAR button
// that must be pressed once before the board accepts a spin. This is a single
// trusted click after boot, distinct from `--tap` (which repeats per press).
const START = flag("--start", null);
const CLICK = flag("--click", null);
const EVAL = flag("--eval", null);
const SHOT = flag("--shot", null);
const OUT = flag("--out", null);
const VIEWPORT = flag("--viewport", "1280x800");
const HEADED = args.includes("--headed");
// A local test server has a self-signed certificate and several clients
// (Pragmatic's Unity one among them) hardcode `https://` before the document
// host, so local verification needs TLS. Accepting that one certificate is
// what makes the local run possible; it never applies to a real publisher.
const INSECURE = args.includes("--ignore-cert-errors");
const RESOLVER = flag("--host-resolver-rules", null);
const BODIES = args.includes("--bodies");
// A canvas with a real size is not the same as a playable board: PG's splash
// spends several seconds at "A iniciar sessão". Give it a longer settle when
// the caller knows the client is heavy.
const BOOT = Number(flag("--boot", 2500));

const CANDIDATES = [
  flag("--browser", null),
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  ...(existsSync("C:\\Users\\Public\\AppData\\Local\\ms-playwright")
    ? [] : []),
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
].filter(Boolean);
const BROWSER = CANDIDATES.find((p) => existsSync(p));
if (!BROWSER) {
  console.error("no browser found; pass --browser <path to chrome/edge>");
  process.exit(2);
}

const PORT = 9400 + Math.floor(Math.random() * 400);
const PROFILE = resolve(tmpdir(), "candibet-drive-" + PORT);

// A headless browser advertises "HeadlessChrome" in its User-Agent, and some
// engines (PG Soft's among them) refuse to lay out under it. Pass an ordinary
// string unless `--ua none` is asked for. The 0062 session pin is a different
// case: that one is about Pragmatic's encrypted scene, not this UA.
const UA = flag("--ua",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
  + "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const child = spawn(BROWSER, [
  ...(HEADED ? [] : ["--headless=new"]),
  // WebGL is the reason the engine draws at all. Headless needs the software
  // fallback explicitly; a headed window keeps the GPU path.
  ...(HEADED
    ? ["--enable-unsafe-swiftshader", "--use-angle=swiftshader"]
    : ["--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--disable-gpu"]),
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-extensions",
  "--disable-background-networking",
  "--mute-audio",
  ...(UA === "none" ? [] : ["--user-agent=" + UA]),
  "--disable-blink-features=AutomationControlled",
  ...(INSECURE ? ["--ignore-certificate-errors",
                  "--allow-insecure-localhost"] : []),
  ...(RESOLVER ? ["--host-resolver-rules=" + RESOLVER] : []),
  `--user-data-dir=${PROFILE}`,
  `--remote-debugging-port=${PORT}`,
  "--window-size=1280,800",
  "about:blank",
], { stdio: "ignore" });

function cleanup() {
  try { child.kill(); } catch {}
  try { rmSync(PROFILE, { recursive: true, force: true }); } catch {}
}
child.on("error", (e) => {
  console.error(`cannot start the browser: ${e.message}`);
  cleanup();
  process.exit(1);
});
process.on("exit", cleanup);

async function devtoolsUrl() {
  for (let i = 0; i < 80; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      if (r.ok) return (await r.json()).webSocketDebuggerUrl;
    } catch {}
    await sleep(250);
  }
  throw new Error(`browser never opened ${PORT}`);
}

let nextId = 1;
function cdp(ws) {
  const pending = new Map();
  const listeners = [];
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve: ok, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(msg.error.message)) : ok(msg.result);
    } else if (msg.method) {
      for (const fn of listeners) fn(msg);
    }
  });
  return {
    send(method, params = {}, sessionId) {
      const id = nextId++;
      return new Promise((ok, reject) => {
        pending.set(id, { resolve: ok, reject });
        ws.send(JSON.stringify({ id, method, params, sessionId }));
      });
    },
    on(fn) { listeners.push(fn); },
  };
}

const KEYCODES = {
  Space: { code: "Space", key: " ", keyCode: 32, text: " " },
  Enter: { code: "Enter", key: "Enter", keyCode: 13, text: "\r" },
};

async function main() {
  const browserWs = await devtoolsUrl();
  const ws = new WebSocket(browserWs);
  await new Promise((ok, bad) => {
    ws.addEventListener("open", ok, { once: true });
    ws.addEventListener("error", () => bad(new Error("devtools socket refused")), { once: true });
  });
  const client = cdp(ws);
  const { targetId } = await client.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await client.send("Target.attachToTarget", { targetId, flatten: true });

  const records = new Map();
  const order = [];
  const console_ = [];
  const exceptions = [];

  client.on((msg) => {
    if (msg.sessionId !== sessionId) return;
    const { method, params } = msg;
    if (method === "Network.requestWillBeSent") {
      const r = params.request;
      const rec = records.get(params.requestId) || { id: params.requestId };
      rec.url = r.url;
      rec.method = r.method;
      rec.type = params.type;
      if (r.postData) rec.postData = r.postData.slice(0, 2000);
      records.set(params.requestId, rec);
      order.push(params.requestId);
    } else if (method === "Network.responseReceived") {
      const rec = records.get(params.requestId) || { id: params.requestId };
      rec.status = params.response.status;
      rec.mime = params.response.mimeType;
      records.set(params.requestId, rec);
    } else if (method === "Network.loadingFailed") {
      const rec = records.get(params.requestId);
      if (rec) rec.failed = params.errorText;
    } else if (method === "Runtime.consoleAPICalled") {
      console_.push({
        level: params.type,
        text: (params.args || []).map((a) => a.value ?? a.description ?? a.type)
          .join(" ").slice(0, 400),
      });
    } else if (method === "Runtime.exceptionThrown") {
      const d = params.exceptionDetails || {};
      exceptions.push((d.exception?.description || d.text || "").slice(0, 400));
    }
  });

  await client.send("Network.enable", {}, sessionId);
  await client.send("Runtime.enable", {}, sessionId);
  await client.send("Page.enable", {}, sessionId);
  const [vw, vh] = VIEWPORT.split("x").map(Number);
  await client.send("Emulation.setDeviceMetricsOverride",
    { width: vw || 1280, height: vh || 800, deviceScaleFactor: 1, mobile: false },
    sessionId);
  await client.send("Page.navigate", { url }, sessionId);

  const evalJs = async (expr) => {
    try {
      const r = await client.send("Runtime.evaluate",
        { expression: expr, awaitPromise: true, returnByValue: true }, sessionId);
      if (r.exceptionDetails) {
        return "EVAL ERROR: " + (r.exceptionDetails.exception?.description
          || r.exceptionDetails.text || "unknown");
      }
      return r.result?.value ?? null;
    } catch (e) { return "EVAL FAILED: " + e.message; }
  };

  // wait for the game to lay out: request count alone lies (the document can
  // arrive while the canvas stays 0x0), so poll the canvas itself
  const bootStart = Date.now();
  let canvas = null;
  while (Date.now() - bootStart < WAIT_MS) {
    canvas = await evalJs(`(() => {
      const c = document.querySelector('canvas');
      if (!c) return null;
      const r = c.getBoundingClientRect();
      return {x: r.x, y: r.y, w: r.width, h: r.height};
    })()`);
    if (canvas && canvas.w > 100 && canvas.h > 100) break;
    await sleep(500);
  }
  await sleep(BOOT);   // let the lobby/splash animate into its board

  async function clickAt(x, y) {
    const seq = [
      ["mouseMoved", {}],
      ["mousePressed", { button: "left", buttons: 1, clickCount: 1 }],
      ["mouseReleased", { button: "left", buttons: 0, clickCount: 1 }],
    ];
    for (const [type, extra] of seq) {
      await client.send("Input.dispatchMouseEvent",
        { type, x, y, pointerType: "mouse", ...extra }, sessionId);
    }
  }

  async function clickCanvas() {
    if (!canvas) return "no canvas";
    await clickAt(canvas.x + canvas.w / 2, canvas.y + canvas.h / 2);
    return `clicked ${Math.round(canvas.x + canvas.w / 2)},${Math.round(canvas.y + canvas.h / 2)}`;
  }

  async function tap() {
    if (!TAP) return null;
    const [coords, sel = "canvas"] = TAP.split("@");
    const [x, y] = coords.split(",").map(Number);
    const rect = await evalJs(`(() => {
      const el = document.querySelector(${JSON.stringify(sel)});
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {x: r.x, y: r.y, w: r.width, h: r.height};
    })()`);
    if (!rect) return "no " + sel;
    const cx = rect.x + (x < 0 ? rect.w / 2 : x);
    const cy = rect.y + (y < 0 ? rect.h / 2 : y);
    await clickAt(cx, cy);
    return `tapped ${Math.round(cx)},${Math.round(cy)}`;
  }

  async function press() {
    const k = KEYCODES[KEY] || KEYCODES.Space;
    await client.send("Input.dispatchKeyEvent", {
      type: "rawKeyDown", key: k.key, code: k.code,
      windowsVirtualKeyCode: k.keyCode, nativeVirtualKeyCode: k.keyCode,
    }, sessionId);
    if (k.text) {
      await client.send("Input.dispatchKeyEvent", {
        type: "char", key: k.key, code: k.code, text: k.text,
        windowsVirtualKeyCode: k.keyCode,
      }, sessionId);
    }
    await client.send("Input.dispatchKeyEvent", {
      type: "keyUp", key: k.key, code: k.code,
      windowsVirtualKeyCode: k.keyCode, nativeVirtualKeyCode: k.keyCode,
    }, sessionId);
  }

  const actions = [];
  actions.push(await clickCanvas());   // focus the board (a real press)
  await sleep(1200);
  if (START) {
    const [sx, sy] = START.split(",").map(Number);
    await clickAt(canvas ? canvas.x + sx : sx, canvas ? canvas.y + sy : sy);
    actions.push(`started ${sx},${sy}`);
    await sleep(2000);                 // entry animation
  }
  for (let i = 0; i < PRESS; i++) {
    if (TAP) actions.push(await tap());
    if (CLICK) {
      const r = await evalJs(`(() => { const el = document.querySelector(${JSON.stringify(CLICK)});
        if (!el) return "no match"; el.click(); return "clicked"; })()`);
      actions.push(String(r));
    }
    if (TAP_ONLY) {
      actions.push(`tapped only #${i + 1}`);
    } else {
      await press();
      actions.push(`pressed ${KEY} #${i + 1}`);
    }
    await sleep(i === PRESS - 1 ? SETTLE : GAP);
  }

  let evalResult = null;
  if (EVAL) {
    evalResult = await evalJs(EVAL);
    console.log("eval:", typeof evalResult === "string"
      ? evalResult : JSON.stringify(evalResult));
  }

  const hud = await evalJs(`(() => {
    const out = [];
    document.querySelectorAll('body *').forEach((el) => {
      if (el.children.length) return;
      const t = (el.textContent || '').trim();
      if (t && t.length < 40) out.push(t);
    });
    return out.slice(0, 40);
  })()`);

  let shot = null;
  if (SHOT) {
    try {
      const r = await client.send("Page.captureScreenshot",
        { format: "png" }, sessionId);
      mkdirSync(dirname(resolve(SHOT)), { recursive: true });
      writeFileSync(resolve(SHOT), Buffer.from(r.data, "base64"));
      shot = SHOT;
    } catch (e) { shot = "failed: " + e.message; }
  }

  const list = order.map((id) => records.get(id)).filter(Boolean);
  // Encrypted game-api answers are noise; the handshake and the trial wallet
  // are plaintext, and they are what the bridge tap needs to read. Fetched
  // after the run because CDP only serves a body once the load finished.
  const bodies = [];
  if (BODIES) {
    for (const rec of list) {
      if (!/verifySession|GameWallet|gameService|\/v4\/Spin|wallet\/round/.test(rec.url || "")) continue;
      try {
        const b = await client.send("Network.getResponseBody",
          { requestId: rec.id }, sessionId);
        bodies.push({
          url: rec.url, status: rec.status,
          base64: b.base64Encoded || false,
          body: (b.body || "").slice(0, 4000),
        });
      } catch {}
    }
  }
  const interesting = list.filter((r) => {
    const u = r.url || "";
    return /wallet|round|spin|gameService|verifySession|GameWallet|history|api\//i
      .test(u) && !/\.(png|jpg|gif|woff2?|css)(\?|$)/i.test(u);
  }).map((r) => ({
    method: r.method, url: r.url, status: r.status,
    failed: r.failed || undefined, postData: r.postData || undefined,
  }));

  const report = {
    captured_at: new Date().toISOString(),
    url, browser: BROWSER, headed: HEADED,
    canvas, actions, key: KEY, presses: PRESS,
    eval_result: evalResult,
    requests_total: list.length,
    console: console_.slice(-40),
    exceptions: exceptions.slice(-20),
    hud: hud || [],
    money_requests: interesting,
    bodies,
    screenshot: shot,
  };
  if (OUT) {
    mkdirSync(dirname(resolve(OUT)), { recursive: true });
    writeFileSync(resolve(OUT), JSON.stringify(report, null, 2));
    console.log(`wrote ${OUT}`);
  }
  console.log(JSON.stringify({
    canvas, actions, requests_total: report.requests_total,
    exceptions: report.exceptions,
    money_requests: interesting.map((r) => `${r.method} ${r.status ?? "?"} ${r.url}`),
    hud: report.hud.slice(0, 20),
    screenshot: shot,
  }, null, 2));

  ws.close();
  cleanup();
  process.exit(0);
}

main().catch((e) => {
  console.error("drive failed:", e.message);
  cleanup();
  process.exit(1);
});
