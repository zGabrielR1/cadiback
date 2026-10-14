/**
 * Capture what a publisher game actually says on the wire.
 *
 *     node scripts/capture_session.mjs <url> [--wait 30000] [--out probes/x.json]
 *                                       [--click "<css>"] [--eval "<js>"] [--steps ms]
 *
 * PG Soft's client is a 1 MB string-array-obfuscated bundle: the money host
 * and every endpoint are built at runtime, so reading the page tells you
 * nothing and guessing at the routes 404s. The only honest source is a real
 * run. This drives the Edge/Chrome already on the machine over the DevTools
 * Protocol and records every request and response — the same recon the
 * earlier captures in `probes/` were built on, but repeatable.
 *
 * A publisher game usually will not touch its money API until the player
 * presses start, so `--click` / `--eval` exist: the capture has to reach the
 * lobby, not just the loading screen, or the interesting requests are never
 * made. `--steps` repeats the clicks every few seconds, which is what gets
 * past a start button followed by a lobby that asks for a game first.
 *
 * Why the DevTools Protocol and not Playwright: playwright-core is not in the
 * tree (deliberately — it is 300 MB of browser binaries), and Node ships a
 * global `WebSocket`, so CDP costs one dependency: the browser you already
 * have. `--browser` points at another binary when Edge is not the one.
 *
 * Read-only in the way that matters: it loads a page in a throwaway profile
 * and writes a JSON report. It only ever presses the publisher's own trial
 * UI, on the publisher's own trial credits — there is no money anywhere in
 * this project.
 */

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { tmpdir } from "node:os";

const args = process.argv.slice(2);
const url = args[0];
if (!url) {
  console.error("usage: node scripts/capture_session.mjs <url> [--wait ms] [--out file] [--browser path] [--click css] [--eval js] [--steps ms]");
  process.exit(2);
}
const flag = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const WAIT_MS = Number(flag("--wait", 30000));
const OUT = flag("--out", null);
const CLICK = flag("--click", null);
const EVAL = flag("--eval", null);
const TAP = flag("--tap", null);          // "x,y" in CSS pixels, or "x,y@selector"
const STEPS = Number(flag("--steps", 5000));
// a headless window starts at 0x0, which makes every canvas rect 0x0 and
// every tap land on 0,0 — the pixel coordinates only mean something once the
// page is given a viewport the size of a phone or a laptop
const VIEWPORT = flag("--viewport", "1280x800");

const CANDIDATES = [
  flag("--browser", null),
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
].filter(Boolean);
const BROWSER = CANDIDATES.find((p) => existsSync(p));
if (!BROWSER) {
  console.error("no browser found; pass --browser <path to chrome/edge>");
  process.exit(2);
}

const PORT = 9222 + Math.floor(Math.random() * 400);
const PROFILE = resolve(tmpdir(), "candibet-cdp-" + PORT);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const child = spawn(BROWSER, [
  "--headless=new",
  "--disable-gpu",
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-extensions",
  "--disable-background-networking",
  "--mute-audio",
  // a publisher client that checks the clock against its own assets gets a
  // normal one; a frozen clock reads as tampering
  `--user-data-dir=${PROFILE}`,
  `--remote-debugging-port=${PORT}`,
  "about:blank",
], { stdio: "ignore" });

function cleanup() {
  try { child.kill(); } catch {}
  try { rmSync(PROFILE, { recursive: true, force: true }); } catch {}
}
process.on("exit", cleanup);
process.on("SIGINT", () => { cleanup(); process.exit(130); });

/** Wait for the browser's debugging endpoint to answer. */
async function devtoolsUrl() {
  for (let i = 0; i < 60; i++) {
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

async function main() {
  const browserWs = await devtoolsUrl();
  const ws = new WebSocket(browserWs);
  await new Promise((ok, bad) => {
    ws.addEventListener("open", ok, { once: true });
    ws.addEventListener("error", () => bad(new Error("devtools socket refused")), { once: true });
  });
  const client = cdp(ws);

  // a fresh tab, so we watch only this page and nothing the user has open
  const { targetId } = await client.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await client.send("Target.attachToTarget", { targetId, flatten: true });

  const records = new Map();     // requestId -> record
  const order = [];
  const console_ = [];

  client.on((msg) => {
    if (msg.sessionId !== sessionId) return;
    const { method, params } = msg;
    if (method === "Network.requestWillBeSent") {
      const r = params.request;
      const rec = records.get(params.requestId) || { id: params.requestId };
      rec.url = r.url;
      rec.method = r.method;
      rec.type = params.type;
      rec.headers = r.headers;
      if (r.postData) rec.postData = r.postData.slice(0, 4000);
      rec.ts = params.timestamp;
      records.set(params.requestId, rec);
      order.push(params.requestId);
    } else if (method === "Network.responseReceived") {
      const rec = records.get(params.requestId) || { id: params.requestId };
      rec.status = params.response.status;
      rec.mime = params.response.mimeType;
      rec.respHeaders = params.response.headers;
      records.set(params.requestId, rec);
    } else if (method === "Network.loadingFinished") {
      const rec = records.get(params.requestId);
      if (rec) rec.bytes = params.encodedDataLength;
    } else if (method === "Network.loadingFailed") {
      const rec = records.get(params.requestId);
      if (rec) rec.failed = params.errorText;
    } else if (method === "Network.webSocketCreated") {
      const rec = records.get("ws:" + params.requestId) || { id: "ws:" + params.requestId };
      rec.url = params.url;
      rec.type = "WebSocket";
      rec.frames = [];
      records.set("ws:" + params.requestId, rec);
      order.push("ws:" + params.requestId);
    } else if (method === "Network.webSocketFrameSent" || method === "Network.webSocketFrameReceived") {
      const rec = records.get("ws:" + params.requestId);
      if (rec && params.response && params.response.payloadData) {
        rec.frames.push({
          dir: method.endsWith("Sent") ? "out" : "in",
          data: params.response.payloadData.slice(0, 4000),
        });
      }
    } else if (method === "Runtime.consoleAPICalled") {
      console_.push({
        level: params.type,
        text: (params.args || []).map((a) => a.value ?? a.description ?? a.type).join(" ").slice(0, 400),
      });
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

  console.log(`watching ${url} for ${WAIT_MS}ms…`);

  /** Press something the page offers. Both paths are best-effort: a game
   * that draws its start button on a canvas has no selector to click, and a
   * failed click is a reason to widen the net, not to abort the capture. */
  async function press() {
    if (TAP) {
      // a canvas game has no clickable element: the button is pixels. Send
      // the same mouse sequence a hand would, so the game cannot tell the
      // difference between a synthetic tap and a real one.
      const [coords, sel = "canvas"] = TAP.split("@");
      const [x, y] = coords.split(",").map(Number);
      const expr = `(() => {
        const el = document.querySelector(${JSON.stringify(sel)});
        if (!el) return "no " + ${JSON.stringify(sel)};
        const r = el.getBoundingClientRect();
        const cx = r.left + (${x} < 0 ? r.width / 2 : ${x});
        const cy = r.top  + (${y} < 0 ? r.height / 2 : ${y});
        const opts = {bubbles:true, cancelable:true, view:window, clientX:cx, clientY:cy,
                      button:0, buttons:1, pointerId:1, pointerType:"mouse", isPrimary:true};
        for (const type of ["pointerdown","mousedown","pointerup","mouseup","click"]) {
          el.dispatchEvent(new (type.startsWith("pointer") ? PointerEvent : MouseEvent)(type, opts));
        }
        return "tapped " + Math.round(cx) + "," + Math.round(cy);
      })()`;
      try {
        const r = await client.send("Runtime.evaluate", { expression: expr, awaitPromise: true }, sessionId);
        console.log(`  tap ${TAP} -> ${r.result?.value ?? "?"}`);
      } catch (e) { console.log(`  tap failed: ${e.message}`); }
    }
    if (CLICK) {
      const expr = `(() => { const el = document.querySelector(${JSON.stringify(CLICK)});
        if (!el) return "no match"; el.click(); return "clicked"; })()`;
      try {
        const r = await client.send("Runtime.evaluate", { expression: expr, awaitPromise: true }, sessionId);
        console.log(`  click ${CLICK} -> ${r.result?.value ?? "?"}`);
      } catch (e) { console.log(`  click failed: ${e.message}`); }
    }
    if (EVAL) {
      try {
        const r = await client.send("Runtime.evaluate", { expression: EVAL, awaitPromise: true }, sessionId);
        console.log(`  eval -> ${JSON.stringify(r.result?.value ?? null)?.slice(0, 120)}`);
      } catch (e) { console.log(`  eval failed: ${e.message}`); }
    }
  }

  // let the game boot first, then keep pressing: one press opens the lobby,
  // the next starts a game, and neither is knowable from outside
  await sleep(Math.min(WAIT_MS, 12000));
  const deadline = Date.now() + WAIT_MS;
  while (Date.now() < deadline) {
    await press();
    await sleep(STEPS);
  }

  const list = order.map((id) => records.get(id)).filter(Boolean);
  // hosts the page touched, with a request count: the shape of the provider
  // in one glance, which is what a human actually wants from this
  const hosts = {};
  for (const r of list) {
    try {
      const h = new URL(r.url).host;
      hosts[h] = (hosts[h] || 0) + 1;
    } catch {}
  }

  const report = {
    captured_at: new Date().toISOString(),
    url,
    browser: BROWSER,
    total_requests: list.length,
    hosts,
    console: console_.slice(0, 120),
    requests: list,
  };

  if (OUT) {
    mkdirSync(dirname(resolve(OUT)), { recursive: true });
    writeFileSync(resolve(OUT), JSON.stringify(report, null, 2));
    console.log(`wrote ${OUT}: ${list.length} requests across ${Object.keys(hosts).length} hosts`);
  } else {
    console.log(JSON.stringify({ total: list.length, hosts }, null, 2));
  }
  for (const [h, n] of Object.entries(hosts).sort((a, b) => b[1] - a[1])) {
    console.log(`  ${String(n).padStart(4)}  ${h}`);
  }
  ws.close();
  cleanup();
  process.exit(0);
}

main().catch((e) => { console.error("capture failed:", e.message); cleanup(); process.exit(1); });
