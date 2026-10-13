# examples/superbet — reference capture (2026-10-06)

This folder is a **mirror from one snapshot**, not a vendored production
asset. It is used to study layout and runtime behaviour of a real BR
operator in this hobby project. Do not redistribute it; do not hotlink
any asset into the live demo.

## What the capture actually got from this network

`https://superbet.bet.br/jogos` redirects **(302)** to a federal
landing page served at `brasilsembets.gov.br` — the GovBR
"Brasil sem Bets / Acesso bloqueado" page — fronted by Cloudflare
(`/cdn-cgi/challenge-platform/` challenge assets). Even the deny page
requires a signed Cloudflare oneshot before it renders.

```
GET /jogos            -> 302  https://brasilsembets.gov.br/
GET /                 -> 200  (GovBR landing: Rawline font, @govbr-ds/core,
                              logo SVGs, Cloudflare jsd challenge)
GET cdn-cgi/challenge -> 302/200 (JS challenge + oneshot XHR)
```

`superbet.com.br` does not resolve in public DNS anymore. Every path and
a plain or browser UA hits the same block. So from this environment we
**cannot** currently mirror the operator games catalog itself.

## Files

| File | What |
|------|------|
| `jogos.live.html`      | raw DOM the Playwright capture saved (rendered output of the block landing) |
| `jogos.offline.html`   | same page with absolute asset URLs rewritten to `./assets/...` |
| `assets/`             | the handful of href/src targets from the page (GovBR DS CSS, fonts, two gov.br pages, falabr link) |
| `frames/jogos.png`    | full-page screenshot of the landing |
| `network.json`        | every request the page issued: url/method/type/status/mime — see ANALYSIS below |
| `title.txt`           | final document.title — "Brasil sem Bets — Acesso bloqueado" |

## How to recapture (e.g., BR egress IP)

```powershell
npm.cmd i --prefix "$env:TEMP\pw" playwright-core@1.63.0
# point scripts/capture_superbet_playwright.mjs import at that prefix, or
node scripts/capture_superbet_playwright.mjs
python scripts/mirror_superbet.py   # rewrites asset links to ./assets and copies them locally
```

The script holds the live approach: real browser context (viewport
1440x900, pt-BR), 12s settle, network log, rendered DOM, full-page
screenshot. The you-can-see-game-cards part requires egress from an IP
the operator does not block.

The component lives outside the repo for backup hygiene:
`npm.cmd i --prefix %TEMP%/opencode/pw playwright-core`, then point the
script's import at that path.
