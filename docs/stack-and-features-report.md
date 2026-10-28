# operator — what it uses and what was built

Inventory of every stack piece, service and capability in `operator/` (a.k.a.
**candibet**). Sources: `README.md`, `ARCHITECTURE.md`, `AGENTS.md`,
`PROGRESS.md`, `decisions/`, `docs/`, the code, and the deploy manifests.
Snapshot: 2026-10-20.

---

## 1. One-paragraph summary

A 1:1 hobby simulation of a Brazilian sportsbook + casino. It is a **Python
standard-library HTTP server** with a **double-entry wallet core**, a
**Next.js 16 / React 19** storefront, a **self-hosted Better Auth (Node)**
sidecar for social login, **Supabase Postgres** as an optional database, real
payment rails through **Asaas (Pix)** and **NOWPayments (crypto)**, **Resend**
for email, **Cloudflare Turnstile** as the bot gate, and 272 official
publisher demo games plus 12 in-house originals. It runs as **one Docker
container on Render**, with the storefront also deployable to **Vercel**.

---

## 2. Stack at a glance

| Layer | What is used |
|---|---|
| Backend language | Python 3.14 (stdlib only, except the database driver) |
| HTTP server | `http.server.ThreadingHTTPServer` — no Flask/FastAPI/Django |
| Wallet/ledger | In-house `frame/` package (integer centavos, double-entry, hash-chained JSONL) |
| API style | JSON over same-origin HTTP; snake_case payloads; Brazilian Portuguese UI copy |
| Database | Supabase Postgres via **SQLAlchemy 2** + **psycopg 3** (optional); JSON/JSONL files by default |
| Frontend | **Next.js 16.3** (App Router) + **React 19.3**, no UI/state library |
| Styling | One hand-written `globals.css` (CSS variables, dark default + light toggle) |
| Static build | `next build` → static export (`output: "export"`) or server mode on Vercel |
| Auth (players) | **Better Auth** 1.7 (Google / Facebook / Apple) + CPF completion; HMAC-signed `ps1.` session tokens |
| Auth (admin) | In-house PBKDF2-HMAC-SHA256 credentials, Bearer sessions, `admin` / `viewer` roles |
| Captcha | **Cloudflare Turnstile** (server-side siteverify, action + hostname checks) |
| Email | **Resend** API (console mailer fallback) |
| Pix | **Asaas** API (charge → QR → webhook-confirmed credit) |
| Crypto | **NOWPayments** API (invoice → IPN with HMAC-SHA512) |
| Sports data | **Flashscore** (primary), **Livescore** and **ESPN** (fallbacks), captured Superbet data |
| Odds | In-house devig + Poisson pricing + market board (no paid feed) |
| Casino content | Pragmatic Play, Spribe, Hacksaw Gaming, Play'n GO, Evolution, PG Soft |
| Hosting | **Render** (Docker, live), **Vercel** (storefront), **Fly.io** config + CI workflow |
| Container | Multi-stage `Dockerfile`: Node 22 builds the storefront + auth deps, Python 3.14 runtime |
| CI/CD | GitHub Actions → `flyctl deploy`; `scripts/render_deploy.py` over the Render REST API |
| Notifications | **ntfy.sh** integration in the `frame` ops layer (implemented and unit-tested; the live server does not call it) + local file double |
| Testing | Python `unittest` (461 test methods total) + `scripts/verify.py` structure/link/freshness checks |
| Recon tooling | Node **CDP** (built-in `WebSocket`) and **playwright-core** (kept outside the repo) |
| Docs/process | `decisions/` (64 ADRs, 0001–0068), `PROGRESS.md`, `CURRENTTASK`, `AGENTS.md` |

---

## 3. Third-party services, and what each is for

| Service | Used for | Optional? | Notes |
|---|---|---|---|
| **Cloudflare Turnstile** | Bot gate on player login, signup and password-reset request | Yes — no secret = no-op | Verifies `success`, `action` and `hostname`; token is single-use |
| **Better Auth** (self-hosted) | Google / Facebook / Apple social sign-in | Yes — no creds, no buttons | Runs as a Node sidecar on loopback `:3100`, proxied at `/api/betterauth/*` |
| **Supabase** | Postgres 14-table schema for players, plays, rounds, postings, settings, promos, exclusions, receipts, ledger | Yes — no `DATABASE_URL` = files | Session pooler `:5432` (IPv4); migrations in `supabase/migrations/` |
| **Asaas** | Real Pix deposits: charge, QR code, provider-confirmed credit; sandbox + production keys | Yes — falls back to instant demo credit | Webhook authenticated with `asaas-access-token` in constant time |
| **NOWPayments** | Crypto deposits: BTC, ETH, USDT, USDC, LTC invoices and IPN | Yes — crypto tab hidden without a key | IPN verified with HMAC-SHA512 (`x-nowpayments-sig`) |
| **Resend** | Welcome email (opt-in) and self-service password reset | Yes — console mailer without a key | Reset token stored only as SHA-256, 30-minute TTL, single use |
| **Render** | Production host (`cadiback.onrender.com`), Docker build, health check | No (chosen path) | `render.yaml`; `scripts/render_deploy.py` can create/update the service via API |
| **Vercel** | Storefront host (`cadiback-web.vercel.app`) proxying `/api` to Render | Optional path | `BACKEND_URL` + rewrites in `next.config.js` |
| **Fly.io** | Alternative single-container host, region `gru` | Configured, not the live host | `fly.toml` + `fly-deploy.yml` |
| **Cloudflare Workers** | Previous deploy front (static assets + API proxy to a tunnel) | Archived | `archive/deploy-worker/`, decision 0023 |
| **ntfy.sh** | Operator push notifications from the `frame` ops layer | Yes | Implemented and unit-tested; `demo.server` does not call it |
| **challenges.cloudflare.com** | Turnstile JS widget script | With Turnstile | Explicit render, reset after each submit |
| **GitHub** | Source hosting + Actions deploy workflow | — | `.github/workflows/fly-deploy.yml` |

Credentials live in gitignored `.env.*` files (`.env.asaas.sandbox`,
`.env.asaasprod`, `.env.asaaswebhook`, `.env.betterauth`, `.env.crypto`,
`.env.render`, `.env.resend`, `.env.supabase`, `.env.turnstile`,
`.env.vercel`). `.env.authgear` is retired (replaced by Better Auth) and
`.env.wuapi` is not referenced by any code. **No secret values are reproduced
in this report.**

---

## 4. Backend: what is inside `frame/` and `demo/`

### `frame/` — the money core (imports nothing from verticals)

- `core/money.py` — integer minor units (centavos), largest-remainder
  allocation, payout math; floats never touch balances.
- `core/ids.py` — canonical fixture keys and refusal-to-guess matching.
- `core/ledger.py` — append-only, hash-chained JSONL; write-once,
  fill-once integrity ledger.
- `core/devig.py` — margin analysis and four fair-price methods
  (multiplicative, power, additive, Shin).
- `wallet/books.py` — double-entry journal with one `RLock` around
  duplicate check + balance guard + append; idempotent postings; player views.
  Nine accounts (`player:balance`, `player:bonus`, `bonus:issued`,
  `operator:cash`, `payable:player`, `bet:staked`, `ggr:revenue`,
  `bonus:revenue`, `adjustment:operator`) and an `assert_balanced()` invariant.
- `validation/gates.py` — freshness, odds sanity, margin bounds, duplicate and
  settlement gates.
- `compliance/sigap.py` — game registry, BR certification gate, exclusions,
  limits, SIGAP-style reporting.
- `models/registry.py` — fair-price provider registry.
- `verticals/sports/` — `SportsEngine` contract, stub, Flashscore / Livescore /
  ESPN engines, PT locale, market board, pricing, settlement, stats engine.
- `verticals/casino/` — `CasinoAggregator` contract + deterministic stub.
- `ops/scheduler.py` — tiered loop (15/30/60 min), per-subject cooldown, daily
  cap, receipts.
- `ops/notifier.py` — ntfy fan-out (fail-open) + local file double.
- `ops/health.py` — receipt freshness, ledger integrity, books balance.
- `tests/test_frame.py` — 50 execution checks; the executable spec.

### `demo/` — the playable product

- `server.py` (~266 KB) — the entire HTTP+JSON API, static serving of
  `web/out`, publisher proxy routes, wallet routes, admin routes, webhooks.
- `auth.py` — admin panel users, PBKDF2 hashing, Bearer sessions, roles,
  legacy hash upgrade on login.
- `player_session.py` — stateless HMAC-signed player tokens
  (`ps1.<payload>.<sig>`) with `session_epoch` revocation.
- `payments.py` — CPF/CNPJ check digits, Pix key classification, own-name bank
  validation, deposit/payout rules, idempotent IDs.
- `asaas.py` / `crypto.py` — real PSP clients over stdlib `urllib`.
- `slot.py` — six-tier paytable engine, `SHA256(game_id:round_id)` draws,
  multiple paytables / RTPs.
- `casino.py` — European single-zero roulette (35:1 straight, 1:1 even money,
  RTP 97.30%).
- `arcade.py` — Crash Nitro (target + live cash-out), Dice, Plinko, Mines,
  Keno, Wheel of Fortune; derived ladders, exact minor-unit settlements.
- `risk.py` — velocity, stake spikes, loss-chase, RTP drift, duplicate rounds.
- `behaviour.py` — per-player win/loss dial used by the admin panel; forces a
  *real* winning/losing draw from the game's own paytable.
- `odds_engine.py` — deterministic team-strength → Poisson → 5 %-margin book,
  repriced on a 30 s bucket.
- `sports_data.py` — captured-fixture loader with stub fallback.
- `vendor.py` — aggregator seam: explicit URL, https-only, gated titles.
- `provider_demos.py` — 272-row catalog loader with https-only + host allowlist.
- `game_proxy.py` — same-origin publisher game front; injects the wallet bridge,
  rewrites the balance, maps publisher money calls (`ADAPTERS`).
- `pg_proxy.py` — mints PG Soft trial sessions, binds the exact per-session
  hosts, forwards signed asset URLs byte-for-byte.
- `rgs_proxy.py` — RGS interposition (Hacksaw): the game stays on the
  publisher's CDN, only its money calls come to us, with CORS on the answers.
- `betterauth_proxy.py` — same-origin proxy to the Node auth sidecar,
  preserving `Host`, `X-Forwarded-Host` and every `Set-Cookie`.
- `models.py` / `db.py` — SQLAlchemy models and engine/session factory for
  Supabase Postgres.
- `test_demo.py` — 411 test methods.
- `index.html` — zero-build fallback storefront.
- `data/` — runtime JSON/JSONL stores (gitignored).

### Foundry kit (`foundry/`, vendored, stdlib only)

- `envfile.py` — `.env` parsing with “environment wins” precedence.
- `mail/` — message builder, HTML templates, Resend transport, console/null
  mailers, reserved-address refusal.
- `turnstile/` — verifier, canonical policy, transport.
- `auth/` — PBKDF2 password hashing, opaque session tokens/fingerprints,
  CPF/CNPJ document validation.
- `betterauth/` — config and the constant-time HMAC signed-identity bridge
  (120 s window).

---

## 5. Authentication & security stack

| Concern | Implementation |
|---|---|
| Player password hashing | PBKDF2-HMAC-SHA256, 600 000 iterations, 16-byte salt, versioned `pbkdf2_sha256$…` format, constant-time verify, `needs_rehash` |
| Player sessions | Stateless HMAC-SHA256 token `ps1.<payload>.<sig>`; 12 h TTL / 30 d “remember me”; revocation by bumping `session_epoch` on the player row |
| Admin sessions | Random Bearer tokens, 12 h TTL, persisted so restarts do not log everyone out; roles `admin` / `viewer` |
| Social login | Better Auth sidecar owns provider credentials and OAuth state; Python verifies an HMAC-signed identity claim; the wallet keys on `provider:subject` |
| Social onboarding | Mandatory CPF completion (check digits + uniqueness) before a wallet exists |
| Bot protection | Turnstile verification per action (`login`, `register`) and hostname allowlist; single-use tokens; fixed delay on failed logins |
| Password reset | 32-byte token, only SHA-256 stored, 30 min, one use, newer request invalidates older ones; neutral answer for unknown accounts; per-IP cap |
| Cross-origin writes | `Content-Type: application/json` + same-origin `Origin` guard, with `X-Forwarded-Host` / `FRONTEND_ORIGINS` support behind Vercel |
| Publisher containment | https-only, publisher-host allowlists, exact per-session host binding (PG Soft), no unsigned asset fallback |
| Webhook auth | Asaas header token + NOWPayments HMAC-SHA512, constant-time compare |
| Money safety | Integer centavos, idempotency keys on every money route, write-once ledger, `RLock`-serialised postings, balanced books invariant |
| PSP confirmation rule | A deposit only credits after the provider confirms it; the webhook is a hint, not the ledger entry |
| Payout rule | Two-step request → pay; only to the Pix key on file; own-name (Portaria 615/2024 style) rule enforced server-side |

---

## 6. Frontend: what the storefront does

`web/app/page.jsx` is the shell; `web/app/components/` holds:

- **Lobby** — `CasinoHome.jsx`: unified in-house + official cards, provider
  filter chips, categories, search, recent games (local cache), covers.
- **Sports** — `SportsHome.jsx`: sport tabs, country → league groups, live
  scoreboard, odds, 15 s polling, market cards.
- **Betslip** — `BetslipTray.jsx`: single and express (up to 12 legs) bets,
  live balance.
- **Game player** — `GameTheater.jsx`: iframe theater, fullscreen, reload,
  balance indicator, one-click game switcher.
- **In-house game panels** — `CrashPanel`, `DicePanel`, `PlinkoPanel`,
  `MinesPanel`, `KenoPanel`, `RoulettePanel`, `SlotPanel`, `WheelPanel`.
- **Cashier** — `CashierModal.jsx`: Pix (real Asaas when configured), crypto
  (NOWPayments), demo instant credit, payout request, QR/copy-paste.
- **Account** — `AccountModal.jsx`, `AccountView.jsx`, `OAuthIcon.jsx`:
  login/signup, social buttons, CPF completion, password reset.
- **Admin** — `AdminPanel.jsx` (~50 KB): totals, RTP, 7-day volume, top
  winners, biggest prizes, risk, player wallet view, balance adjustment,
  win/loss behaviour dial, test deposits, panel-user CRUD, registration
  settings, test accounts, mail test, password change.
- **Extras** — `PromosView`, `Header`, `BottomNav`, `ChatWidget` (canned-intent
  triage, labelled “simulada”), `DetailModal`, `TurnstileWidget`.
- **Libs** — `lib/api.js` (fetch helper, BRL formatting, 8 s timeout,
  `crypto.randomUUID` idempotency IDs, session storage), `lib/useSession.js`
  (shared player/profile/history/health state), `lib/localCache.js`
  (30-game recent cache that survives a cold backend), `lib/validation.js`.

No state manager, no UI kit, no CSS framework — plain React + one stylesheet.

---

## 7. Games & casino content

| Provider | Rows | How it runs |
|---|---:|---|
| **Hacksaw Gaming** | 139 | Demo launcher takes its RGS base from `env=`; money calls answered by us at `/rgs/hacksaw_gaming/…` and settled via `/api/wallet/round` |
| **PG Soft** | 92 | Trial session minted by us; hosts bound per session; page proxied same-origin; money API tapped on our transport |
| **Pragmatic Play** | 22 | Boot pushed to server contact; same-origin proxy + bridge; round settles on our books |
| **Play'n GO** | 9 | Runs from our origin; injected bridge taps the page's SignalR socket and settles each round |
| **Spribe** | 8 | Aviator etc. run from our origin on our wallet (`?user=&token=`) |
| **Evolution** | 2 | Live-casino demos embedded in theater mode |
| **Total** | **272** | Catalog: `probes/provider-demos.json`; covers: `games/*.svg` (~280) |

In-house originals (12 catalog rows, 11 playable):

- Slots: **Neon Gems**, **Fortune Ledger**, **Crimson Dragons**, **Gold Vault**,
  **Royale Roulette** (deliberately uncertified → BLOQUEADO).
- Table: **Roleta Europeia** (single-zero, 97.30 % RTP).
- Arcade: **Crash Nitro** (target + live cash-out), **Plinko Drops**,
  **Minas** (mines), **Dados** (dice), **Keno Relâmpago**, **Roda da Sorte**.
- Every draw derives from `SHA256(game_id:round_id)`; every round settles
  through `Books.place_bet` → `settle_bet_win|loss`.
- RTPs: 95.90 % / 94.95 % / 96.60 % per slot paytable; wheel/arcade ≈ 97 %.

---

## 8. Sportsbook

- **Fixtures:** Flashscore `.ninja` feed (primary), Livescore public API and
  ESPN scoreboards (NBA, NFL, MLB, NHL, Brazilian/European soccer, UCL) as
  fallbacks. Captured Superbet/Flashscore evidence lives in `probes/`.
- **Odds:** in-house engine — team strength → Poisson probabilities → margin
  book; `marketboard` builds moneyline/1X2, draw-no-bet, Asian handicap, double
  chance, both-teams-to-score, over/under totals, cards/corners/fouls counts and
  anytime-scorer lists; a per-market book with exact overround and a live-score
  tilt.
- **Prices:** one real published moneyline (ESPN) tagged `market`; the rest
  `inhouse`.
- **Lifecycle:** quote → accept (single or express) → settle on real results →
  void; settlement reads `frame/verticals/sports/settlement.py` and the stats
  engine.
- **UI:** sport-separated board, country → league grouping, live minute,
  repricing, PT-BR locale (`locale_pt.py`).

---

## 9. Data & persistence

**Postgres (Supabase), 14 tables** —
`players`, `users`, `sessions`, `settings`, `promos`, `plays`, `rounds`,
`books_postings`, `crash_pending`, `asaas_charges`, `exclusions`,
`sched_receipts`, `sched_counters`, `ledger`.

Still file-backed under `$OPERATOR_DATA_DIR`: the player store (and therefore
`oauth_links.json`), profiles, rounds, sessions, password resets, settings.
`DATABASE_URL` unset → everything stays on JSON/JSONL. Migrations:

- `20261015000000_operator_schema.sql`
- `20261016000000_players_username.sql`
- `20261017000000_player_behaviour.sql`

---

## 10. Deployment & operations

- **One container, one port.** `Dockerfile` stage 1 builds the Next export,
  stage 1b installs the auth-server deps, stage 2 is Python 3.14 + Node 22
  (checksum-pinned tarball) and runs `node auth-server/server.mjs & python3 -m
  demo.server`. Non-root `operator` user, `/data` volume, health check on
  `/api/health`.
- **Render** — `render.yaml`: free plan, one instance (the ledger is
  single-writer), health path, env placeholders with `sync: false` for every
  secret, `FRONTEND_ORIGINS`, `PUBLIC_SITE_URL`.
- **Vercel** — `web/` root, `BACKEND_URL` rewrites for `/api`, `/g`, `/rgs`,
  `/web-api`, `/game-api` and PG Soft root paths; server output when
  `VERCEL=1` or `NEXT_OUTPUT=server`.
- **Fly.io** — `fly.toml` (`gru`, 256 MB, suspend/auto-start, `/data` volume)
  and a GitHub Actions workflow on push to `main`/`master`.
- **Render API deploy** — `scripts/render_deploy.py --check | --url-only |
  --replace-env`, merging dashboard-only env with local `.env.*` values.
- **Health/observability** — `/api/health` reports mail, Turnstile, Asaas,
  crypto, Better Auth callback URLs, proxy counters, PG mint counters, ledger
  and books health.
- **Scheduler** — tiered cycles with per-subject cooldowns, daily caps and
  receipts (`frame/ops/scheduler.py`); `demo.server` writes boot/heartbeat
  receipts and `frame/ops/health.py` reads their freshness.
- **Notifications** — ntfy fan-out with a local file double, both in
  `frame/ops` and covered by tests; the live server does not send them yet.

---

## 11. Developer tooling in the repo

| Script | Purpose |
|---|---|
| `scripts/verify.py` / `verify.sh` | Structure, required files, markdown links, `web/out` freshness, markers |
| `frame/selftest.py` | Fast core self-test |
| `scripts/discover_hacksaw_demos.py` | Crawl the publisher's own games page/version.json; `--write` appends verified rows |
| `scripts/discover_pgsoft_demos.py` | Mint each PG Soft candidate and read its slug |
| `scripts/live_providers.py` | Launch each publisher through `/g/`, prove the bridge answers our saldo and a round debits |
| `scripts/live_spin.py` | Local TLS-intercept harness for observing game money calls (`cryptography` mints certs) |
| `scripts/capture_session.mjs` | Chrome DevTools Protocol capture over Node's built-in WebSocket |
| `scripts/drive_game.mjs` | Drive a real browser through CDP (Windows Chrome/Edge/Playwright Chromium) |
| `scripts/recon_game.mjs` / `recon_sites.mjs` | Playwright-based recon of demo URLs, websockets, asset types |
| `scripts/capture_superbet_playwright.mjs` | Capture Superbet's rendered state and realtime data plane |
| `scripts/make-covers.py` | Generate SVG cover art per title |
| `scripts/fetch-covers.py` | Fetch real publisher `og:image` covers |
| `scripts/fetch_live_fixtures.py` / `probe_live_feeds.py` | Refresh fixtures and report which feeds answer |
| `scripts/probe_vendor_catalog.py` | Single-GET probe of publisher/aggregator sites |
| `scripts/docker_context.py` | Check what the image will actually contain |
| `Makefile` | `selftest`, `demo-test`, `check`, `check-py`, `web-install`, `web-build`, `deploy-prep`, `deploy-check`, `feeds`, `lint` (markdownlint) |

Also in the tree: `templates/betterauth/` and `templates/auth/` (reusable auth
scaffolds with env examples and an Apple client-secret test), `supabase/README.md`
(schema verification queries), and `probes/` (captured evidence: 272-row demo
catalog, live fixtures, Flashscore/ESPN/Livescore caches, PG Soft
handshake/spin captures and screenshots).

---

## 12. What was built, area by area

- **Money core** — double-entry books, hash-chained write-once ledger, integer
  centavos, largest-remainder splits, idempotency, balanced-books assertion.
- **Wallet lifecycle** — deposit → bet → settle → withdraw, every step gated
  and posted once; nine account classes; bonus funds separated.
- **Player onboarding** — name, CPF/CNPJ check digits, email, username,
  password policy, Pix key classification, optional bank at signup, one wallet
  per CPF/email/username.
- **Cashier** — real Pix via Asaas, real crypto via NOWPayments, instant demo
  credit fallback, payout requests with masked receipts, own-name rule.
- **Casino** — 272 publisher demos + 11 playable originals; theater player;
  lobby filters, categories, search, recent, favorites, jackpot, trending.
- **Publisher wallet integration** — same-origin proxy, injected bridge,
  RGS interposition, PG Soft session minting, Play'n GO SignalR tap,
  Pragmatic boot push, Spribe origin coupling.
- **Sportsbook** — live fixtures from public feeds, in-house odds engine,
  market board, betslip (single + express), live repricing, real-result
  settlement, stats, anytime scorer, PT localization.
- **Risk & compliance** — velocity/stake-spike/loss-chase/RTP-drift/duplicate
  detection, SIGAP-style registry, BR certificate gate, limits, self-exclusion
  (persisted and expiring), hidden test accounts, per-player win/loss dial.
- **Promotions** — welcome bonus and cashback posted through the wallet, not
  bolted on top.
- **Admin panel** — hidden login, dashboard (totals, RTP, 7-day volume, top
  winners, biggest prizes, risk), player wallet operations, behaviour control,
  test deposits, panel-user CRUD with roles, registration settings, mail test,
  password change.
- **Content surfaces** — news panel derived from real server facts,
  tournaments with real leaderboards, jackpot, hot/cold activity board,
  chat triage widget, game detail modal.
- **Auth evolution** — password auth → Authgear (retired) → Better Auth
  sidecar with CPF completion; player sessions hardened into signed tokens
  with epoch revocation; password reset over email.
- **Platform evolution** — Cloudflare Worker + tunnel (archived) → single
  container on Render; storefront on Vercel; Supabase Postgres cutover in
  progress; Docker build made self-contained so no local artifact is needed.
- **Quality gates** — 50 frame checks, 411 demo checks, structural/link/
  freshness verification, live provider harness, honesty rules (a game that
  renders but never talks to our wallet is reported `wired=no`).

### Chronology (condensed from `PROGRESS.md` / `decisions/`)

2026-10-01 → 10-07: frame + demo, audit fixes, Next.js storefront, live feeds,
in-house odds engine, casino catalog 22 → 40, jackpot/favorites/chat/news/
tournaments/recent/hot-cold, functional promos, express betslip, admin panel.
10-08 → 10-13: ESPN engine, Superbet fallback, provider research, Hacksaw on
our wallet, Play'n GO SignalR, Spribe origin, in-house crash/plinko/mines/dice,
PG Soft proxy, brand → CadiBet, Cloudflare Worker deploy, single-container
PaaS, Pragmatic boot, deploy independent of the build machine, live on Render.
10-14 → 10-20: Keno original, Asaas Pix live, Turnstile, foundry kit + Resend,
signup without bank + hidden test accounts, Supabase + Vercel, usernames + live
feed, Flashscore board, PT countries + fuller markets, real-result settlement,
Authgear social + real sports book, hardening arc (crypto, behaviour, stats,
providers, wheel, test deposits), Pragmatic round tap, Better Auth replaces
Authgear, PG Soft production-ready, Pragmatic free spins, password reset.

---

## 13. Numbers snapshot

| Metric | Value |
|---|---:|
| Publisher demo games | 272 (6 providers) |
| In-house game rows | 12 (11 playable, 1 intentionally blocked) |
| Cover images | ~280 |
| Decision records | 64 files (0001–0068) |
| Postgres tables | 14 |
| Frame tests | 50 |
| Demo tests | 411 (docs snapshot older: 387 / 191) |
| API route prefixes | `/api`, `/g`, `/rgs`, `/web-api`, `/game-api`, PG `<gi>` root |
| Public hosts | `cadiback.onrender.com`, `cadiback-web.vercel.app` |

---

## 14. Gaps, caveats and honest notes

- **Supabase is partially cut over.** The schema and the seam exist, but the
  player store (and `oauth_links`) is still JSON; `OPERATOR_DATA_DIR` is not
  fully vestigial yet. PROGRESS marks the item `DOING`.
- **File-backed by default.** Without `DATABASE_URL`, everything is JSON/JSONL
  under `/data`; on Render's free plan that disk is ephemeral, so state resets
  on redeploy/restart.
- **No real-money licensing, CNPJ or regulator filing** — deliberate, stated in
  `docs/gap-assessment.md`.
- **Test counts in older docs are stale** (README says 45/191, AGENTS 50/387);
  the tree currently greps 50 + 411 test methods.
- **Cache and demo artifacts** (`probes/*.json`, `__pycache__`, `web/out`) are
  committed/kept for evidence and offline builds; `web/node_modules` is pruned
  on purpose (`npm ci` restores it).
- **Security note:** the working tree contains real credentials in gitignored
  `.env.*` files (Asaas prod, NOWPayments, Resend, Turnstile, Supabase,
  Better Auth, Render and Vercel tokens). They are excluded by `.gitignore`,
  but they are plaintext on disk — rotate anything that may have been shared
  and keep the tree out of public backups.

---

## 15. Where to read next

- `README.md` — overview and provider catalog.
- `ARCHITECTURE.md` — seams, wallet accounts, money lifecycle.
- `AGENTS.md` — file-by-file role map.
- `PROGRESS.md` / `CURRENTTASK` — state and active objective.
- `decisions/` — why each choice was made (newest wins on conflict).
- `docs/deploy-easy.md`, `docs/deploy-paas.md` — ship it.
- `docs/asaas.md`, `docs/crypto.md`, `docs/mail.md`, `docs/turnstile.md`,
  `docs/oauth.md`, `docs/supabase.md` — per-rail runbooks.
- `docs/gap-assessment.md` — fidelity scoreboard.
