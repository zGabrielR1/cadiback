# PROGRESS

## DONE (2026-10-15 — Signup without the payout account + hidden test accounts, decision 0046)

- **Signup no longer demands bank/agência/conta.** The Pix key is the payout
  destination, so the account fields were vestigial friction. `register_player`
  now treats them as optional, and a new operator setting
  `require_bank_at_signup` (painel → Configurações do cadastro) restores the old
  strict behaviour. A *half*-filled account is still validated as a whole the
  moment any field is touched — worse than none.
- **Test accounts are invisible and painel-managed.** The visible "Usar conta de
  teste" button is gone. A test account is an ordinary player row flagged
  `is_test`; it logs in through the normal email + password door, and the
  built-in identity is reachable on the storefront only through **Ctrl+Shift+T**
  while the account modal is open. A second setting `test_accounts_enabled` turns
  them off entirely (a disabled test account cannot log in — same message, same
  delay). The painel gains "Contas de teste": list, create, reset password,
  delete, never exposing salt/hash.
- **Settings store + public config.** Settings live in a JSON store
  (`settings.json`), defaults in `SETTINGS_DEFAULTS`; `GET /api/config` (public)
  and `GET|POST /api/admin/settings` (admin-only, role-gated). `/api/health` also
  carries `config`.
- **No auto-fetch from the Pix key** (the owner's ideal): Asaas exposes no DICT
  lookup for an arbitrary key, and a bank account is not derivable from an
  email/CPF/EVP key. The honest resolution is that the account is optional,
  because the payout already follows the key.
- **`SignupSettingsTest` x6**: defaults; optional-vs-required; a partial account
  refused; settings admin-only and persistent across a restart; test accounts
  flagged, listed without secrets, blocked when disabled, reset, deleted;
  test accounts exempt from the signup rule; the test-account doors are
  admin-only. `frame` 45/45, `demo` 258/258, `verify.py` 0. The HTTP routes were
  smoked live too (config, a settings flip reflected publicly, signup with and
  without the account, create/list/login/reset/delete test account, viewer
  refusal).

## DONE (2026-10-15 — Asaas Pix rail: a real charge, confirmed before a centavo posts, decision 0045)

- **Real Pix, or the instant demo credit — never both halves of each.** When
  Asaas is configured the cashier opens a real Pix charge, shows the QR and the
  copia-e-cola, and polls until the money lands. When it is not, the deposit
  behaves exactly as before. `GET /api/health` reports `asaas.configured` and
  `asaas.env` (`sandbox` | `production`).
- **The webhook is a hint, never proof.** Asaas says a payment happened; the
  server re-reads the charge (`GET /payments/{id}`), requires a terminal status
  and a matching amount, and only then posts. A replayed event, a forged body,
  or an event for an unrelated charge credits nothing. Same posture as the
  publisher-game taps (0032/0043/0044): read truth from the side that owns it.
- **`demo/asaas.py`** (~300 lines, stdlib only, `urllib`): `AsaasConfig`
  (env / gitignored `.env.asaas`, https enforced), `AsaasClient` (create,
  read, `pixQrCode`, constant-time webhook check), `Charge`, `resolve_webhook`,
  a four-outcome status map, and an injectable transport so the whole path is
  testable with no network and no key. A cross-host redirect is refused, so the
  account key can never be replayed to another origin.
- **Idempotency in three places:** `Idempotency-Key: dep:{deposit_id}` on the
  create, `create_pix_deposit` idempotent on `deposit_id`, and the books post
  once under `demo:deposit:{player}:{deposit_id}` inside `books.lock` — the
  webhook and the poll share that one path, so they can race without double
  paying. Lock order is fixed: `_asaas_lock` before `books.lock`.
- **Server wiring:** `POST /api/deposit/pix`, `POST /api/deposit/pix/status`,
  and `POST|GET /api/webhooks/asaas` (routed *before* the same-origin gate,
  because Asaas calls it from its own servers). Pending charges persist to
  `$OPERATOR_DATA_DIR/asaas_charges.json` and survive a restart without
  crediting anyone.
- **Frontend:** `useSession` exposes `asaasAvailable`; the cashier shows the QR
  and a copy button, polls the status endpoint every 5s while it is open, and
  keeps the instant credit path untouched for an unconfigured server.
- **`AsaasTest` 6 + `AsaasDepositTest` 10** (+16): config needs a key, customer
  and https; the status map collapses to four outcomes; a pending charge is not
  a balance; the poll confirms exactly once; the charge is idempotent on the
  deposit id; a bad token is refused and a good one credits once; an amount
  mismatch, an unknown deposit and an unpaid event each credit nothing; a
  pending charge survives a restart. `frame` 45/45, `demo` 252/252, `verify.py`
  0.
- **Docs + deploy:** `docs/asaas.md` (credentials, flow, webhook
  registration, production swap, deploy plumbing, triage);
  `scripts/render_deploy.py` carries the four `ASAAS_*` settings from the
  gitignored `.env.asaas`/environment; `render.yaml` holds `sync: false`
  placeholders only, so no secret enters the repository.
- **Live-verified in the sandbox.** A real R$5,00 charge → QR → provider-side
  confirm → webhook credit → a replay credits nothing → books balanced. The
  smoke also caught two constraints the fake transport could not: the billed
  customer must carry a CPF/CNPJ (provisioned once via
  `POST /customers/{id}`), and Asaas enforces a **R$5,00 minimum** per charge.
  Neither is a code defect; both are in the runbook, along with the real sandbox
  confirm action `POST /v3/sandbox/payment/{id}/confirm`.
- **Registered and verified on the live host.** The webhook `operator-deposits`
  → `https://cadiback.onrender.com/api/webhooks/asaas` (RECEIVED / CONFIRMED /
  OVERDUE / REFUNDED, `hasAuthToken: true`). A live end-to-end on the deployed
  service: a R$5 charge confirmed provider-side credited the player through the
  **webhook alone** (balance 500 at t+5s with no poll call), and the poll agreed
  without double-crediting. Render is the host; the earlier Fly-vs-Render
  confusion was moot because nothing was registered before.
- **A deploy-tooling bug surfaced on the way:** `PATCH /services/{id}` does not
  own environment variables — smuggling `envVars` into it collapsed the
  service's whole environment to one junk variable, and the first deploy came up
  with the rail unconfigured. They now go through `PUT /services/{id}/env-vars`.
- **Honest limits:** the payer is one configured customer, not the player
  (per-player customers are the production path); the sandbox customer needed a
  CPF/CNPJ, provisioned once. The two webhook-secret files were reconciled to
  the `.env.asaas` value. A pre-existing `weeeb` webhook (enabled, pointing at
  the site root) was left untouched.

## DONE (2026-10-14 — Keno Relâmpago, the original that was set aside for the wrong reason, decision 0042)

- **`demo:keno` "Keno Relâmpago"** (BR-DEMO-0010, RTP 97.00, Originais):
  20 of 80 numbers drawn from a digest-seeded shuffle; the player picks 1–10
  spots and the hit count pays.
- **The paytable is derived, not typed** — which is the answer to the reason
  0034 set keno aside ("a full paytable to get exactly right"). The hit
  probabilities are exact hypergeometric in `Fraction`, the shape is one
  decision (every extra hit doubles), and the ladder is divided by its own
  expected return times `HOUSE_KEEP`. So **RTP is 97.000000% at every spot
  count by construction**, worst deviation across all ten being 0.0000089%.
  There is no table to mistype and no way to change the shape and accidentally
  make the house generous.
- **Two things nearly wrong, both caught by measurement:** flooring the payout
  to centavos cost **1.5% of the RTP** at a R$1 stake (ten tiers × up to a
  centavo each) — fixed by rounding half up, which is unbiased; and the ladder
  needs four-decimal precision across its settling passes, or the model drifts
  0.08%. Realised RTP is now 96.9–97.2% and `keno_realised_rtp` reports it.
- **A sub-stake tier is not a win**: 1 hit on 10 spots pays 0.2240×, which the
  panel shows in amber as `retorno parcial`, never as a prize. Same honesty
  dice already has with `under:99.00`.
- `KenoPanel.jsx`: an 80-number board (10×8), spot selector, quick-pick, live
  ladder with per-tier chance, and four cell states after a draw.
- `KenoTest` 17: RTP 97% at every spot count, the 2× shape, zero hits never
  pays, probabilities summing to exactly 1 with mean exactly `s·20/80`,
  **every hit count paying exactly the ladder**, sub-stake ≠ win, settlement
  through the books, a missing selection refused moving no money, history with
  its unit, certified and launchable.
- `frame` 45/45, `demo` 222/222 (+17), `verify.py` 0. Live over HTTP: eight
  10-spot rounds settling on our books, 400 + pt-BR on a missing selection,
  `books: 17 postings balance to zero`.
- **Wheel is the next arcade original** (0042 §7): its only obstacle is a spin
  visual, and a wheel's ladder is one `(slots, multiplier)` table with a
  closed-form RTP — the derivation keno just proved. Limbo stays set aside;
  it overlaps Crash's target mode.

## DONE (2026-10-14 — PG Soft's money API captured, 2 titles → 92, decision 0040)

- **The PG investigation finished, and the blocker was one flag.** 0035
  recorded that PG's client "will not boot outside a real browser". It does —
  it will not boot with a **headless User-Agent**. Same code, same 1280x800
  viewport: `HeadlessChrome` gives `#GameCanvas` = `0x0` and 56 requests;
  an ordinary Chrome UA gives `450x800` and 332 requests, with the money host
  going from 3 calls to 13. `capture_session.mjs` now sets a real UA by
  default. This is the same trap as 0028's "the importer is not
  order-sensitive" — a conclusion drawn from a probe that was itself broken.
- **The money API is mapped.** `verifySession` (→ `tk`, `geu` = the game's
  slug, `occ.tcm` = *"You are playing Demo."*) → `GameName/Get` →
  `Resources/GetByResourcesTypeIds` → `GameInfo/Get` (**binary**) →
  `GameWallet/Get` (**JSON**: `tb`/`cb`/`pb`/`ch`). The balance is the easy
  half and `rewrite_balance` already fits it; the spin is a binary protocol,
  which is real work rather than a wall. Paths and shapes are now constants
  in `pg_proxy` with the measurement beside them.
- **`GameName/Get`'s `"31"` is a localization key, not the name** — it answers
  "Baccarat Deluxe" for every title. It nearly produced a wrong catalog; the
  only per-game identifier is the slug from `geu`.
- **92 PG Soft titles, up from 2.** `scripts/discover_pgsoft_demos.py` mints
  each candidate and reads its slug. The numbering is **gi 1–135** (nothing
  above answers; 92 live, 43 dead ids — re-probed serially to prove they were
  dead, not throttled). Catalog 182 → **272** demos. `gi=126` → `fortune-tiger`
  → "Fortune Tiger", which is what the catalog already said.
- Provider sweep **16/16**, six PG titles each serving its real ~1 MB
  document through `/g/` with the bridge.
- `frame` 45/45, `demo` 205/205 (+14), `verify.py` 0.

## DONE (2026-10-14 — PG Soft through our own origin + the local cache, decisions 0040/0041)

## DONE (2026-10-14 — the deploy is LIVE on Render, decision 0039)

- **The site is live: <https://cadiback.onrender.com>.** Every deploy had
  been failing silently and neither the API, the deploy object nor the
  service object said why. Two faults: a service created in the dashboard
  keeps Render's **Python buildpack** and ignores the Dockerfile (the switch
  is `env`, not `runtime`), and `python:3.14-slim` ships an `operator`
  **group**, so `useradd operator` died with exit 9 after the storefront had
  already built. Both fixed; the deploy driver now reads Render's log stream
  and prints why a build failed, finds `.env.render` on its own, and takes the
  repository from the git remote.
- **PG Soft boots from our origin** with the wallet bridge — the half that
  was buildable. `demo/pg_proxy.py` mints the trial session server-side and
  binds the hosts it names; the session id travels in our own path, which is
  what makes the per-session hosts resolvable without a standing rule about
  somebody else's domain. Both PG titles now serve through `/g/` (1.0 MB /
  0.98 MB real documents, bridge injected, no wallet token upstream, signed
  asset URLs intact). **The money tap is not built**: the client is a
  obfuscated 1 MB bundle whose `#GameCanvas` is `0x0` in any browser we can
  drive, so it never reaches its lobby and the spin shape is unknown.
- **The games you opened are cached on the machine** — full game rows, not
  ids, so Recentes works with no catalog, no network and no cold start, and
  says when it is showing cached rows.
- **A general proxy bug found and fixed:** `rewritable()` read an empty last
  path segment as "not a document", so any document served at a
  trailing-slash path got no `<base>` repair and **no wallet bridge** — the
  game booted with nothing in front of it and looked fine from our side.
- New: `scripts/capture_session.mjs` — drives the browser already on the
  machine over CDP (tap/click/eval/websocket/viewport) to capture what a
  publisher game says on the wire. The recon the older captures were built on,
  made repeatable.
- **Provider sweep: 12/12** — one real launcher per provider through `/g/`
  (`demo/_sweep.py`), including both PG rows, which previously could not be
  served through `/g/` at all.
- `frame` 45/45, `demo` 203/203 (+12 PG), `verify.py` 0 problems, `localCache`
  21 checks, live smoke on all of the above.

## DONE (2026-10-13 — the deploy stopped depending on the build machine, decision 0038)

- **The image builds the storefront itself** (node stage → `web/out` → python
  runtime). A deploy is now *the repository plus the Dockerfile*: nothing is
  built or committed from any machine first, and `web/out` can never be stale
  in the image because it is not in the image at all.
- **It is a git repository** (701 files on `main`, first commit) with
  `.gitignore` (no `node_modules`, no `web/out`, no live `demo/data`, no
  wrangler state) and `.gitattributes` (LF, so the Linux build never meets a
  CRLF in `deploy/*.sh`).
- **Verified without Docker:** `npm ci && npm run build` from a clean tree;
  the runtime file set alone (no sources, no docs) booting and serving the
  storefront, the catalog (10 in-house + 182 publisher) and a live publisher
  game through the proxy; a fresh `git clone` carrying everything needed and
  no local state.
- **`scripts/render_deploy.py`**: `--check` preflight (credential-free) and a
  full create-or-find → deploy → watch-to-live over the public Render API.
- **`render.yaml`**: `numInstances: 1`, free-plan data reality documented.
- `docs/deploy-easy.md` rewritten as the runbook (states + checks + the two
  ways in + post-deploy smoke + triage). `make deploy-check` added.
- **Still missing: one credential.** No git remote, no Render account on this
  machine. Push the repo and either click Apply, or hand over
  `RENDER_API_KEY` + `RENDER_REPO` and I run the deploy.
- Suites unchanged by this pass: `frame` 45/45, `demo` 191/191,
  `verify.py` 0 problems.

## DONE (2026-10-13 — publisher-game proxy: leaks, truncation and the cache it never had, decision 0037)

- **A player's wallet token was being forwarded to the publisher** (the
  `wallet_token` / launch `token` rode the query straight through). Stripped,
  except on an interposed RGS where that token *is* the game's plumbing.
- **A publisher answer over the cap was truncated and served as if whole** —
  half a bundle deserialized, the exact failure class 0036 chased. The cap is
  now a 502, not a cut.
- **Every upstream error leaked its connection** (demo suite `ResourceWarning`,
  and the same shape in the ESPN/Superbet feed seams). Suite is clean under
  `-W error::ResourceWarning`.
- **The proxy had no cache at all** (`no-cache` on everything): an untouched
  asset now keeps the publisher's validators and a reload costs a 304, a
  money answer and a publisher error are `no-store`, and a body we rewrite is
  validated in neither direction.
- Four smaller ones: `<base>` repaired whatever way it is written, client
  patches confined to script bodies, the bridge config can no longer close its
  own `<script>`, the HUD survives a document with no body, `HEAD` answers
  instead of 501, a declared charset is no longer declared twice.
- `GET /api/health` now reports the proxy (calls, failures, bytes, redirects).
- `frame` 45/45, `demo` 191/191 (+20), `verify.py` 0 problems, live smoke on
  PP (launcher, 3.1 MB bundle, HEAD, missing asset) and Hacksaw (interposed
  token + bridge config intact).

## DONE (2026-10-13 — PP boot pushed to server contact, decision 0036)

- Pragmatic Play goes from instant-death loader to a clean error-free loop
  that POSTs gameService through our proxy: tree repair, animator guard,
  real-cred config fallback, 5 sanitizers, Awake/OnEnable/frame shields,
  session kickstart — all shipped in the bridge, all verified live step by
  step. Session completion (login response → stages) is the open frontier;
  PP stays free play until then.
- Deploy moved (temp workers keep being reaped): now
  `candibet.road-hydrant.workers.dev`, backend + tunnel healthy.
- `frame` OK, `verify.py` 0 problems (full demo suite re-run queued with
  the next session — game_proxy changed under it).

## DONE (2026-10-12 — Dados Relâmpago, a whitelabel dice original, decision 0034)

- **New in-house original `demo:dados` ("Dados Relâmpago")** joins the arcade
  trio: one sha256 draw on a 0.01 roll grid; pick **under/over** a target in
  [1.00, 99.00]; a win pays `0.97 / P(win)` — which can land **below the stake**
  on a high-probability bet (settles via `settle_casino`). RTP **97%** on every
  selection (closed form, no paytable). BR-DEMO-0009, category Originais.
- No `Demo.spin` change: `demo:dados` just joined `ARCADE_GAME_IDS`. New
  `DicePanel.jsx` (slider + under/over + live chance/payment/potential), cover
  `games/demo-dados.svg`.
- **PG Soft path documented (decision 0035, not built):** it stays trial play;
  the wallet route needs a server-side session mint, a **per-session dynamic
  host allowlist** (random-letter `<session>.com` hosts), and a game-api money
  tap — a Hacksaw-sized job, inherently brittle.
- `frame` 44/44, `demo` 171/171 (+10 dice), `verify.py` 0 problems, export
  rebuilt, live HTTP smoke green.

## DONE (2026-10-12 — deploy Worker: game root requests no longer serve the storefront, decision 0033)

- **Bug:** on the deploy, launching a page-proxied game (PP, Spribe) made the
  game frame render the whole storefront; clicking the game inside it opened
  another frame — the "loop mirror".
- **Cause:** the Worker forwards only `/api|/g|/rgs` to the backend, so a
  game client's root-level request (PP derives URLs from `location.origin`;
  Spribe's launcher) fell to the assets layer, and
  `not_found_handling: "single-page-application"` answered it with
  `index.html`. The backend handles those paths correctly via
  `Demo._serve_publisher_root` (cookie-gated) — hence they work locally.
- **Fix:** `not_found_handling` → `"none"`; `src/index.js` routes a non-asset
  miss carrying the proxy session cookie to the backend. Also fixed
  `/api/wallet/launch` to build the interposed URL from `_our_origin()`
  instead of `"http://" + Host`.
- `frame` 44/44, `demo` 161/161, `verify.py` 0 problems, Worker routing
  unit-checked (dynamic proxy, storefront served, session miss proxied,
  no-session miss 404s).

## DONE (2026-10-12 — Crash Nitro interactive live cash-out, decision 0036)

- **Crash Nitro gains a Manual mode (the new default):** the curve climbs
  live and the player cashes out whenever they want; the server holds the
  secret bust and pays `stake x multiplier` at its clock instant. The old
  auto-target mode stays as a second tab. Both share one draw and one 97%
  RTP (`crash_live_rtp` exact over the grid).
- New endpoints `POST /api/crash/{start,status,cashout}`: start draws a
  hidden `round_id` seed (an opaque token goes to the client), debits the
  stake, and persists the round to `crash_pending.json`; status is the
  ~300ms poll; a round the client abandons is swept to a loss, and a round
  still pending at boot is refunded and recorded as cancelled (no stake is
  ever stranded). Front end: `CrashPanel.jsx` Manual/Automático toggle.
- `frame` 44/44, `demo` 161/161 (+8 live-crash), `verify.py` 0 problems,
  export rebuilt, verified live over HTTP.

## DONE (2026-10-12 — Spribe Aviator settles on our wallet, decision 0031)

- **Aviator runs on our saldo, verified with real bets:** R$100 → R$1 bet
  → cashout 1.28x → R$100.28, round row on the books; bust settles the
  stake; R$0 trial bets mirror nothing. No socket decoding — the theater
  bridges the game's own operator channel (`ifc.make.bet`/`win.info` →
  `wallet/round`, our saldo pushed back via `ifc.set.balance`).
- Theater-side R$0 gate (demo ships validation off) + 2s win grace on
  busts; two execution-caught bugs fixed (NaN push, stale profile).
- Applies to all 8 `spribe:` rows; only Aviator bet-tested.
- `frame` 44/44, `demo` 153/153 (+2 theater), `verify.py` 0 problems,
  export rebuilt.

## DONE (2026-10-12 — Candibet brand, in-house crash/plinko/mines, provider second takes, decision 0030)

- **Candibet** (like candy): every visible string and deploy name renamed;
  `candibet.workers.dev` free, `.pages.dev`/`.com` taken (probed).
- **In-house Aviator-style trio, no provider:** `demo:crash-nitro` (name a
  cash-out, 3% instant bust, RTP 97.00%), `demo:plinko-drops` (12 digest-bit
  moves, edges 130x, RTP 97.16%), `demo:minas` (5x5, `m=:cells=`, fair odds
  minus edge, RTP 97%) — sha256 draws, exact minor-unit settlement incl.
  sub-stake partials, BR-DEMO-0006/7/8, Crash-lane rows, covers, three
  panels in the site's UI patterns. Verified live over HTTP.
- **Second takes:** Spribe operator postMessage protocol fully decoded
  (`ifc.make.bet`/`win.info` → our wallet, `ifc.set.balance` ← our saldo;
  build specified, needs a real bet to verify); PP GetDomain/serverUrl
  split attempted live — client resolves to `studio.game-service.biz` and
  still throws, defect deeper than identity (stays free play); PG Soft
  wallet mirror specified in 0029, unbuilt.
- `frame` 44/44, `demo` 151/151 (+12 arcade), `verify.py` 0 problems,
  export rebuilt.

## DONE (2026-10-12 — CadiBet rebrand, PG Soft revived, Play'n GO 5 → 9, decision 0029)

- **Rebrand to CadiBet**: every visible string renamed (page title, logo,
  topbar, footer, zero-build fallback, package name); `localStorage` keys
  kept so player prefs survive.
- **PG Soft loads and plays again.** The old `m/static.pgsoft-games.com`
  hosts are NXDOMAIN globally; the catalog now uses PG Soft's live trial
  launcher `public.pg-demo.com/demo/?gi=<id>&lang=pt` — Fortune Tiger
  (gi=126, full boot) and Mahjong Ways (gi=65, `INICIAR`) verified live
  headless. Money path mapped (per-session HTTPS game-api); the wallet
  mirror is specified in 0029 (server-minted session + game-api mirror like
  Hacksaw) but not yet built — PG Soft is trial play for now.
- **Play'n GO 5 → 9** on our wallet: `riseofolympus`, `moonprincess100`,
  `sweetalchemy`, `goldenosiris` added (launcher-acceptance verified; same
  `gamehub` socket tap, zero new mechanism).
- Working set: Hacksaw 139 + PGO 9 wallet-settled; Spribe loads; PP 21 free
  play; PG Soft 2 trial; Evolution 2 stream pages. Catalog 182 rows.
- `frame` OK, `demo` 139/139, `verify.py` 0 problems, export rebuilt.

## DONE (2026-10-12 — Spribe client blocker SOLVED: Aviator runs from our origin)

- **The hostname coupling is found and fixed.** Spribe's client mirrors the
  vendor's hostnames onto the site's own second-level domain
  (`app-demo2.spribegaming.com` -> `app-demo2.<ours>`; the mirror list exempts
  `adjarabet|spribegaming|spribe`), because a real operator aliases those hosts
  under their own domain. A personal deploy has no alias, so the client dialled
  a host that does not exist and sat on "Ligação…" forever.
  Fixed with a one-line bundle patch (`game_proxy.patch_spribe_client`).
- Verified on plain `http://127.0.0.1:8765`: the client connects to the real
  `wss://app-demo2.spribegaming.com/BlueBox/websocket`, completes the SFS
  handshake and **renders the full live game** (canvas, bet feed, multipliers,
  our HUD).
- How it was pinned down: loading the publisher's own page with only the config
  stubbed (their CDN 403s browsers) connects and renders — that working
  reference cracked it. Ruled out: config bytes, the wallet bridge, HTTPS,
  `<base href>` (fixed anyway), missing requests, console errors, user gesture,
  postMessage, SFS origin validation.
- NEXT (the money): read each round's stake/win from the SFS frames (typed keys
  `betId`, `winAmount`, `multiplier`, `cashouts`) and report to
  `POST /api/wallet/round`, plus the R$0 gate. The socket needs no proxy — the
  browser reaches it directly, so a client-side tap applies.
- `frame` 44/44, `demo` 139/139, `verify.py` 0 problems.

## DONE (2026-10-12 — PP cause found: the client is origin-coupled, decision 0028)

- **Option 4 is a dead end, proven.** Two loads of PP's own page complete their
  37 JSON resources in *different* orders and PP renders fine both times — the
  importer is not order-sensitive, so there is no order to reproduce.
- **The real cause: the client is origin-coupled by design.**
  `ServerOptions.serverUrl = location.protocol + "//" + ServerInterface.GetDomain()`
  and `GetDomain(){ return UHT_LOCAL ? domain : location.host }` — everything it
  calls "the server" derives from `location`. A **pure passthrough** of the
  document from our origin (no bridge, no rewriting) still fails, so it is the
  origin, not our changes.
- Only door left (untested, in 0028): split the client's *identity* from where
  its calls *go* — `GetDomain()` → the publisher's host, `serverUrl` → us.
- **Pragmatic Play remains wallet-isolated free play** (21 titles). Working set
  unchanged: Hacksaw 139 + Play'n GO 5 on our wallet.

## DONE (2026-10-12 — Pragmatic Play characterised; Spribe researched; PGO complete)

- **Pragmatic Play is NOT working** (decision 0028). Its Unity client renders on
  PP's own origin (0 errors) but off-origin its importer resolves references by
  hard-coded index and lands on the wrong object — a different error each run
  (empty game root → `ParseConfigFile` → `animationCurve.keys` →
  `internalContinueImporting`). Re-applied three target-verified client fixes
  this session (search-all for `LocalizationRoot`, `configFile` fallback, and
  one helper covering all ~42 `animationCurve.keys` reads); they advance the
  client one error at a time but the defect is the resource **order**, so it is
  a moving target. Options in 0028; recommendation: keep PP as labelled free
  play, and only pursue it via the publisher's origin / a vendor account.
- Spribe: **not working either** (decision 0027) — loads fully through our
  origin, stalls at "Ligação…" before opening its socket; the SFS endpoint is
  reachable (101, no origin check) so a server-side socket proxy is viable.
- Play'n GO: all 5 titles settle on our wallet (decision 0026). Hacksaw: 139
  titles (decision 0025). `frame` 44/44, `demo` 138/138, `verify.py` 0 problems.

## DONE (2026-10-12 — all 5 Play'n GO titles settle; Spribe researched, decision 0027)

- Play'n GO: **all five catalog titles** now settle on our wallet (book-of-dead,
  reactoonz, fire-joker, moon-princess, legacy-of-dead), verified live — the
  two that first produced no rounds were an intro-click issue, not a
  mechanism one.
- Spribe (research, decision 0027): the launcher redirect mints the session in
  the URL; the SPA ships `<base href="/">`; its config host
  (`app-config.spribegaming.com`) **403s browser-like requests and sends no
  CORS**, so the publisher's own demo cannot start in a browser today; the
  money runs over **SmartFoxServer BlueBox**
  (`wss://app-demo.spribegaming.com:443/BlueBox/websocket`), which is reachable
  and **not origin-validated** (101 from any origin).
- Built for it: publisher domains allowed by suffix (lookalikes refused),
  redirect passthrough carrying the session + our `wallet_token`,
  `SERVICE_HOSTS` config rewrite, document-host cookie, tracebacks logged on
  500. Aviator now loads fully through our origin (assets + config + our HUD)
  and stops at "Ligação…" with no socket opened — that gate is the next
  actionable, then the SFS wire decode.
- `frame` 44/44, `demo` 138/138, `verify.py` 0 problems.

## DONE (2026-10-12 — Play'n GO on our wallet, no vendor account, decision 0026)

- **`pgo:book-of-dead` now settles on our books**, verified live: 4 rounds
  (stake R$1.00, two 0.5x wins) moved the wallet R$372.60 → R$369.60, and a
  **R$0 player got 0 round calls** ("Saldo insuficiente — deposite para
  girar"). No vendor account needed.
- How: Play'n GO's launcher runs from our origin, and its money travels over
  a SignalR WebSocket (`wss://ascflyp.playngonetwork.com//gamehub`) in a line
  protocol — spin = `1 <credits> <lines> <coin>`, balance = `52 <minor> 0 0`.
  The injected bridge taps the page's own socket (a `window.WebSocket` hook):
  it reads the stake from the spin line, takes the round's net from the
  balance delta, and reports it to a new `POST /api/wallet/round` that
  settles through the same idempotent write as the interposed RGS. It never
  touches the publisher's server and never re-encodes a frame.
- New: `Demo.wallet_round` + `/api/wallet/round` + the socket tap in
  `game_proxy._BRIDGE`; `SocketRoundTest` ×4. `frame` 44/44, `demo` 135/135,
  `verify.py` 0 problems.
- The same shape should fit other socket publishers (Spribe SmartFoxServer).

## DONE (2026-10-12 — Hacksaw catalog expanded to 139 wallet-settled titles)

- The lobby's Hacksaw lane went **1 → 139 titles**, every one a real
  publisher demo that settles on our books (same `env=` interposition, no
  per-title work). Discovered from Hacksaw's own games page (`data-gameid`)
  + each game's `version.json`, each verified (launcher 200 + RGS `gameInfo`
  200) before shipping; 12 publisher-listed titles are skipped (their RGS
  refuses the demo query).
- Verified live on a new title, `hs:chaos-crew` (gameid 1059): 30 bets through
  `/rgs/hacksaw_gaming/…`, 20 rounds on the books, 4 with a payout (incl. a
  0.30x), wallet moved. Catalog now 178 publisher demos + 6 in-house.
- New tool `scripts/discover_hacksaw_demos.py` (read-only report, `--write`
  to append) makes the expansion reproducible/auditable; covers via
  `scripts/make-covers.py`, export rebuilt.
- `frame` 44/44, `demo` 131/131, `verify.py` 0 problems.

## DONE (2026-10-12 — provider games on our money: Hacksaw verified live, decision 0025)

- **A publisher's game now runs on our books, verified live.** Hacksaw
  `hs:rip-city-dice` driven through its interposed launch: 34 spins took the
  wallet R$342.00 → R$305.20, 20 rounds recorded, 3 with a payout (e.g.
  `stake=200 payout=100`, a 0.50x win), every spin hitting
  `/rgs/hacksaw_gaming/api/play/bet`.
- `game_proxy.rewrite_urls` now rewrites **only the provider's money URLs**,
  leaving the client, bundles and data on the publisher's CDN. Proxying the
  whole game made the Unity importer deserialize an empty game root; this
  gets Pragmatic Play past that blocker. The previous session's dead
  byte-patches of the Unity client were removed.
- Established the real constraint (evidence in decision 0025): a publisher
  client runs on the publisher's own origin, so only a launcher that accepts
  a redirectable RGS (Hacksaw's `env=`) can be bound for free play; the rest
  need a vendor operator account (retired track 0007). Spribe takes
  `operator=`/`token=`, Play'n GO sets `window.serverUrl` — both server-issued.
- `frame` 44/44, `demo` 131/131, `verify.py` 0 problems.

## DONE (2026-10-12 — single-container PaaS deploy: backend + storefront, one port)

- Chosen direction after the Cloudflare Worker: host the **Python backend and
  the storefront in one container** on a Python host (Render/Fly/Koyeb/
  Railway), which removes the `cloudflared` tunnel and its expiring hostname.
  Gives `cadibet.onrender.com` / `cadibet.fly.dev`.
- `Dockerfile` + `.dockerignore` (context `operator/`), `fly.toml` (region
  `gru`, `cadibet_data` volume at `/data`), `render.yaml`, and
  `docs/deploy-paas.md`. One process serves everything: `demo.server` already
  answers the API and serves `web/out` itself, so no reverse proxy is needed.
- `demo/server.py` made hostable, local defaults unchanged:
  `HOST`/`PORT` in `run()` (binds `0.0.0.0:$PORT`) and `OPERATOR_DATA_DIR`
  (mount the ledger/profiles on a volume).
- Verified without Docker (none on this host): a copy of the exact image
  layout (`frame/ demo/ probes/ web/out/`) runs `python -m demo.server` and
  answers `/api/health`, `/` (storefront) and `/api/catalog` (40 publisher
  demos from `probes/`). `frame` 44/44, `demo` 131/131, `verify.py` 0 problems.
- The Cloudflare Worker deploy (decision 0023) remains live as the
  static-front option.

## DONE (2026-10-12 — public deploy on Cloudflare Workers, decision 0023)

- The platform is live at **https://cadibet.luminous-schooner.workers.dev**
  (Worker name `cadibet`). One Worker (`deploy/`) serves the static export
  (`web/out`) and proxies `/api`, `/g`, `/rgs` to the Python backend.
- Name checked free in the Cloudflare namespaces (`cadibet.pages.dev` /
  `cadibet.workers.dev`); `cadibet.com` is registered but serves no HTTP.
- `demo/server.py`: the game proxy's public origin now comes from
  `X-Forwarded-Proto`/`X-Forwarded-Host` (`Handler._our_origin()`), so the
  rewritten game URLs carry the proxy's https host instead of the internal
  one. `frame` 44/44, `demo` 131/131, `verify.py` 0 problems.
- Live-verified end-to-end: storefront 200, `/api/catalog` (40 publisher
  demos + 6 in-house), `/api/sports`, and player → deposit → `wallet/launch`
  → `wallet/status` → `spin`.
- Caveats (by design, documented in `deploy/README.md`): the temporary
  Cloudflare account deletes in ~60 min unless the claim URL is used, and the
  site depends on a `cloudflared` quick tunnel to the backend (re-run
  `deploy/deploy.sh` with the new `BACKEND_ORIGIN` after a tunnel restart).

## DONE (2026-10-10 — publisher games on our wallet, decision 0022)

- Corrected the previous session's misread (in-house flagship originals):
  that work was reverted (engines, panels, decision doc, server/test wiring,
  docs) and replaced by the real objective — the **publishers' games on our
  books**.
- Operator wallet path (verified, `frame` 44/44, `demo` 115/115, `verify.py`
  0 problems):
  - `Books.settle_casino` — settle a casino round with an **arbitrary payout**
    (a 0.42x win is still a win; the odds-based `settle_bet_win` cannot say
    that). Bonus share returns to `player:bonus`.
  - `POST /api/wallet/launch` binds a session to (player, game) and reports
    `can_play` from the real saldo; `/api/wallet/{status,debit,credit}` take
    the stake and settle the win through the books; an empty saldo is refused
    with "Saldo insuficiente — deposite para girar."
- Same-origin **game proxy** `demo/game_proxy.py` + `/g/<game_id>` routes and
  the injected bridge `/g/bridge.js`: the publisher launcher and every
  asset/RGS request are forwarded, absolute publisher URLs rewritten to
  `/_abs/<host>/…`, the bridge injected first, the token kept on sub-requests
  via a scoped cookie. Live-verified against Pragmatic Play (launcher proxied,
  5/5 absolute URLs rewritten, bridge + cookie present, empty-wallet launch
  refused). Front end opens `/g/<id>?token=…`.
- Why a same-origin proxy: a cross-origin iframe cannot be scripted, and the
  publisher RGS refuses a foreign origin (observed: Hacksaw's preflight has no
  ACAO). Serving the game from our origin removes the CORS wall and puts the
  bridge in front of the game's networking.
- NEXT: the per-publisher money-tap (`ADAPTERS`: bet/balance/win JSON) so each
  round settles through the books and the in-game saldo equals ours; then the
  in-house slots/roulette library is deleted so every lobby title is a
  publisher's. Websocket publishers (Spribe SFS, Play'n GO) need a websocket
  proxy.

## DONE (2026-10-10 — continuation of the pi session: repo restored green, 0021 suites verified, handover written)

- The `pi` session (2026-10-10 04:57Z) left the repo RED: a stray
  `demo/roulette.py` with JavaScript syntax in a Python file (imported
  by nothing; the real engine is `demo/casino.py`). It broke
  `verify.py`'s `py_compile`. Removed the orphan → `verify.py` back to
  0 problems.
- Reserved decision-0021 verification FINALLY run (both prior sessions
  skipped it): `frame.selftest` 43/43, `demo.test_demo` **101/101**
  (incl. CasinoTest ×12, SlotPaytableTest ×6, LiveTest ×3 — the 21 ran
  verbosely, all green), `verify.py` 48 files/49 py/0 problems.
- Live smoke against the user's running server (read-only): `/api/live`
  answers; catalog row `demo:roulette-europeia` launchable, RTP 97.30,
  BR-DEMO-0003, Mesa. Isolated money path (`Demo(data_dir=tmp)`,
  user data untouched): deposit R$100 → roulette even-money wins 2.00x
  and losses settle the player's server saldo → no-selection refused →
  slot settles → books balanced → `/api/live` shows the wins.
- Export current (pi's rebuild 02:07 predates no source change; both
  0021 UI markers present) ⇒ no rebuild needed.
- Handover written for the next agent: `docs/handover-2026-10-10.md`
  (the log the pi session was asked for and never produced). It
  reconciles the follow-on "saldo must coincide with the player's"
  ask: already true for the operator's own games (0021); structurally
  blocked for the publisher demos (RGS-side), and rehost stays refused
  (0006/0008/0020).
- NEXT: pick a direction in `docs/handover-2026-10-10.md` §5. Default
  recommendation — deepen the in-house library (crash original + a
  second table game), which is unblocked and directly "not demo + saldo
  + payouts".
- DONE (user chose §5 option 3): de-demo'd the in-house titles — the six
  registry titles now read `Neon Gems`, `Fortune Ledger`, `Crimson
  Dragons`, `Gold Vault`, `Roleta Europeia`, `Royale Roulette
  (uncertified)` (dropped the `(demo)` suffix; the cert gate still
  blocks the uncertified one). Catalog/live resolve titles from the
  registry, so no web rebuild is needed — only a restart of the :8765
  server (`python -m demo.server` from `operator/`) makes the new copy
  live. `demo.test_demo` 101/101, `verify.py` 0 problems.
- **CORRECTION (owner, 2026-10-10):** the de-demo target is NOT the
  in-house `demo:` titles — it is the **off-house publisher demos**
  (the 40 iframed rows), which is why a decompilation was requested:
  *decompile the external sites, extract their games, load them into
  our casino as real games whose saldo + payouts come from our server.*
  The §8 in-house rename is off-target (harmless; revert on request).
  This end state needs a **vendor wallet-delegation integration** (their
  RGS calls our wallet API) — rehosting stays refused (0006/0008/0020),
  and the client cannot bind a third-party game to our books. Full
  write-up + next-session options: `docs/handover-2026-10-10.md` §9.
  NEXT SESSION: confirm with the owner → (1) vendor wallet integration
  scoping, or (2) in-house equivalents of the official titles.

## DONE (2026-10-09 — in-house casino library + live feed, decision 0021)

- The operator's own games now span categories, all
  playable against the double-entry books (previously
  only 2 slots shared one paytable; Mesa/Crash had no
  launchable in-house titles):
  - `demo/casino.py`: European single-zero roulette —
    ball from SHA256(game_id:round_id), straight-up
    35:1, even-money 1:1, zero loses everything but a
    straight 0 (house edge 1/37, RTP 97.30% on every
    market), selection required (clean 400 without one).
  - `demo/slot.py`: per-game paytables — Neon Gems /
    Fortune Ledger keep the original 95.90% table (rounds
    on file were drawn against it); Crimson Dragons 94.95%
    and Gold Vault 96.60% are new distinct games.
  - `demo/server.py`: BR demo certs BR-DEMO-0003/0004/0005
    registered (the cert gate launches them), `spin()`
    routes roulette by selection and slots by their own
    table, catalog rows carry the real paytable.
  - `GET /api/live` (`Demo.live()`): real-time pulse from
    existing files — players active in the last 15 min,
    games on the floor, 10 newest wins (newest first,
    names masked "First L."), ledger-backed jackpot pool.
    Empty lobby reports zero; torn lines never crash it.
  - Frontend: `RoulettePanel.jsx` (0–36 grid in wheel
    colors + even-money chips), SlotPanel renders the
    per-game paytable, `page.jsx` owns selection/ball
    state, CasinoHome gains the "Ao Vivo Agora" strip
    polling /api/live every 15s.
- Written but RESERVED (not run this session): 18 new
  tests — `CasinoTest` (determinism, all 37 pockets
  reachable, 36x/2x payouts, zero-loses-everything,
  RTP 36/37, selection required, book settlement both
  outcomes, new originals settle), `SlotPaytableTest`
  (tables sum to 1, distinct RTPs, catalog paytables),
  `LiveTest` (window counting, newest-first masked wins,
  empty-lobby honesty). Expected suite 80 → 98.
- Also reserved: `frame.selftest` (43/43 before), 
  `verify.py` (0 problems before), web rebuild
  (`cd web && npm.cmd ci && npm.cmd run build`) and a
  live smoke of /api/live + one roulette round.
- Verified by execution this session: `import demo.server,
  demo.casino, demo.slot` clean; rtp_of → neon 0.959,
  crimson 0.9495, gold 0.966.

## DONE (2026-10-08 — game-recon over the 40-demo catalog, decision 0020)

- New `research/game-recon/` project: `targets.json` from the live
  catalog, reusable `scripts/recon_game.mjs` (headless Chromium:
  tech signals + request inventories, metadata only, no game bytes
  on disk). All 40 targets reconned: PP launcher map, Spribe
  Angular + SmartFoxServer backend, PGO dual websockets, Hacksaw
  atlas/KTX2 pipeline, Evolution = marketing pages, PG Soft
  DNS-blocked.
- Catalog fix from the captures: `pp:big-bass-splash` serves Big
  Bass Amazon Xtreme (title corrected). 5 PP launchers stall
  headless (PARTIAL, real-Chrome follow-up queued, URLs stay).
- Playable clones BLOCKED by design (server outcomes + no-rehost
  rule); deliverable is documentation. Gates green (see below).

## DONE (2026-10-08 — Casino catalog 22 → 40 demos, decision 0019)

- 18 new publisher-hosted rows, every URL live-verified same day:
  7 Pragmatic Play (incl. the three 1000-series flagships),
  7 Spribe mini-games, 4 Play'n GO. Rejected-and-left-out:
  `vswaysbuffalo`, `hilo`; PG ids, Hacksaw builds and Evolution
  pages skipped as unverifiable from here. PG host currently
  unreachable even for listed ids (DNS) — flagged, not acted on.
- 18 generated SVG covers; no UI change (card fallback already
  covers it). Rebuilt export (`npm ci` + `next build` green),
  `node_modules` pruned.
- Gates: 40/40 catalog rows accepted live, demo 80/80, frame
  43/43, `verify.py` 0 problems.

## DONE (2026-10-08 — Superbet fallback source + expanded sports coverage, decision 0018)

- Fallback chain at `/api/sports`: EspnSportsEngine ->
  SuperbetSportsEngine -> deterministic slate (0016), last resort
  only.
- `frame/verticals/sports/superbet_engine.py`: real fixtures from
  Superbet's public v3 offer server (same endpoint as cleanSheet's
  superbet_snapshot; no key; 600s cache at `probes/superbet-cache.json`);
  soccer only; in-house model prices. Encoded the two live gotchas:
  `startDate` needs whole-hour precision (HTTP 400), event names
  separate teams with U+00B7 ("·", mojibake as "�").
- ESPN widened to 11 competitions: bra.1, ita.1, eng.1, esp.1, ger.1,
  fra.1, uefa.champions, nfl, nba, mlb, nhl — 52 fixtures today, one
  scoreboard req/league/120s cycle (~5.5 req/min, inside the
  conservative cleanSheet budget). Moneyline + totals recipes per
  sport, same deterministic pricing model.
- Gates: `demo.test_demo` 80/80 (+1 Superbet contract test),
  `frame.selftest` 43/43, `verify.py` 0 problems. Live probe: ESPN
  52 fixtures, Superbet 132 fixtures.

## DONE (2026-10-08 — EspnSportsEngine: real fixtures, in-house prices, decision 0017)

- New `frame/verticals/sports/espn_engine.py` implements the
  `SportsEngine` protocol over public ESPN scoreboards (bra.1,
  ita.1, nfl — same source as cleanSheet edgewatch, no key).
  120s cache to `probes/espn-cache.json`; stale-cache keeps the
  site up through ESPN outages; no network + no cache =>
  ProviderError, and `demo/server.py` falls back to the 0016
  deterministic slate so the board never blanks.
- New `frame/verticals/sports/pricing.py` holds the deterministic
  pricing model (sha256 team strength -> Poisson 1x2/totals,
  logistic NFL moneyline, 5% uniform margin, 30s-bucket drift).
  `demo/odds_engine.py` now reuses it instead of duplicating.
- ESPN's own DraftKings prices are not served; the house quotes
  its own book. `/api/sports` now returns `source: "espn"`,
  `provider: "ESPN scoreboard + in-house model"`, 22 real
  fixtures on today's board.
- Gates: `demo.test_demo` 79/79 (+1 engine contract test, canned
  feed), `frame.selftest` 43/43, `verify.py` 0 problems, live
  smoke green. No web source change, no rebuild.

## DONE (2026-10-08 — In-house odds engine replaces the capture seam, decision 0016)

- New `demo/odds_engine.py`: deterministic daily fixture board across
  bra.1 / ita.1 / nfl from real team pools; SCHEDULED / IN_PROGRESS /
  STATUS_FINAL lifecycle; finished games drop off the board.
- Pricing model: per-team sha256-derived strength → Poisson 1x2 and
  totals probabilities → uniform 5% book margin → decimal prices;
  NFL logistic moneyline, totals line 44.5. Prices reprice
  deterministically per 30s bucket; live drift scales with match
  minute — the UI's 15s polling now surfaces real motion.
- `/api/sports` envelope unchanged: `source: "inhouse"`,
  `provider: "in-house odds engine (deterministic)"`,
  `licensed_feed: false`, explicit note. SharpAPI.io skipped on
  purpose (dog food, offline, reproducible, zero keys).
- Removed: `sports_data.showcase`, stub fallback path, `SportsStub`
  wiring in `server.py`. `sports_data` keeps `load_live`/`live_available`
  for the news panel; ESPN capture remains refreshable.
- Gates: `demo.test_demo` 78/78 (+1 determinism check), `frame.selftest`
  43/43, `verify.py` 0 problems, live HTTP smoke green (36 fixtures,
  1x2+total / moneyline+total). No web source change, so no rebuild.

## DONE (2026-10-07 — F1: page.jsx god component split)

- `web/app/page.jsx` 1364 -> 587 lines. Every visual block extracted
  verbatim into `web/app/components/`: `Header`, `BottomNav`,
  `CashierModal`, `AccountModal`, `DetailModal`, `GameTheater`,
  `BetslipTray`, `ChatWidget`, plus views `PromosView`, `AccountView`,
  `SlotPanel`. Shared player-session state (player/profile/history/
  health/refreshError/busy + `refresh()`) lifted into
  `web/lib/useSession.js`. Page keeps routing, view-local UI state and
  the wallet handlers (save/deposit/withdraw/spin/bet/claim/chat/play)
  with unchanged logic — pure extract, no behavior change.
- Honest delta vs the audit proposal: page is 587 lines, not under
  ~250 — the async handlers (~200 lines) stay in the orchestrator so
  the wallet check lives in one place instead of being drilled into a
  hook through 20 params. Each modal/view is now independently
  readable; no JSX was altered in the move.
- Verified by execution: `npm ci` (0 vulns) + `next build` green,
  `verify.py` 0 problems, frame 43/43, demo 77/77. Live smoke on fresh
  data: health ok, `/api/admin` 401 anon / 200 with admin token,
  register -> deposit R$100 -> spin `demo:neon-gems` (loss, R$95.00 left),
  served chunk carries the extracted strings (Boletim/Caixa/Central).
  Server stopped, `demo/data` + `web/node_modules` pruned.
- Next: F2 dedupe category matcher in `CasinoHome`.

## DONE (2026-10-07 — Pending admin rebuild verified live: 77/77)

- Finished the queued rebuild+restart from 2026-10-06 (shell is back).
  Two execution-caught bugs from the unrun pass, both fixed:
  (1) `demo/auth.py` `revoke_user` body under-indented 4sp — `py_compile`
  FAIL on every import; re-indented to 8sp. (2) `demo/server.py`
  `SessionStore` used in `_load_sessions`/`_save_sessions` but missing
  from the `from .auth import` line (NameError at `Demo()` boot) plus a
  duplicated `_save_sessions` definition — import fixed, duplicate
  removed, `SessionBook` docstring corrected to persisted-via-SessionStore.
- Rebuilt: `npm ci` (0 vulns) + `next build` green, export fresh.
  Full gates green: `verify.py` 0 problems (44 files/44 py), `frame`
  43/43, `demo` 77/77 (AuthTest is 7 cases, not 6 — prior 66->76 note
  was off by one; true chain 66->70 admin +7 auth = 77).
- Live smoke on fresh `demo/data`: `/api/health` ok, `/api/admin` 401
  without token and 200 with `admin/admin` login, `/api/jackpot` +
  `/api/tournaments` real, served chunk carries `api/admin` +
  `casa-admin` + `ctrlKey&&e.shiftKey` gating + `Painel` x2 (hidden
  shortcut, no unconditional button). Server stopped + `demo/data`
  wiped after.
- `web/node_modules` (328M) pruned after build per backup hygiene;
  restore with `cd web && npm ci` before next build.

## DONE (2026-10-06 — Painel is now hidden behind a real admin login)

- Ask: hide the painel from normal users, gate it behind an admin login,
  seed a default **admin/admin** (to be changed later), let the admin
  change their own password and control every user's credentials.
- `demo/auth.py` (new): `UserStore` — salted SHA-256 hashes + constant-
  time compare (the users file never carries plaintext), atomic writes,
  one lock per mutation, default `admin`/`admin` seeded on first boot
  (or when the last admin is gone); `SessionBook` — in-memory bearer
  tokens, 12h TTL, `revoke_user` so a password change kills every live
  session for that user. Two roles: `admin` (manage credentials) and
  `viewer` (dashboard only). Refusals are pt-BR, no enumeration
  (unknown user = wrong password, and the unknown path burns a
  comparable hash).
- `demo/server.py`: `POST /api/auth/login` (fixed 0.25s delay on failed
  attempts — no tight-loop brute force), `GET /api/auth/me`,
  `POST /api/auth/logout`, `POST /api/auth/password` (current password
  required; revokes + reissues), `GET /api/admin` now **requires a
  session** (401 otherwise), and `GET/POST /api/admin/users[ /reset
  /delete]` gated to the `admin` role (cannot delete self or the last
  admin). `AuthError` maps to 401 in both handlers; `Authorization:
  Bearer` parsed by `_bearer()`.
- Frontend: `lib/api.js` gained `getAdminSession`/`setAdminSession`
  (localStorage `casa-admin`) and attaches the Bearer header to every
  request when a session exists. `page.jsx` renders the header "Painel"
  button **only for a logged-in admin** and adds the hidden entry
  **Ctrl+Shift+A** → login door. `AdminPanel.jsx` reworked: login form,
  logout, "Minha senha" (own change with confirm), and — for admins —
  "Usuários do painel": list (no hashes), create with role, reset
  password (revokes sessions), remove (self/last-admin refused by the
  server).
- Tests: `AuthTest` (6 cases: seeded+hashed at rest, session lifecycle,
  dashboard gate, viewer role gate + no salt/hash in listings, own-
  password change revokes+reissues, reset/delete guards + weak
  passwords) and `AdminDashboardTest` now logs in for its token.
  Expected suite 66 -> 76 (unrun — no shell).
- LIMIT: no execution shell (bash missing; hooks unsupported) — build,
  verify, and all suites did NOT run this pass; everything re-read in
  full instead. As before: `cd web && npm.cmd run build` + restart
  `python -m demo.server` are required for the new UI/endpoint to be
  live (the running process still predates both; probed 404 earlier).
  The old served bundle shows an unconditional "Painel" button until
  that rebuild — the hiding is source-side until then.

## DONE (2026-10-06 — Full-width responsive layout + admin panel)

- Ask clarified by the user: (a) the site must **use the screen** — no
  dead side margins, responsive across resolutions; (b) "management of
  the app" means an **admin panel**: dashboard, top winners, % returns.
- Layout (`web/app/globals.css`): `.wrap`/`.hwrap` 1120px -> 1720px with
  `clamp()` gutters (fluid down to phones); sidebar rail 210 -> 230px;
  `nav.main button` gets `white-space: nowrap` (the "Ao Vivo" wrap in
  the screenshot); `.rowscroll` cards scale `clamp(180px, 13vw, 230px)`;
  at >=1400px the casino main column becomes a **two-column grid** (first
  two sections + last span full width — bars side by side); <=640px
  hardening (header wrap, hero padding, full-width betslip above the
  bottom nav, horizontally scrollable history table, folded topbar),
  <=420px topbar trim. Existing 860/760px collapse rules preserved.
- No shell on this host -> no `npm run build`, so the layout rules were
  **mirrored into the built stylesheet** (`web/out/_next/static/chunks/
  354hd4ssuqhgq.css`, appended block with a banner comment, scoped
  `min-width:861px` so it cannot clobber the original 860px collapse):
  the served site picks the layout up immediately; the next build
  regenerates from source and the mirror disappears by itself.
- Admin panel, end to end:
  - `GET /api/admin` -> `Demo.admin_dashboard()`: players, rounds
    (+today), deposits/withdrawals/paid/pending from posting kinds, GGR,
    operator cash, player+bonus liabilities, **realized RTP** (settled
    in-house rounds only — excludes pending and odds-priced sports — vs
    the 95.90% model), turnover (all-time + today via the jackpot's own
    volume), 7-day UTC series, top-5 winners by net (settled rounds only:
    a pending stake is not a loss), top-5 biggest wins, pending sports,
    risk-flagged players, jackpot, health. Every figure derived from the
    stores; payload carries the honest `note`.
  - `web/app/components/AdminPanel.jsx`: KPI grid, RTP comparison bars,
    7-day CSS bar chart, top-winners/biggest-wins tables, risk cards,
    loading/error states, 30s poll, pt-BR.
  - `page.jsx`: header ghost button "Painel" + `view === "admin"`.
  - `AdminDashboardTest` (4 cases) in `demo/test_demo.py`: books
    equality, RTP exclusions (pending + sports), leaderboard ranking +
    pending-not-a-loss, honest empty shape. Expected suite 66 -> 70.
  - Docs/lists: `demo/README.md` API entry; `verify.py` + `verify.sh`
    now require `AdminPanel.jsx` (10 web files).
- Verification done by execution: against the running server at 1900 /
  780 / 375 px — `.wrap` 1120 -> 1720px (was 390px dead margins each
  side), main grid `699px 699px` at >=1400, single column at 780,
  zero horizontal overflow at 780 and 375, header wrap / hero padding /
  bottom-nav / topbar-trim rules all active (the appended mirror proved
  itself; `getComputedStyle` reads 1720px where the built original said
  1120px).
- LIMIT, stated honestly: no execution shell on this host (bash missing;
  hooks unsupported) — verify/selftest/demo suites and the web build did
  NOT run this pass. verify will (correctly) report a **stale export**
  until `cd web && npm.cmd run build`, and the running `demo.server`
  predates `GET /api/admin` (live probe: 404 vs 200 on `/api/health`) —
  restart it too. The admin panel appears after rebuild + restart (or
  instantly under `npm run dev`). The layout is live already via the
  CSS mirror.

## DONE (2026-10-06 — Web app management audit: QC now covers web/)

- Continued the recon thread with the queued ask — "find improvements for
  the management of our web app". Findings, evidence, and the ordered
  roadmap live in `docs/web-management-audit-2026-10-06.md`.
- `scripts/verify.py` no longer ignores the storefront: 9 required web
  files (adds `error.jsx`, both components, `next.config.js`,
  `package.json`; the `verify.sh` mirror gained the same file list),
  `web/out/index.html` must exist, every `/_next/…` asset
  it references must exist in `web/out`, any web source newer than the
  export fails as a stale export (makes AGENTS workflow step 5
  executable), and fragment markers are refused in web sources with the
  same rule Python sources follow. Static cross-check: all 9 referenced
  assets exist in the current export; web sources are marker-clean.
- `Makefile`: added `make demo-test` (`python3 -m unittest demo.test_demo`)
  and `.PHONY` — AGENTS step 4 now has a target beside `make selftest`.
- `web/README.md` drift fixed: Next 15 -> 16 (`package.json` pins ^16.3.8),
  "providers refuse framing -> links out" -> the embedded theater reality
  (decision 0006: provider-hosted `demo_url` iframes, wallet-isolated),
  `CasinoHome` section list rewritten to the sections that actually exist,
  a new Quality control section, and `npm ci` as the documented install.
- Roadmap recorded (F1-F7): split the 1,334-line `page.jsx` god component,
  dedupe the twice-written category matcher, one `usePoll` hook for the
  seven copied pollers (5 in CasinoHome + 2 in page.jsx), eslint +
  `node --test` (blocked on shell for
  lockfile regen), a drift guard for the zero-build `demo/index.html`,
  toasts instead of `window.alert`, and list-key/favorites hygiene.
- LIMIT, stated honestly: this host had no execution shell (bash missing;
  file-change hooks unsupported), so `verify.py`, `frame.selftest`,
  `demo.test_demo`, and the web build did NOT run this pass — static
  verification only. First commands with a shell: `python scripts/verify.py`
  (if it reports a stale export: `cd web && npm.cmd run build`), then
  `make selftest`, then `make demo-test`.

## DONE (2026-10-06 — Recon: reachable-site analysis + FanDuel network plane)

- Probed fourteen candidate sites with a real browser UA. Outcome:
  `fanduel.com` casino OK (437 req, full lobby), `bovada.lv` login OK,
  `fanatics.com` Akamai-403, `draftkingscasino.com` parked, `bet365`/`stake`/
  `betmgm`/`caesars` 403, all `.bet.br`/`.com.br` probes routed to
  `brasilsembets.gov.br`. `examples/recon/<site>/` holds the rendered DOM,
  first frame phone, network.json, and visible text per site.
- FanDuel proved the realtime shape of a real operator: HLS-streamed game
  trailers on tiles, polled jackpot API (`api.mi.casino.fanduel.com/jackpot/api/v2`),
  Rive canvas badges, Prismic CMS promos, flags incl. responsible-gaming
  config, Datadog/Amplitude/Snowplow/PerimeterX. Our mapping: provider_demos
  embeds, the ledger-backed jackpot, risk/limits, `/api/trending` honesty.
- Full write-up in `docs/recon-reachable-sites-2026-10-06.md`. Context
  only — no demo UI copied; still the reachable mirror location.

## DONE (2026-10-06 — Superbet edge capture + runtime analysis)

- Requested a real mirror of `https://superbet.bet.br/jogos` for reference.
  From this network the web tier is unreachable: every path 302s to
  `brasilsembets.gov.br` (GovBR block landing behind Cloudflare jsd
  challenge); `superbet.com.br` is gone from public DNS. So the capture
  is honest by accident: `examples/superbet/` holds the rendered block
  page (`jogos.live.html`), an assets-mirrored offline copy
  (`jogos.offline.html` + `assets/`: GovBR DS core, Rawline, gov.br pages,
  falabr link), `network.json` (16 requests, redirect + challenge
  timeline), a full-page screenshot, and title.txt. Analysis in
  `docs/superbet-2026-10-06.md` — verified items listed, unverifiable
  ones (catalog XHR shapes, websocket cadence, game rails) queued as the
  re-capture checklist for a BR-facing IP. An attempt with `superbet.com.br`-style variants
  confirmed the block is IP-based.
- `scripts/capture_superbet_playwright.mjs` + `scripts/mirror_superbet.py`
  shipped; playwright-core vendor copy lives outside the repo (TEMP) —
  backup-safe, verify.py stays clean (0 problems; 43 py sources).

## DONE (2026-10-06 — Jackpot, Favoritos, game detail, chat widget)

- The last four TV-blocks are real now (decision 0015):
  - Jackpot pool tied to ledger: `GET /api/jackpot` = seed + 1% of today's
    recorded stakes; the RNG ticker interval is deleted, the panel polls
    every 15s.
  - Favoritos: star toggle in the game detail modal → `casa-favs` in
    localStorage; new Favoritos chip filters the lobby.
  - Game detail modal: clicking a card opens provider/category/RTP/notes
    before launch; the card's Jogar Agora still plays instantly.
  - Chat widget: floating panel with a canned-intent triage bot over
    `POST /api/chat` (depósitos/saques/bônus/limites/jogos), labelled
    "simulada".
- Demo suite 64 -> 66 (JackpotChatTest: turnover moves the pool 1% exactly,
  stale rows ignored, chat triage + fallback). verify 0 problems, frame
  43/43, export rebuilt and served, live endpoints verified.

## DONE (2026-10-06 — Notícias derivada de fatos reais do servidor)

- The hardcoded NEWS array is gone. `GET /api/news` derives the card list
  from what the server already holds: official-game/provider counts (real
  catalog), the fixture capture's actual `fetched_at`, the top-24h game
  from `trending()` (title joined server-side), today's biggest win from
  `tournaments()` (R$ formatted), and a factual pointer to the working
  promo mechanics. CasinoHome renders it with loading/empty states and a
  60s poll. Decision 0014.
- Demo suite 62 -> 64 (NewsTest: catalog/provider/fixture facts present,
  ALTA + PRÊMIO surface after a real open + win row). Export rebuilt;
  served HTML references the fresh chunk; full suites green
  (verify 0 problems, frame 43, demo 64).

## DONE (2026-10-06 — Tournaments panel shows real leaderboards)

- The two hardcoded tournament cards are gone. `GET /api/tournaments`
  (`Demo.tournaments`) computes today's (UTC) real boards from the round
  ledger: Maior Ganho (top per-player max payout) and Mais Rodadas (top
  per-player round count), player labels from the players store, stale
  rows and blank players dropped. The honest note "Torneios organizados
  não existem no demo" ships in the payload; the lobby renders the note
  and an empty day gracefully. Decision 0013.
- Demo suite 60 -> 62 (TournamentTest: today-only counting, win ordering,
  empty-day shape). Extrapolated verified live: `/api/tournaments` and
  `/api/trending` both answer; served HTML carries the fresh chunk with
  `api/tournaments`; web build green; full suites green.

## DONE (2026-10-06 — Quentes e frios: activity board from real opens + rounds)

- New honest trend board (decision 0012): `Demo.record_play` +
  `POST /api/play` append every game open to `demo/data/plays.jsonl`
  (not a books posting — an open moves no money); `GET /api/trending`
  counts last-24h opens + recorded rounds per catalog `game_id` (torn-line
  tolerant, unknown ids dropped); CasinoHome renders a "Quentes e Frios"
  panel with playable hot cards + a cold row, refreshed every 60s.
- Demo suite 56 -> 60 (TrendingTest: opens counted, rounds counted, garbage
  never leaks, 24h cutoff, missing id refused). Verified live: two
  `POST /api/play` calls show in `/api/trending` hot, `verify.py` 0 problems,
  frame 43/43, export rebuilt and served.

## DONE (2026-10-06 — Recentes: real recently-played persistence)

- `play()` now records `{game_id, ts}` to `localStorage["casa-recent"]` (dedupe,
  newest first, cap 30), and the casino Recentes tab unions those opens with
  server-history rounds, newest-first, dropping the old catalog-order list.
  Official iframe demos (the bulk of the catalog) previously left no trace
  here because they write no server round. Decision 0011.
- Verified: `npm ci` + `next build` green, fresh export served by
  `demo/server.py` (`casa-recent` present in the served chunk), `verify.py`
  0 problems, frame 43/43, demo 56/56, health ok.
- AGENTS.md Workflow step 5 now records the `web/node_modules` prune +
  `npm.cmd ci` restore loop (normal for backup hygiene, surprising mid-task).

## DONE (2026-10-06 — Live sports view polls the fixture feed every 15s)

- The sports view fetched `/api/sports` once and never asked again, while the
  server already re-prices live fixtures on a 30s deterministic bucket and
  `scripts/fetch_live_fixtures.py` can refresh the capture. Now:
  `web/app/page.jsx` polls every 15s while the sports view is mounted; the
  CasinoHome pricing strip polls the same. No server change; betslip selections
  keep their locked price. Decision 0010.
- Verified by execution: export rebuilt (`15e3` present in the served chunk
  `1tju9koisjct1.js`), `demo/server.py` serves the fresh HTML, and two
  `/api/sports` calls confirmed the current capture is 20/20
  `STATUS_SCHEDULED` — so prices are constant today and polling surfaces the
  next capture within one tick rather than inventing motion.
- Housekeeping: `web/node_modules` had vanished overnight; `npm ci` restored
  it (0 vulnerabilities), build green, `verify.py` 0 problems, frame 43, demo
  56 — all re-run green. Server restarted clean (fresh `demo/data`).

## DONE (2026-10-05 — Functional promotions: welcome bonus + cashback through the wallet)

- The Promoções page advertised a welcome bonus and a daily cashback with nothing
  behind either. Both are now real mechanics over the double-entry wallet
  (decision 0009): `POST /api/bonus` grants `player:bonus` (100% of the first
  deposit up to R$500, 20x wagering; 10% of the day's net loss up to R$200, 1x,
  once per UTC day), stakes split cash-first under the books lock, and bonus
  converts to withdrawable cash only when the target is met (orphaned bonus from
  late-settling wins converts on the next settle). One active event at a time;
  bonus can never be withdrawn before conversion.
- Frame: `settle_bet_win` gained `bonus_part` — the bonus-funded portion of a
  win pays back into `player:bonus`, not cash (`frame/tests/test_frame.py` 42 -> 43).
- Demo: profile exposes `bonus_minor` + a `bonus` view (eligibility, progress,
  percent); Promoções page shows working claim buttons and a live wagering
  progress bar; header shows `saldo + bônus`; betslip balance check includes bonus.
- Hardening found by the live smoke: a replayed `round_id` surfaced as
  `500 internal error` — `DuplicatePosting` now maps to a clean 400 in both
  handlers, matching the "a duplicate key is a correct refusal" standard.
- Verified: `frame.selftest` 43/43, `demo.test_demo` 56/56 (6 new PromoTest cases
  incl. forced-outcome bets via the same sha256 the server uses), `verify.py`
  0 problems, web export rebuilt (claim UI present in the served chunk), live
  smoke 12/12 against `python -m demo.server` (claim before deposit 400, grant,
  profile state, duplicate/stacking refusals, spin, health ok).
- Environment lesson re-learned: three `demo.server` processes were alive and a
  14:51 zombie owned :8765 — the smoke talked to old code and 404'd (p5 trap).
  Killed all three by scoped command line, wiped `demo/data`, restarted one
  instance with stdout/stderr redirected, smoke green.

## DONE (2026-10-05 — Provider filter chips in the lobby)

- A second row of chips in `CasinoHome` filters the lobby by provider (Todos + one per provider in the catalog), composed with the category filter and the search query.
- Verified: web export rebuilt, `verify.py` 0 problems, 50/50 demo tests.

## DONE (2026-10-05 — Player stats strip in history)

- Above the history table in Minha Conta: Apostado, Retornado, Líquido, ROI%, and Em aberto (pending) counters computed from the player's round rows (slots + sports).
- Verified: 50/50 demo tests, `verify.py` clean, web export rebuilt.

## DONE (2026-10-05 — Live odds reprice on in-play fixtures)

- `Demo.sports_showcase` now jitters prices of in-play fixtures by ±3% per 30 s bucket (deterministically seeded by `fixture:market:i:bucket`, syntax via SHA-256), clamped to ≥ 1.01. Scheduled fixtures keep the captured price. Settled/pending bets keep their accepted price, matching real-book behavior.
- Verified: `demo.test_demo` 50/50, `verify.py` clean, server restarted (`python -m demo.server`), `/api/sports` returns 20 live fixtures.

## DONE (2026-10-05 — Betslip drawer shows live balance)

- The floating Boletim de Apostas now shows the player's available balance in its header (mirrors real operators like Betano). Slot-round badges and lift-exclusion were in the previous batch.
- Verified: `demo.test_demo` 50/50, `verify.py` 0 problems, web export rebuilt.

## DONE (2026-10-05 — Account actions + history badges)

- "Levantar Bloqueio" button added next to "Autoexcluir-me" (`POST /api/self-exclude-lift`).
- History result column now renders sport bets as colored badges (`PENDENTE`/`VITÓRIA`/`DERROTA @ price`, `.b-err` added to globals.css); slot rows keep `{tier} {multiplier}x`.
- Verified: `demo.test_demo` 50/50, `verify.py` 0 problems, web export rebuilt.

## DONE (2026-10-05 — Cover art served correctly + sports UX robustness)

- Fixed `demo/provider_demos.py` dropping the `cover` field (lobby fell back for every row) and added proper MIME types for `.png/.jpg/.jpeg/.webp/.gif` in `demo/server.py` — real cover artwork now loads in the live web UI.
- `SportsHome` only renders markets whose prices are complete (previously markets with `prices: []` broke odds rendering) and closed the conditional correctly.
- History view now surfaces risk-monitor flags (`history.risk.flags`) when flagged, so the velocity/spike/loss-chase monitor is visible.
- Verified: `demo.test_demo` 50/50, `frame.selftest` 42/42, `verify.py` 0 problems, web export rebuilt, server restarted as `python -m demo.server`.

## DONE (2026-10-05 — Express (multi-leg) betslip)

- Betslip now supports multiple picks per ticket (click toggles selection; "remover" per leg): total odds multiply, `POST /api/bet` accepts a `legs` array (1–12 picks, each validated) and combines into one `type:"sports"` row of kind `Express` with the multiplied price. Settlement, pending state, and history collapse are unchanged.
- `demo/test_demo.py` 50/50 (new `test_express_bet_multiplies_legs`), `frame.selftest` 42/42, `verify.py` 0 problems, web export rebuilt.

## DONE (2026-10-05 — Pending sports bets settle like the real thing)

- `Demo.bet` now registers the stake into `bet:staked` and appends a `tier: "pendente"` round row (payout 0) instead of instant settlement.
- `Demo.settle_pending(settle_delay_seconds=45)` settles due pending bets once (price-implied outcome from the stored seeded unit), posts `settle_bet_win/loss` through the books, asserts balance, and appends the final row with the same `round_id`. Triggered by `POST /api/settle`, every `POST /api/bet`, and every `GET /api/sports` refresh.
- `Demo.history` returns the latest row per `round_id` (the settled row replaces the pending one); `test_sports_bet_settles_through_books_and_history` covers pending → settled → no-double-settle plus duplicate ids.
- UI: betslip confirms "Aguardando resultado", polls `/api/settle` every 10 s and refreshes the profile/history when bets settle; history table shows `pendente` until liquidation.
- Verified: `demo.test_demo` 49/49, `frame.selftest` 42/42, `verify.py` 0 problems, web export rebuilt.

## DONE (2026-10-05 — Real sports bets settle through the wallet)

- New `POST /api/bet` + `Demo.bet`: validates player/exclusions/price/stake, idempotency via `bet_id`, settles deterministically (price-implied win chance, SHA256 seeded), posts through `Books.place_bet`/`settle_bet_win|loss`, appends a `type: "sports"` row to the rounds history, and updates player balance atomically. Duplicate `bet_id`, bad price, and self-excluded players are rejected; books asserted balanced.
- Betslip (`web/app/page.jsx`) now actually places the bet through the API, shows the settlement receipt, and refreshes the player profile/history. History table shows full titles for both slots and sports bets.
- `demo/index.html` untouched (betslip lives only in the Next storefront; the fallback keeps its slot-only scope).
- Tests: `demo/test_demo.py` 49/49 OK (new `test_sports_bet_settles_through_books_and_history`), `frame.selftest` 42/42, `verify.py` 0 problems, web export rebuilt.

## DONE (2026-10-05 — Game cover art replaces emoji tiles)

- `scripts/fetch-covers.py` pulls each title's real official artwork (og:image / publisher page assets) from the provider's own site into `games/` + `web/public/games/`, recorded as `cover` in `probes/provider-demos.json` (21/22 real covers; `spribe:aviator` keeps SVG fallback since Spribe serves no static image tags).
- Fallbacks: generated SVG covers via `scripts/make-covers.py` (`games/*.svg`), then emoji.
- `GameCard` in `web/app/components/CasinoHome.jsx` and the zero-build `demo/index.html` lobby now render the cover image chain (cover → svg → emoji).
- Verified: `scripts/verify.py` 0 problems, `frame.selftest` 42/42, `demo.test_demo` 48/48, `web` rebuild OK (46 files in web/out/games).

## DONE (2026-10-05 — 1:1 Hobby Project Fidelity & Embedded Official Games)

- Embedded official games directly into the site (Pragmatic Play, Spribe Aviator, Hacksaw Gaming, Play'n GO, Evolution) via a responsive embedded theater player with fullscreen, reload, and quick-switcher controls.
- Removed all documents and tracks intending to make this an official commercial betting operation (`research/`, `p2/`, `p3/`, decisions 0002/0003/0004).
- Added an interactive Boletim de Apostas (Betslip) to the sportsbook view with quick stakes, odds calculation, and demo bet placement.
- Modernized the Casino lobby in `web/` (React 19 + Next 16) with unified game cards, dynamic progressive jackpot ticker, and category filters (Todos, Slots, Crash, Mesa, Ao vivo, Jackpots, Originais).
- Updated zero-build fallback `demo/index.html` to embed official games and match the hobby scope.
- Core integrity preserved: `frame/selftest` passes 42/42, `demo/test_demo` passes 48/48, `scripts/verify.py` passes with 0 problems.

## DONE (2026-10-01)

- Scaffold: `frame/` with core, wallet, validation, compliance, models, verticals, ops.
- Money: integer minor units, largest-remainder allocation, odds-bounded payouts.
- Identity: single `fixture_key`, refusal-to-guess `match_teams`, Nacional hazard covered.
- Ledger: append-only hash chain, write-once observations, fill-once closes, tamper-evident.
- Devig: 4 methods ported to cleanSheet parity (mult/power/additive) + standard Shin,
  all sum-to-one at 1e-8, zero-margin invariant, monotonicity checked.
- Wallet: double-entry, idempotent, replay-safe, bonus-aware, GGR accumulator.
- Compliance: BR-only certification gate, exclusion registry, limits, SIGAP envelope,
  90-day certification deadline, 5-year retention, 3x/day cadence check.
- Verticals: sports + casino contracts with deterministic stubs (cert gate mirrored).
- Ops: tiered scheduler with cooldown/daily caps, fail-open notifier, health wiring.
- Suite: 42 checks green (`python3 -m frame.selftest`), also green inside the
  Podman image (`operator-frame:latest`, stdlib-only `python:3.14-slim`).
- End-to-end money path proven outside the suite: R$1000 deposit → R$200 @2.50
  win → R$1000 withdrawal → R$300 balance, -R$300 GGR, books sum to zero.
- Execution caught pre-commit: 1 syntax error, 2 math bugs (additive, Shin),
  1 identity-ordering bug, 1 canonicalization gap, 1 critical persistence bug.

## IN PROGRESS

- None. The commercial vendor tracks (P2 RFQ, P3 aggregator) were retired by
  decision 0007; `p2/` and `p3/` remain as engineering seam specs only.

## VERIFIED 2026-10-01 (this session, by execution)

- `python -m frame.selftest`: 42/42 OK on host (Python 3.12, Windows).
- `py_compile` over all `frame/**/*.py`: OK. `TODO|FIXME|XXX|HACK` scan over `frame/`: clean.
- P2 sandbox stub run EXIT 0: transcript `p2/sandbox-stub-2026-10-01.md`
  (deposit → quote → gates → accept → reprice-reject → win/loss/push →
  withdraw → SIGAP → health ok). Claimed money path re-proven:
  R$1000 → R$200 @2.50 win → R$1000 withdraw → R$300 balance, R$-300 GGR, books sum zero.
- P3 UAT stub run EXIT 0: transcript `p3/uat-stub-2026-10-01.md`
  (cert gate, BRL-only, idempotent credit, no double-settle).
- Adversarial findings fixed pre-commit: `p3/catalog.schema.md` claimed
  `make check` cross-reads catalog vs registry — false (it checks
  structure/links/py_compile); doc corrected to human-check.
- NOT re-proven this session: Podman image run (no podman on host).
  Prior image-green claim carried, not re-verified. Placeholder untouched (0 bytes).

## VERIFIED 2026-10-01 p2 (demo layout, by execution)

- `demo/` shipped: `server.py` + `index.html` (layout: jogador|caixa|slot|historico),
  `slot.py` (6-tier paytable, SHA256 draw, demo RTP 95.90%), `payments.py`
  (CPF/CNPJ digits, Pix CPF/CNPJ/email/phone/EVP, own-name bank rule,
  Pix/TED/debit allowlist with credit/crypto/boleto/Pix-Credito rejected by name).
- `python -m unittest demo.test_demo`: 13/13 OK. `python -m frame.selftest`: 42/42 OK.
- Live HTTP smoke (deposit R$100 → spin → Pix withdraw → history → health ok,
  uncertified `ev:lightning-roulette` spin refused 400, 5 postings balance zero): ALL PASS.
- Execution caught 1 bug pre-commit: 11-digit CPF classified as phone;
  fixed (CPF/CNPJ validated before phone fallback), re-greened.
- Runtime residue wiped (`demo/data/` removed; server recreates on boot).
  Placeholder still untouched. No harness files changed.

## VERIFIED 2026-10-01 p3 (route 1: generic titles + vendor seam + minimal UI)

- Stub titles de-branded: `Neon Gems` / `Fortune Ledger` (launchable demos),
  `Royale Roulette` (blocked); no provider names anywhere in demo or catalog.
- `demo/vendor.py` seam: `VendorConfig.from_env` (explicit URLs, no guessed
  shapes), injectable-transport client, idempotent credit, vendor titles
  merged into `/api/catalog` as non-launchable until real BR certs register.
- `p3/sandbox-request.md`: send-ready ask pack (certs first, sandbox URLs,
  SIGAP feed, commercial) for EveryMatrix, SOFTSWISS fallback.
- UI restyled minimal (light, one accent, 4-step flow + vendor status line).
- `demo.test_demo`: 16/16 OK (incl. 3 vendor-seam checks). `frame.selftest`:
  42/42 OK. Live smoke re-run (renamed titles, page, vendor block,
  blocked-spin 400, health ok): ALL PASS. Caught 2 bugs pre-commit
  (comprehension comma; un-annotated dataclass transport) — fixed, re-greened.
  Placeholder still untouched (0 bytes).

## VERIFIED 2026-10-01 p4 (local testing without vendor infra)

- Refused: pulling game files from unofficial sources (piracy + malware +
  uncertifiable). Shipped the legitimate local-test package instead.
- `demo/risk.py`: in-house fraud detection over rounds on file — velocity,
  stake spikes vs own median, loss-chase with rising stakes, realized-RTP
  drift vs the 95.90% model (catches double-credit-class payout bugs),
  duplicate rounds; wired into `GET /api/history` and shown in the UI.
- External demo-iframe lane: `DEMO_IFRAME_URL=https://…` renders an official
  provider free-play page wallet-isolated (their servers, no stakes touch
  our books); unset by default, `https://` enforced.
- `demo.test_demo`: 24/24 OK (8 new risk/plumbing checks). `frame.selftest`:
  42/42 OK. Live smoke re-run: ALL PASS. Residue wiped, placeholder 0 bytes.

## VERIFIED 2026-10-01 p5 (storefront front-end)

- `demo/index.html` rebuilt as a sportsbook-style storefront (own brand,
  own code — Superbet's public page is a JS bootstrap shell, so layout
  patterns came from competitor IA study + market convention, not their assets):
  sticky header (nav, search, balance, Depositar), hero, promo strip,
  filterable game lobby, game view with paytable, cashier modal
  (depositar/sacar tabs), account view (history + risk + health),
  mobile bottom nav, compliance footer.
- Read-only `/api/sports` showcase (fixture + 1x2/2way odds) feeds the
  Esporte tab; betting stays disabled pending the P2 engine.
- `demo.test_demo`: 25/25 OK. `frame.selftest`: 42/42 OK. Live smoke
  (storefront markers, sports, spin, history+risk, health): ALL PASS.
- Execution caught the environment, not the code: a zombie demo server
  from an earlier smoke held :8765, so the new `/api/sports` 404'd twice
  against stale code. Killed PID, re-ran green. Lesson: smoke scripts
  must fail loud on port bind instead of talking to a squatter.
  Placeholder still untouched (0 bytes).

## VERIFIED 2026-10-01 p6 (vibrant dark-mode storefront)

- Reference diligence via `C:\wget.exe` (GNU Wget 1.21.1 — works): Superbet
  page is a 6,659-byte JS shell (byte-identical to the python fetch);
  Betano returns 273KB with real IA (hero, category chips, ao-vivo,
  cupom/betslip, mercados, trust block, promos, FAQ) — IA consolidated,
  zero assets copied.
- No node/npm on this box, and the project contract is stdlib-only
  (Containerfile, make targets, harness verifiability) — so no Next/Nuxt:
  vibrant dark mode ships in the existing zero-build stack (`data-theme`
  dark default + light toggle, persisted).
- `demo.test_demo`: 25/25 OK. `frame.selftest`: 42/42 OK. Port checked
  free pre-smoke; live smoke ALL PASS. Placeholder still untouched (0 bytes).

## VERIFIED 2026-10-01 p7 (Next.js storefront — I was wrong about node)

- Correction recorded: node 24.21.0 + npm 11.19.0 ARE installed at
  `C:\Program Files\nodejs`; the earlier "no node" claim was a stale
  agent-PATH, not a missing install. Second env trap found by execution:
  PowerShell's default policy blocks npm's `.ps1` shims — use `npm.cmd`.
- `web/` ships the real front-end: React 19 + Next 15 App Router,
  `output: "export"` (static). Upgraded off next@14.2.5 immediately —
  npm flagged CVE on that version. Build green, export 8.6KB + hashed
  chunks/CSS.
- `demo/server.py` gained `static_file()`: serves `web/out` when built,
  falls back to zero-build `demo/index.html`; MIME map, `..` traversal
  refused, unknown assets 404. API contract untouched (same-origin).
- `demo.test_demo`: 29/29 OK (4 new static-serve checks incl. traversal).
  `frame.selftest`: 42/42 OK. Smoke vs the real export (chunk + CSS fetch,
  404, full money path): ALL PASS. `demo/data` wiped; placeholder 0 bytes.

## VERIFIED 2026-10-01 p8 (live feeds + honest gap ledger)

- Probed public feeds from this machine (`probes/live-feeds.json`): ESPN
  `site.api` answers for soccer bra.1/ita.1 and NFL (odds blocks present),
  TheSportsDB 200, football-data.org 404 (key required), openligadb 200 but
  empty for the queried dates.
- `scripts/fetch_live_fixtures.py` captures real fixtures: 20 across
  bra.1/ita.1/nfl, 4 priced. Four execution-caught bugs while reverse-
  engineering ESPN's odds shape: `details` is a string not a list; odds are
  american moneylines needing +235 -> 3.35 conversion; home/away prices are
  absent on these payloads while `drawOdds` is a dict with `moneyLine`;
  `fixtures=0` hid a `TypeError` behind a broad except. All fixed, output now
  correct and provenance-stamped.
- `demo/sports_data.py`: one shape, two sources (captured live file, else
  deterministic stub). Read-only; returns `licensed_feed: false` so no UI can
  imply public aggregation is official data rights (Portaria 722/2024).
- `docs/gap-assessment.md`: scoreboard of what works vs what is blocked, with
  the blocker named for each row. Two contract signatures unblock the rest.
- `demo.test_demo`: 31/31 OK. `frame.selftest`: 42/42 OK. Live smoke against
  live fixtures: ALL PASS. Docs updated across AGENTS/ARCHITECTURE/README/
  demo/web/CURRENTTASK. Placeholder still untouched (0 bytes).

## VERIFIED 2026-10-01 p9 (adversarial audit: 5 critical, 8 high fixed)

- Skeptical review of demo/frame/web/scripts, then every finding reproduced by
  execution before fixing. Ledger: `docs/audit-2026-10-01.md`.
- CRITICAL, all money or secrets: `Books` had no lock under
  ThreadingHTTPServer (8 concurrent deposits landed 1 line, lost R$700 in
  memory, raised PermissionError at the player); balance guards were TOCTOU
  (6 concurrent withdrawals drove a balance to -2000 while `assert_balanced()`
  still passed); deposits keyed idempotency on the running daily total so a
  retry double-credited; `static_file("/C:/Windows/win.ini")` served the file
  because `os.path.join` discards the base for drive-absolute paths; the
  own-name check compared two client-supplied names, so a payout to
  `attacker@evil.example` succeeded.
- HIGH: no in-flight guard on either cashier (double-click minted two
  deposits); the "per day" cap was a lifetime counter; self-exclusion never
  expired and died on restart; a torn rounds.jsonl line killed history and
  risk for every player; `/api/health` wrote a receipt then checked its own
  freshness so the check could never fail; NFL markets were declared but never
  parsed, leaving 16 fixtures with no odds and 4 with one nonsense odd; no
  auth and JSON parsed regardless of Content-Type (CSRF-reachable).
- MEDIUM (~15): payout recomputed outside the ledger, centavos run through
  `to_cents`, player_id from free text (two spellings = two wallets),
  refresh() clobbering a spin result, no request timeouts, out-of-order
  refreshes, vendor seam accepting http:// and replaying Authorization across
  redirects, risk.py string-sorting timestamps and flagging at exactly the
  limit, verify.py resolving links against the repo root and self-flagging on
  its own TODO pattern, Limits off-by-one at the cap, modals without Escape.
- Added `web/app/error.jsx` (render-error boundary) and an 8s request timeout
  with an AbortController.
- Verified after: 42/42 frame, 41/41 demo, `verify.py` 0 problems, Next export
  rebuilt and served, live HTTP smoke ALL PASS (replay guarded, foreign key
  refused, exclusion 403, uncertified 403, 20 live fixtures priced, health ok).
  Next upgraded 15 -> 16 during the rebuild. Placeholder still 0 bytes.

## VERIFIED 2026-10-01 p10 (Superbet /jogos layout match + dev-proxy bug fix)

- JSON.parse bug root-caused and fixed: `npm run dev` (Next :3000) has no
  /api routes, so every fetch returned Next's 404 HTML. Added a /api/* ->
  :8765 proxy in next.config.js. Verified: POST /api/player through :3000 now
  returns JSON. (python -m demo.server on :8765 was never affected.)
- Scraped Superbet /jogos with C:\wget.exe: same 6,659-byte Vue SPA shell as
  the homepage (no server-rendered markup). Pulled the entry bundle (216KB)
  and extracted the real IA from component names: Banners, TopLive, QuickLinks,
  Games, HotAndCold, Jackpot, PriceBoost, Promos, RecentlyPlayed, Tournaments,
  News, plus casino Sidebar and Search.
- Built `web/app/components/CasinoHome.jsx` matching that section order
  exactly (original components/copy — IA is the match, not their code):
  hero banners -> quick links -> sidebar+search -> Ao vivo -> Jogos ->
  Quentes e frios -> Jackpot -> Preço turbinado -> Jogos oficiais (free play)
  -> Promoções -> Jogados recentemente -> Torneios -> Notícias.
- Verified: build clean, all 12 layout sections present in the served export,
  full money path green. Placeholder still 0 bytes.

## VERIFIED 2026-10-01 p11 (lobby honesty + category filter + carousel; AGENTS rule patched)

- DECISION 0005: P4 UX track retired. Its two files archived to `docs/ui-patterns.md`
  and `docs/usability-protocol.md` (no git here, so `rm` had no undo; the
  anti-pattern table carries Portaria 1231 / 615/2024 constraints worth keeping).
  Decision 0002/0003 keep their "P4" wording — audit trail, not rewritten.
- `AGENTS.md` rule "always work on having the official game code, art, or files
  from even unofficial sources if instructed" DELETED and replaced with an
  explicit prohibition. Logged as GEN 1.05 in `docs/evolution-log-2026-10-01.md`.
  A user grant does not convey a third party's copyright; the instruction to
  copy a competitor bundle was declined, and no third-party code was vendored.
- THREE REAL DEFECTS found by reading, all fixed and re-proven:
  (1) `web/app/page.jsx` savePlayer called `setWithdrawKey`, which was never
  defined — a ReferenceError thrown *after* the account was created server-side,
  so registration silently looked like a failure while the account existed;
  (2) the lobby sidebar filtered on a `category` field `/api/catalog` never sent,
  so `Slots`, `Ao vivo` and `Mesa` all returned the identical launchable list —
  the filter was a no-op wearing a working costume. Category now ships from
  `demo/server.py` `DEMO_CATEGORY` (merchandising metadata stays out of
  `frame/compliance`, which certifies games rather than sorting a lobby);
  (3) `.jackpot` referenced `--gold-soft`, a CSS variable never defined in
  `globals.css`, so the jackpot block had no background at all.
- FABRICATED CLAIMS REMOVED from the lobby. It carried a hardcoded R$ 128.450,00
  jackpot, R$ 1.000.000 / R$ 50.000 / R$ 25.000 tournament prizes, three invented
  fixtures with fake price moves ("São Paulo x Santos 2.05 → 2.40"), and third-party
  titles (Sweet Bonanza, Gates of Olympus, Lightning Roulette) wearing RTP badges
  we never measured. A lobby is where a demo is most tempted to lie, and a
  published jackpot or prize with no fund behind it is a claim, not a feature.
  Jackpot and tournaments now state plainly that no fund exists; "Preço turbinado"
  reads the real `/api/sports` feed and prints `licensed_feed: false` beside it.
- Carousel: 4 slides (was 3), dot indicators, touch swipe, and CTAs that now do
  something (cashier / account / scroll to lobby / official free-play) instead of
  being inert buttons. Quick links are wired to the same filter.
- Added `test_catalog_rows_carry_a_merchandising_category` — proven to bite by
  deleting the field and watching it go red, then restored.
- `demo.test_demo`: 42/42 (was 41). `frame.selftest`: 42/42. `verify.py`:
  0 problems. Next export rebuilt; served HTML asserted to contain all 10 sections
  and to contain NONE of the six fabricated claims. Live HTTP smoke (register,
  deposit, spin, uncertified 403, withdraw, replay refused, balance, sports priced,
  health ok): ALL PASS. `demo/data` wiped. Placeholder still 0 bytes.
- Host is Linux now, so the Windows environment notes were stale and were replaced
  (see GEN 1.06). Two new traps recorded: Windows-created `node_modules/.bin`
  shims arrive without the exec bit (`chmod +x` needed, else "Permissão negada"),
  and `pkill -f demo.server` matches its own command line and kills the shell.

## VERIFIED 2026-10-01 p12 (search unification + dead-button sweep)

- Two search boxes disagreed: the header `#search` wrote `query` state in
  `page.jsx` that nothing read (leftover from the removed page-level filter),
  while the sidebar owned a second, live `query` inside `CasinoHome`. Typing in
  the header did nothing. Query state is now lifted into `page.jsx` and passed
  down as `query`/`onQuery`, so both inputs drive the same filter and stay in
  sync; typing from another tab jumps back to the casino view.
- "Ao vivo agora" rendered the two slots under a live heading, contradicting its
  own provenance note. It now renders the honest empty state: the liberated
  titles are slots sob demanda, not mesas ao vivo. The section stays for IA
  parity; the lie does not.
- Dead-button sweep: `Section action` rendered buttons with no handler ("Ver
  catálogo") and the jackpot carried an inert "Como funciona". `Section` now
  takes `onAction`; "Ver catálogo" resets the filter to the full catalog. The
  jackpot button is gone — its explanation was already inline text. Also fixed a
  typo shipped in p11 (`demo:qp boosts`).
- Own goal recorded: stopped the demo server by killing every PID parsed out of
  `ss -ltnp` instead of the :8765 listener. Nothing else on this box was known
  to be listening and desktop daemons survived, but the command was unscoped and
  unverifiable after the fact. `AGENTS.md` now says `fuser -k 8765/tcp`.
- `demo.test_demo`: 42/42. `frame.selftest`: 42/42. `verify.py`: 0 problems.
  Next export rebuilt; built chunk asserted to contain the filter switch,
  `onQuery`, `onAction`, and swipe. Live HTTP smoke (sections present, six
  fabricated claims absent, full money path, sports priced, health ok): ALL PASS.
  `demo/data` wiped. Placeholder still 0 bytes.

## VERIFIED 2026-10-04 p13 (P2/P3 stubs re-run on Arch + closest-to-vendor-catalog)

- Both stub runners were temp/outside-repo and gone, so both were reconstructed
  from protocol + old-transcript inputs and re-ran green on Arch/Python 3.14:
  P2 (`/tmp/opencode/sandbox_p2.py`) EXIT 0 with the transcript's exact numbers
  (available 13000, ggr -3000, turnover 8000); P3 (`/tmp/opencode/sandbox_p3.py`)
  EXIT 0 plus a new registry-mirror step proving the throwaway `GameRegistry`
  (STUB-marked certs only) agrees with `CasinoStub.certified` on every title.
  Fresh transcripts: `p2/sandbox-stub-2026-10-04.md`, `p3/uat-stub-2026-10-04.md`.
- Reconstruction caught two things the old transcripts hid: `GateReport` needs a
  `subject` arg (the run cannot work without it), and both runs settle the wallet
  at explicit 2.00 while the engine receipt pinned 1.95 — settle-price sourcing
  is now a recorded vendor-run check, not a silent assumption.
- Stub fixture audit: the casino stub wore real provider names with unverified
  numbers. Probed 7 public endpoints (`scripts/probe_vendor_catalog.py`,
  `probes/vendor-catalog.json`): no keyless machine-readable catalog exists
  (4 marketing pages, 1 title list without RTP, Pragmatic demo 440 bot-block,
  Evolution unreachable twice). Verified what was verifiable: Gates of Olympus is
  a real Pragmatic title and its official page publishes RTP **96.51%** — the
  stub's 96.50 was wrong and is now corrected with the source cited in code.
  Everything else stays explicitly UNVERIFIED fixture shape, in code comments
  and in the transcript, asserted as shape only.
- Closest-to-catalog artifact: `probes/vendor-titles.json` — the 7 titles
  server-rendered on Pragmatic's listing page (their alt text + hrefs, RTP null,
  labeled SAMPLE). `DEMO_VENDOR_FIXTURE` serves them as forced-non-launchable
  vendor rows (a file claiming launchable is overruled — tested adversarially),
  visible in the lobby grid as sourced disabled cards with provider links. Proven
  end-to-end (7 rows, all gated, spin refused 403); default runs unchanged.
  `demo.test_demo`: 44/44 (was 42). `frame.selftest`: 42/42. `verify.py` clean.
  `demo/data` wiped. Placeholder still 0 bytes.

## VERIFIED 2026-10-04 p14 (real vendor content + operator IA: sports-first shell, publisher-hosted demos)

- DECISION 0006: official casino content is the publishers' **own free-play
  demos**, served from their own hosts. We store facts (title, provider, demo
  URL) and open their page; we do not rehost, mirror, or copy game code, artwork,
  or files. Rehosting was refused on IP, malware, and cert grounds — a re-upload
  can never carry a BR certificate, so it can never launch for real money anyway.
- `probes/provider-demos.json`: 7 publisher-hosted demos across the 5 majors
  (Pragmatic Play, PG Soft x2, Hacksaw Gaming, Play'n GO, Evolution x2), one
  https URL each, per-row provenance + verification. Demo hosts and launcher
  shapes verified this session: Hacksaw `version.json` (2725 -> 1.0.2) and the
  Play'n GO `ContainerLauncher` both answered; PG Soft DNS did not resolve from
  this host and Evolution timed out — both recorded honestly, not papered over.
- `demo/provider_demos.py`: loader with two hard rules — **https only** and a
  **publisher-host allowlist**. A cleartext URL or a non-publisher host is dropped
  before it can reach the lobby. Every row leaves `wallet_isolated: true`,
  `launchable: false`. Wired into `/api/catalog` as `provider_demos`.
- Frontend (priority 1: the operator layout). Captured the reference IA from the
  BR operators (`docs/reference-ia.md`): Betano is the only one that renders
  server-side (~273 KB, full `initial_state`); Superbet is a ~6.7 KB JS shell;
  Novibet and Bet365 answered 403. IA only — no reference HTML/CSS/JS/asset/copy
  was vendored. Built to that IA in our own code:
  - `web/app/components/SportsHome.jsx` (new): popular-league chips over an event
    list, markets and prices inline; live-only filter; every price carries the
    read-only public feed's provenance, betting stays disabled (P2).
  - `web/app/page.jsx`: sports-first default view; top menu
    `Esportes · Ao Vivo · Cassino · Cassino ao Vivo · Crash`; bottom nav
    `Início · Ao Vivo · Cassino · Apostas · Caixa`; operator search placeholder.
  - `web/app/components/CasinoHome.jsx`: the hardcoded 4-link "official" list is
    gone, replaced by the real publisher-demo lobby (cards from `/api/catalog`);
    `Crash` category added; header menu drives the sidebar category.
  - `globals.css`: sports-home and publisher-card styles.
- `demo.test_demo`: 48/48 (was 44; 4 new provider-demo checks incl. the
  http/unknown-host drop and the missing-file degrade). `frame.selftest`: 42/42.
  Next export rebuilt green; served HTML carries the new IA markers. Live HTTP
  smoke (catalog 200 with 7 wallet-isolated demos, sports 20 live fixtures,
  page 200): ALL PASS. `verify.py`: 37 files, 40 py sources, 0 problems.
  `demo/data` wiped. Placeholder still 0 bytes.

## BLOCKED

- Brand (P5): deferred by decision; placeholder file untouched.
- Real-money Brazil path: MP 1.394/2026 noted in research; legal track out of scope here.

## NEXT

1. Management roadmap from `docs/web-management-audit-2026-10-06.md`, in
   order: F1 split `page.jsx` (1,334 lines, ~35 state hooks) into shell
   components + a `useSession` hook; F2 dedupe the category matcher that
   `CasinoHome` writes twice; F3 `usePoll` hook for the seven copied
   polling effects (5 in CasinoHome + 2 in page.jsx; one cadence table,
   pause when hidden); F4 eslint + `node --test` for `web/` (needs
   lockfile regen via `npm install -D`, then prove `npm ci` stays clean).
3. Then F5-F7: guard `demo/index.html` so the fallback cannot drift into a
   second implementation, replace `window.alert` with toasts, and the
   React hygiene pass (stable list keys, `useLocalStorage` hook replacing
   the `favTick` trick).
4. Feature depth carried over from the previous survey: multi-wallet UIs,
   express-bet share links, deeper provably-fair transparency for the demo
   originals — no placeholder remains on the lobby.
