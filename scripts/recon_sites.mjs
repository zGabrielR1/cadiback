/* Recon pass across reachable real casino/sportsbook sites.
 * Outputs under examples/recon/<site>/: live.html, network.json,
 * frame.png, title.txt. Reference only — not for hotlinking.
 */
import { chromium } from "file:///C:/Users/GABRIE~1/AppData/Local/Temp/opencode/scripts-vendor/playwright-core/index.mjs";
import fs from "node:fs";
import path from "node:path";

const SITES = [
  ["fanduel-casino", "https://casino.fanduel.com/"],
  ["draftkings-casino", "https://www.draftkingscasino.com/"],
  ["fanatics-casino", "https://casino.fanatics.com/"],
  ["bovada", "https://www.bovada.lv/"],
];

const browser = await chromium.launch({ headless: true });
for (const [name, url] of SITES) {
  const dir = path.join("examples", "recon", name);
  fs.mkdirSync(dir, { recursive: true });
  const calls = [];
  const ctx = await browser.newContext({
    locale: "pt-BR",
    viewport: { width: 1440, height: 900 },
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
  });
  const page = await ctx.newPage();
  page.on("response", async (resp) => {
    try {
      calls.push({
        url: resp.url(),
        method: resp.request().method(),
        type: resp.request().resourceType(),
        status: resp.status(),
        mime: resp.headers()["content-type"]?.split(";")[0] || "",
      });
    } catch {}
  });
  page.on("websocket", (ws) =>
    calls.push({ url: ws.url(), method: "WS", type: "websocket", status: 101, mime: "" })
  );
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(10000);
    const title = (await page.title()) || "";
    fs.writeFileSync(path.join(dir, "title.txt"), title);
    fs.writeFileSync(path.join(dir, "live.html"), await page.content());
    await page.screenshot({ path: path.join(dir, "frame.png"), fullPage: false });
    const text = await page.evaluate(() => document.body.innerText.slice(0, 600));
    fs.writeFileSync(path.join(dir, "visible.txt"), text);
    console.log(`OK  ${name}: title=${JSON.stringify(title)} calls=${calls.length}`);
  } catch (e) {
    console.log(`ERR ${name}: ${String(e).slice(0, 120)}`);
  }
  await ctx.close();
  fs.writeFileSync(path.join(dir, "network.json"), JSON.stringify(calls, null, 2));
}
await browser.close();
