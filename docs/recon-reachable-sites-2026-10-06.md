# Recon of reachable sites — 2026-10-06

Candidate list was probed with a real browser UA; four were reachable in
this environment, ten were not (regulatory 302s to brasilsembets.gov.br /
Akamai 403s / DNS parked or gone). Per site, a Playwright-like session
log shows what the browser actually fetched. Reference only.

## Reachable — captured

| Site | Status | Notes |
|------|--------|-------|
| `https://casino.fanduel.com/` | 200 | Real SPA — 437 requests. Network plane below. |
| `https://www.bovada.lv/` | 200 | RSC login page — only jurisdiction + cookie + RUM chatter before auth. |
| `https://casino.fanatics.com/` | 403 | Akamai "Access Denied". |
| `https://www.draftkingscasino.com/` | 200 but parked | GoDaddy parking landers + Trustpilot. The brand is not operated at this URL. |
| `https://bet365.com/`, `stake.com`, `betmgm.com`, `caesars.com` | 403 | Likely region-gated/bot-walled from here. |
| `https://www.betano.com.br/` (and other `.com.br`s) | 302 | Funneled into the same `brasilsembets.gov.br` block — confirms the BR-market redirect for the regulator's watchlist. |
| `leovegas.com`, `ladbrokes.com`, `unibet.com`, `888casino.com` | DNS fail | Possibly upstream DNS filtering of betting-adjacent domains here. |

## FanDuel — the most useful one

Header = RG strip (`GAMBLING PROBLEM? Call 1-800-GAMBLER`) → top nav
`Responsible Gaming | Casino | Sportsbook | Log in | Join Now | Search`
→ promo hero → category rails (observed in DOM):
Home, Rewards, Earn $$$, New, **Slots, Jackpots, Blackjack, Live,
Exclusives, Classic Reels** (same shape as our `web/app/page.jsx` chip
row; ours additionally track Recentes/Favoritos client-side).

Data plane observed during one 10s on the home lobby (437 requests):

- Lobby bootstrap: `https://casino.fanduel.com/JMCVuBG8/init.js`
- Realtime jackpot feed, polled: `https://api.mi.casino.fanduel.com/jackpot/api/v2/jackpots`
  and `.../jackpot/api/v1/winFrequency?jackpotRefs=...`,
  `.../jackpot/api/v1/winners?jackpotRefs=...`
- Animated game tiles over HLS: `https://animatedtrailer.casino.fanduel.com/games/*.m3u8`
  with `.ts` segments — tiles are animated trailers, there are no static
  cover cards on the entry lobby
- Rive canvas (`@rive-app/canvas` WASM from unpkg) for animated logo/badges
- CMS-backed promo refs: `fanduel-casino.cdn.prismic.io` assets
- Config/flags: `config.account.fanduel.com/flags/...` incl.
  responsible-gaming session-activity config (`state-session-activity-config.json`)
- Observability: Datadog browser RUM, Amplitude, Snowplow, PerimeterX
  (`px-collector`, `ift.px-cloud.net`), DoubleClick

## Bovada

RSC Next.js shell — login page + `services.bovada.lv/jurisdiction/v2/access`
for geo-gating, cookie consent from CookieInformation, RUM from
wicket-keeper. 125 requests, no catalog without an account.

## Mapping to our demo

What a real operator (here: FanDuel) does that our hobby replica already
echoes:

- Peripheral per-game animated assets → our `provider_demos` cards embed
  publisher-hosted pages; a lighter variant would be a video-tile refresh
- Resumed jackpot feed to the lobby → our `GET /api/jackpot` (decision
  0015) already exposes a ledger-backed jackpot; stretching it to a
  per-game jackpot list on game tiles is the analog
- Responsible-gaming config endpoint → `demo/risk.py` limits + self-exclude
- No separate dev API for RTP/popularity on the lobby — our
  `/api/trending` and `/api/news` derive these from the round ledger in
  line with the same honesty posture.

This is context only. No demo code was adapted from the fetched pages;
the mirror/capture scripts stay separate from any UI work.
