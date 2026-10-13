# findings — per-publisher client architecture (from `out/*/meta.json` + `network.json`)

Confidence tags: **Observed** (in the captures), **Strongly inferred**
(multiple corroborating signals), **Inferred** (single-signal reading).

## Pragmatic Play — one launcher, N skins (Observed)

Every booting slot shows the same delivery shape:

```text
openGame.do?gameSymbol=<sym>          (302 → launcher shell)
 └─ html5Game.do?symbol=<sym>          (document, game shell)
     ├─ html5-script-external.js        (common launcher, ~4KB)
     ├─ logo_info.js                   (operator logos, ~1.8MB)
     ├─ games/vs/<sym>/desktop/bo…     (per-game bootstrap JS)
     ├─ games/vs/<sym>/desktop/pa…     (per-game JSON configs, 30–60 files)
     ├─ games/vs/<sym>/desktop/bu…     (game client bundle, ~3MB)
     ├─ …/desktop/cu…                  (binary octet-stream)
     └─ gs2c/*.do ×8                   (game-server round calls)
```

Rendering: single `<canvas>` (Observed). No websockets — rounds go
over HTTP to the `.do` game server (Observed), which is the
client/server boundary: reel outcomes are server-decided, so a local
clone could only ever replay canned rounds (Strongly inferred).
Telemetry alongside: GA, GTM, Grafana Faro, two custom collector
hosts (Observed).

Two catalog corrections fell out of the captures (Observed):
- `pp:big-bass-splash` (`vs10bbextreme`) boots titled **Big Bass
  Amazon Xtreme** — the catalog title is wrong.
- 5 launchers (`wild-west-gold`, `spaceman`, `roulette`,
  `blackjack`, `baccarat`) answer HTTP 200 + one stylesheet and never
  boot headless (PARTIAL). Smallest missing piece: a real-Chrome
  pass to see whether it is headless user-agent/feature detection.

## Spribe — Angular SPA + SmartFoxServer (Observed)

```text
demo.spribe.io/launch/<slug>          (302 → turbo.spribegaming.com/<slug>)
 └─ Angular shell (runtime/polyfills/main…js, v2.1.50-hotfix, Observed)
     ├─ assets/resources/dist/<slug>/<slug>.json + .png   (resource pack)
     ├─ assets/i18n/{en,pt}.json, app-config …/turbo/demo (config)
     ├─ assets/sounds/*.mp3
     └─ wss://app-demo*.spribegaming.com/BlueBox/websocket (game backend)
```

`BlueBox/websocket` is SmartFoxServer's HTTP-tunneling endpoint
(Strongly inferred: SFS2X serves multiplayer state + round results —
aviator's shared crash curve cannot be client-decided). Aviator's
backend is sharded (`app-demo2` vs `app-demo` for the rest,
Observed). Mines/aviator/plinko/mini-roulette/hotline mounted a
`<canvas>`; dice/goal/keno showed none at probe time — SVG/DOM
rendering or lazy mount after first interaction (Inferred).

## Play'n GO — Canvas + DOM, dual websockets (Observed)

ContainerLauncher shell → single canvas + DOM UI (fonts, css, png);
**two** persistent websockets per game: `ascflyp.*` and
`pc-prod-eu.*`. Dual-channel split (session/flyp vs game-round
traffic) is the natural reading (Inferred). No titles in the shell
(title empty, canvas present) — game identity lives in the `gid`
param, not the document (Observed).

## Hacksaw — atlas + KTX2 texture pipeline (Observed)

Single game, loudest asset signal in the set: 53 `.webm`, 26 `.png`,
14 `.atlas`, 11 `.ktx2` (Khronos GPU-compressed textures). Custom
RGS client loading pre-atlased, pre-compressed textures (Strongly
inferred); no websocket, HTTP RGS calls.

## Evolution — not games (Observed)

Both URLs are marketing pages (SVG/JPG heavy, zero canvas, zero
sockets). They are stream promos, not playable demos. Catalog
`note` fields already say "stream demo" — accurate, keep.

## PG Soft — BLOCKED on network (Observed)

`m.pgsoft-games.com` does not resolve from here
(`ERR_NAME_NOT_RESOLVED`, both listed ids). Same DNS failure as
decision 0019's expansion attempt. Retry from another network; the
pilot + full runs already cover the other five publishers.

## Reconstruction verdicts (Phase 10)

- Executable local clones: **BLOCKED** for all five playable
  publishers — round outcomes/state are server-side, assets are
  publisher property, and this project's no-rehost rule (0006/0008)
  forbids vendoring client bytes. This is a deliberate scope
  ceiling, not a tooling gap.
- Documentation-level reconstruction (delivery maps, protocol
  shapes, asset-pipeline notes above): **MOSTLY COMPLETE** for
  33/40, PARTIAL for 5 (PP stall), BLOCKED for 2 (PG DNS).
