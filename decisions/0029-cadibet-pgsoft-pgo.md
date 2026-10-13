# 0029 — CadiBet rebrand, PG Soft revived on the trial launcher, Play'n GO 5 → 9

Date: 2026-10-12. Status: **shipped** — `frame` OK, `demo` 139/139,
`verify.py` 0 problems, export rebuilt, `/api/catalog` serves 182.

## 1. Rebrand to CadiBet

Visible strings `CasaBet`/`Casa Demo`/`casa-demo-web` are now **CadiBet**
(`web/app/layout.jsx` title, `Header.jsx` topbar + logo, `page.jsx`
footer, `demo/index.html`, `package.json`, READMEs). `localStorage` keys
(`casa-theme`, `casa-recent`, `casa-favs`, `casa-admin`) are deliberately
unchanged — they are invisible and renaming them would wipe player prefs.

## 2. PG Soft works again (loads + plays; wallet mirror specified, not built)

The old hosts are gone from public DNS (`m/static.pgsoft-games.com` =
NXDOMAIN even via Google DoH — dead globally, not just here). The live
replacement, found through a review site's preconnect hint:

- Loader: `https://public.pg-demo.com/demo/?gi=<id>&lang=pt` (200).
- It POSTs the query to
  `https://public-api.pg-demo.com/web-api/operator-proxy/v2/Game/GetTrialLaunchURLHTML`
  (form-urlencoded), which returns the game HTML; the game boots from a
  per-session host with an `ot=` token, e.g.
  `https://m.<session>.com/126/index.html?ot=…&l=pt&btt=2`.
- Money runs over HTTPS, not a socket:
  `POST https://api.<session>.com/web-api/auth/session/v2/verifySession`,
  `…/game-proxy/v2/GameName/Get`,
  `…/game-api/fortune-tiger/v4/GameInfo/Get` (+ spin endpoints).

Catalog rows updated and **verified live headless**: `pg:fortune-tiger`
(gi=126, full boot) and `pg:mahjong-ways` (gi=65, game doc + `INICIAR`).
`demo/provider_demos.py` allowlists `public.pg-demo.com`.

Wallet status, honestly: PG Soft is **trial play, not on our wallet**.
The path is fully mapped and needs no vendor account — our server mints
the trial session (the POST above), serves the game through `/g/` with
the session's hosts bound dynamically (they are random-letter domains,
so no static suffix covers them), and mirrors each round to our books
from the `game-api` spin request/response exactly like the Hacksaw RGS
proxy (decision 0025), with the R$0 gate refusing the spin. Not built
this session: it is a Hacksaw-sized job on its own.

## 3. More working titles: Play'n GO 5 → 9

Same launcher + same `gamehub` socket tap as decision 0026, so every
accepted gid settles with zero new mechanism. Launcher-probed
(200 = accepts, 400 = unknown): **added** `riseofolympus`,
`moonprincess100`, `sweetalchemy`, `goldenosiris`; rejected-and-left-out
`gemsbonanza`, `reactoonz2`, `bigbadwolf`,
`gargoyleinfinitysweetalchemy2`, `livingstoneswordofseshat`.

Working set now: Hacksaw 139 + Play'n GO 9 on our wallet; Spribe loads
(Aviator runs, money tap = SFS `bet`/`cashOut` frames per 0027);
Pragmatic Play 21 wallet-isolated free play (origin-coupled, 0028);
PG Soft 2 trial play; Evolution 2 stream pages.
