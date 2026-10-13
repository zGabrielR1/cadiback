# operator — 1:1 Hobby Betting Platform & Casino Replica

A high-fidelity 1:1 hobby simulation of a modern sports betting and online casino platform created for personal usage and testing.

## What this is

A complete, self-contained personal hobby platform:
- **Embedded Official Games**: Top titles from Pragmatic Play (Gates of Olympus, Sweet Bonanza, Sugar Rush, Spaceman, Roleta Europeia, Blackjack), Spribe (Aviator), Hacksaw Gaming (RIP City), Play'n GO (Book of Dead), and Evolution embedded directly into the site via a full theater player.
- **Interactive Sportsbook**: Live fixtures streamed from public sports feeds with an interactive Boletim de Apostas (Betslip) supporting single and multiple bets.
- **Double-Entry Wallet Core**: Integer minor units (centavos), thread-safe ledger, and idempotent transactions.
- **Fast Cashier**: Realistic Pix deposit and payout simulation for full end-to-end player journeys.
- **Modern Front-end**: Responsive Next.js 16 + React 19 storefront (`web/`) matching the visual fidelity, navigation, and UX patterns of leading betting platforms.
- **No commercial or regulatory obligations**: Personal hobby project without real money, CNPJ requirements, or licensing bureaucracy.

## Layout

```
operator/
  AGENTS.md / ARCHITECTURE.md / PROGRESS.md / CURRENTTASK  state + instruction
  Makefile / scripts/verify.py / scripts/verify.sh         verification checks
  container/Containerfile / container/frame.service        runtime definitions
  decisions/                                               architecture decisions
  docs/gap-assessment.md                                   platform scoreboard
  docs/deploy-easy.md                                      how to ship it, and how to check it
  docs/audit-2026-10-01.md                                 audit findings + fixes
  demo/                                                    playable server: Pix + slots + risk
  web/                                                     Next.js storefront (React 19), builds to web/out
  probes/                                                  live-feed evidence & provider demos
  frame/                                                   underlying wallet & integrity core
    core/        money, ids, ledger, devig
    wallet/      double-entry books
    validation/  data quality gates
    compliance/  game registry & limits
    models/      fair-price provider registry
    verticals/   sports + casino contracts and stubs
    ops/         scheduler, notifier, health
    tests/       42 core checks
```

## Running it

```bash
python scripts/verify.py                    # structure & integrity check
python -m frame.selftest                   # 45 core execution checks
python -m unittest demo.test_demo -v        # 191 demo checks
cd web && npm run build                    # build Next.js storefront to web/out
python -m demo.server                      # serves web/out on http://127.0.0.1:8765
```

`web/node_modules` is pruned between sessions on purpose — run `npm ci` once
before `npm run build`.

## Deploying it

**Start here: [`docs/deploy-easy.md`](docs/deploy-easy.md)** — the gates to
run first, the two paths, the post-deploy smoke checks, and what to read when
a game does not load.

- **One container on a Python host** (Render/Fly/Koyeb/Railway) — backend and
  storefront on one port, gives `candibet.<host>` with no proxy or tunnel:
  see [`docs/deploy-paas.md`](docs/deploy-paas.md) (`Dockerfile`, `fly.toml`,
  `render.yaml`). This is the chosen path; it needs an account on the host to
  go live.
- **Cloudflare Workers fronting a tunnel** — the Worker serves `web/out` and
  proxies the API to the backend: see [`deploy/README.md`](deploy/README.md)
  (decision 0023). Two things expire — the tunnel hostname and a
  `--temporary` account — so it is not the default.

## Provider catalog

The lobby's publisher demos live in `probes/provider-demos.json`. The
Hacksaw lane is discovered and verified, not hand-listed:

```bash
python scripts/discover_hacksaw_demos.py           # report (read-only)
python scripts/discover_hacksaw_demos.py --write   # append verified new rows
python scripts/make-covers.py && cd web && npm run build
```

Those titles run on our wallet (decision 0025): Hacksaw's demo launcher takes
its RGS base from an `env=` parameter, so the game's money calls are answered
by `frame` through `/rgs/hacksaw_gaming/…`.

Play'n GO also runs on our wallet (decision 0026): its launcher runs from our
origin, and the injected bridge taps the page's own SignalR socket
(`wss://ascflyp.playngonetwork.com//gamehub`) — reading each spin's stake and
the balance delta and settling the round via `POST /api/wallet/round`.


## Ground rules

- Money is integer minor units (centavos). Floats never touch balances.
- Ledgers write once and fills close once.
- All official games run safely in embedded iframe theater mode.
- Personal hobby simulation with no real money at risk.
