/* Capture https://superbet.bet.br/jogos rendered state with Playwright.
 *
 * Uses the chromium installed under ms-playwright by `npx playwright install`.
 * Outputs under examples/superbet/:
 *   - live-jogos.html    rendered DOM snapshot (post-JS)
 *   - network.json       every request: url, method, resourceType, status, mimeType
 *   - frames/            full-page screenshot(s)
 *   - title.txt          final document.title (helps prove which page shipped)
 * Any fetch/XHR/GraphQL/WebSocket URL seen here is the realtime data plane
 * of a real operator. Reference only; do not hotlink into the demo.
 */
// playwright-core is kept OUTSIDE the repo (backup hygiene).
// Reinstall with:  npm.cmd i --prefix "%TEMP%\opencode\pw" playwright-core
// and copy back into scripts/_vendor, or adjust this path.
import { chromium } from "file:///C:/Users/GABRIE~1/AppData/Local/Temp/opencode/scripts-vendor/playwright-core/index.mjs";
import fs from "node:fs";
import path from "node:path";

const OUT = "examples/superbet";
fs.mkdirSync(path.join(OUT, "frames"), { recursive: true });

const calls = [];
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  locale: "pt-BR",
  viewport: { width: 1440, height: 900 },
  userAgent:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
});
const page = await ctx.newPage();
page.on("response", async (resp) => {
  try {
    const t = resp.request().resourceType();
    calls.push({
      url: resp.url(),
      method: resp.request().method(),
      type: t,
      status: resp.status(),
      mime: resp.headers()["content-type"]?.split(";")[0] || "",
    });
  } catch {}
});

page.on("websocket", (ws) => {
  calls.push({ url: ws.url(), method: "WS", type: "websocket", status: 101, mime: "" });
});

try {
  await page.goto("https://superbet.bet.br/jogos", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(12000);
  const title = (await page.title()) || "";
  fs.writeFileSync(path.join(OUT, "title.txt"), title);
  const html = await page.content();
  fs.writeFileSync(path.join(OUT, "live-jogos.html"), html, "utf8");
  await page.screenshot({ path: path.join(OUT, "frames", "jogos.png"), fullPage: true });
  const len = html.length;
  const gamesHint = (html.match(/casino|jogo|slot/gi) || []).length;
  console.log(`title=${JSON.stringify(title)} html=${len}B casinoish-mentions=${gamesHint}`);
} catch (e) {
  console.log("goto failed:", String(e).slice(0, 200));
}
await browser.close();
fs.writeFileSync(path.join(OUT, "network.json"), JSON.stringify(calls, null, 2));
console.log(`network.json: ${calls.length} entries`);
