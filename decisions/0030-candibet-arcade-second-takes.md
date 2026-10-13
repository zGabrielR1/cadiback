# 0030 — Candibet brand, in-house arcade trio, provider second takes

Date: 2026-10-12. Status: **shipped** — `frame` 44/44, `demo` 151/151
(+12 arcade), `verify.py` 0 problems, export rebuilt, trio verified live
over HTTP (crash bust, plinko 0.2x partial, mines clean-sheet win).

## 1. Candibet (like candy)

All visible strings and deploy names are `candibet`/`Candibet`
(title, logo `Candi+bet`, topbar, footer, fallback page, package,
`fly.toml` app, `render.yaml`, Worker name, deploy script, docs).
`localStorage` keys stay `casa-*` (invisible; renaming wipes prefs) and
history files keep their old names. Name reality, probed 2026-10-12:
`candibet.workers.dev` free, `candibet.pages.dev` + `candibet.com`
taken, `.com.br`/`.bet`/`.io` answer no DNS.

## 2. In-house Aviator-style trio (no provider, our wallet, our RTP)

New `demo/arcade.py` (stdlib, sha256 draw discipline, exact minor-unit
payouts via `place_bet` + `settle_casino` so sub-stake partial returns
pay to the centavo), wired into `Demo.spin`, certified BR-DEMO-0006/7/8,
Crash-lane catalog rows, SVG covers, three panels in the site's own UI
patterns (`CrashPanel` animated curve + target chips, `PlinkoPanel`
12-row replay board, `MinesPanel` 5x5 picker + bomb/gem reveal):

- `demo:crash-nitro` "Crash Nitro" — name a cash-out 1.01–1000x; 3%
  instant bust at 1.00x, else floor(0.97/(1-u)). RTP **97.00%** every
  target (exact over the draw grid). No target = clean 400.
- `demo:plinko-drops` "Plinko Drops" — 12 digest-bit moves into 13 slots
  (edges 130x, center 0.2x). RTP **97.16%** exact.
- `demo:minas` "Minas" — `m=<minas>:cells=…` on 5x5, digest-seeded mine
  field; clean sheet pays floor(0.97·C(25,k)/C(25-m,k)). RTP **97%**
  minus flooring dust (< 1 centavo).

## 3. Provider second takes (all read-only probes, no vendor account)

- **Spribe — the operator channel is decoded.** The client posts
  `{type, data}` to `parent` when framed (`ifc.make.bet {id, amount}`,
  `ifc.cashout.complete`, `ifc.win.info {id, amount}`,
  `ifc.update.balance`) and obeys `{cmd, data}` back (`ifc.set.balance
  {value}`). A framed load sent 0 messages (nothing fires before a bet),
  so the build is specified, not done: the theater listens for
  `ifc.make.bet` → debit, `ifc.win.info` → settle, and pushes our saldo
  via `ifc.set.balance`. No socket decoding needed.
- **Pragmatic Play — split attempted, defect is deeper.** The bridge now
  holds `GetDomain() → demogamesfree.pragmaticplay.net` while rewriting
  `serverUrl` to our origin (polls; boot is async). Live run: the client
  resolves `serverUrl` to `https://studio.game-service.biz` instead — the
  publisher host never appears — and still throws on `transform`. The
  coupling is not (only) GetDomain. PP stays labelled free play.
- **PG Soft — trial plays; wallet mirror specified in 0029**, unbuilt
  (Hacksaw-sized: server-minted session + dynamic host binding +
  game-api mirror settle).

Working set: 9 in-house originals (4 slots + roleta + crash + plinko +
minas + royale-pendente) + Hacksaw 139 + PGO 9 on our wallet; Spribe
loads; PP 21 free play; PG Soft 2 trial; Evolution 2 stream pages.
