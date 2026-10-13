/* Game recon pass over the site's own embedded demo catalog.
 *
 * Usage: node scripts/recon_game.mjs [slug-substring] [max]
 *   slugs come from research/game-recon/targets.json (game_id based).
 *   Output per game under research/game-recon/out/<slug>/:
 *     meta.json     — url, title, tech signals, counts
 *     network.json  — [{url, method, type, status, mime, bytes}]
 *    Visible text + screenshots are intentionally NOT stored here:
 *     the old examples/recon/ pass already covers page captures, and
 *     game art stays on publisher hosts (no-rehost rule, decision 0006).
 *
 * Metadata only: request URLs, MIME types, byte sizes, status codes.
 * No response bodies are written to disk — assets, scripts and blobs
 * stay on the publisher's servers.
 */
import { chromium } from "file:///C:/Users/GABRIE~1/AppData/Local/Temp/opencode/scripts-vendor/playwright-core/index.mjs";
import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(ROOT, "research", "game-recon", "out");
const targets = JSON.parse(
  fs.readFileSync(path.join(ROOT, "research", "game-recon", "targets.json"), "utf-8")
);

const filter = (process.argv[2] || "").toLowerCase();
const max = parseInt(process.argv[3] || "40", 10);
const picked = targets
  .filter((t) => !filter || t.game_id.toLowerCase().includes(filter))
  .slice(0, max);
if (!picked.length) {
  console.log("no targets match");
  process.exit(1);
}

const browser = await chromium.launch({ headless: true });
for (const t of picked) {
  const slug = t.game_id.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "");
  const dir = path.join(OUT, slug);
  fs.mkdirSync(dir, { recursive: true });
  const calls = [];
  const seenWs = [];
  const ctx = await browser.newContext({
    locale: "pt-BR",
    viewport: { width: 1366, height: 768 },
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
  });
  const page = await ctx.newPage();
  page.on("response", async (resp) => {
    try {
      const req = resp.request();
      const headers = resp.headers();
      let bytes = -1;
      try {
        const buf = await resp.body();
        bytes = buf.length;
      } catch {}
      calls.push({
        url: req.url(),
        method: req.method(),
        type: req.resourceType(),
        status: resp.status(),
        mime: (headers["content-type"] || "").split(";")[0],
        bytes,
        urlhash: createHash("sha256").update(req.url()).digest("hex").slice(0, 16),
      });
    } catch {}
  });
  page.on("websocket", (ws) => seenWs.push(ws.url()));
  const tech = { title: "", canvas: 0, webgl: false, wasm: false, workers: 0, iframes: 0 };
  try {
    await page.goto(t.demo_url, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(12000);
    const probed = await page.evaluate(() => ({
      title: document.title || "",
      canvas: document.querySelectorAll("canvas").length,
      webgl: (() => {
        try {
          const c = document.createElement("canvas");
          return !!(c.getContext("webgl2") || c.getContext("webgl"));
        } catch {
          return false;
        }
      })(),
      wasm: typeof WebAssembly !== "undefined",
      workers: 0,
      iframes: document.querySelectorAll("iframe").length,
      scripts: Array.from(document.scripts).map((s) => s.src || "(inline)").slice(0, 40),
    }));
    Object.assign(tech, probed);
    const byType = {};
    for (const c of calls) byType[c.type] = (byType[c.type] || 0) + 1;
    const exts = {};
    for (const c of calls) {
      const m = (c.url.split("?")[0].match(/\.([a-z0-9]{2,5})$/i) || [])[1];
      if (m) exts[m.toLowerCase()] = (exts[m.toLowerCase()] || 0) + 1;
    }
    fs.writeFileSync(
      path.join(dir, "meta.json"),
      JSON.stringify({ game_id: t.game_id, provider: t.provider, title: t.title,
        url: t.demo_url, tech, websockets: seenWs, byType, exts,
        totalRequests: calls.length }, null, 2)
    );
    console.log(`OK  ${slug}: title=${JSON.stringify(tech.title.slice(0, 60))} reqs=${calls.length} canvas=${tech.canvas} ws=${seenWs.length}`);
  } catch (e) {
    console.log(`ERR ${slug}: ${String(e).slice(0, 140)}`);
    fs.writeFileSync(path.join(dir, "meta.json"),
      JSON.stringify({ game_id: t.game_id, error: String(e).slice(0, 300) }, null, 2));
  }
  await ctx.close();
  fs.writeFileSync(path.join(dir, "network.json"), JSON.stringify(calls, null, 2));
}
await browser.close();
