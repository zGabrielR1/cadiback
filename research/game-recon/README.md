# game-recon — authorized client-side analysis of the site's embedded demos

Authorized targets: the 40 publisher free-play demos already embedded
in this site's casino section (`targets.json`, generated from
`probes/provider-demos.json`). Analysis is limited to what the
publishers' servers deliver to a normal browser visit: request
inventories, technology signals, protocol shapes.

## Hard boundaries (non-negotiable, extend decisions 0006/0008)

1. **Metadata only.** `out/<game>/` holds `meta.json` (tech signals)
   and `network.json` (request URL, method, type, status, MIME,
   byte size). No response bodies — no JS, WASM, sprites, audio —
   are written to disk. Game bytes stay on publisher hosts.
2. **No rehost, no clone.** A playable local reconstruction is
   BLOCKED by design: round outcomes and state live on publisher
   game servers (PP `.do` endpoints, PGO websockets, Spribe
   SmartFoxServer backends), and art/RNG are publisher property.
   The reconstruction deliverable here is architecture
   documentation + protocol maps, never a working copy.
3. Read-only traffic: one normal page load per game, no auth, no
   credential use, no request tampering.

## Reproduce

```bash
node scripts/recon_game.mjs [slug-substring] [max]
```

One load per game (~20s). Results land in `out/<slug>/`.

## Status ledger

| Group | Games | Recon | Rendering | Backend |
|---|---|---|---|---|
| Pragmatic slots (16) | olympus, sweet, rush, bass ×2, starlight, doghouse, wolf, fruit, cleocatra, 1000-series ×4, zeus-hades, joker, bonanzagold | MOSTLY COMPLETE | Canvas, uniform launcher | HTTP game server (`gs2c/*.do`) |
| Pragmatic stall (5) | wild-west, spaceman, roulette, blackjack, baccarat | PARTIAL | launcher 200, client never boots headless | same — needs real-Chrome follow-up |
| Spribe (8) | aviator, mines, plinko, dice, keno, goal, mini-roulette, hotline | MOSTLY COMPLETE | Canvas/SVG hybrid | SmartFoxServer (`BlueBox/websocket`, sharded `app-demo*`) |
| Play'n GO (5) | bookofdead, reactoonz, firejoker, moonprincess, legacyofdead | MOSTLY COMPLETE | Canvas + DOM | 2 websockets (`ascflyp`, `pc-prod-eu`) |
| Hacksaw (1) | rip-city | MOSTLY COMPLETE | Canvas, `.atlas` + `.ktx2` texture pipeline, `.webm` | HTTP RGS |
| Evolution (2) | lightning-roulette, crazy-time | COMPLETE | marketing pages, no game client | n/a (streams, not demos) |
| PG Soft (2) | fortune-tiger, mahjong-ways | BLOCKED | host DNS-dead from here | retry from another network |

Details: `findings.md`.
