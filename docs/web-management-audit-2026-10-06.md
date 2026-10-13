# Web app management audit — 2026-10-06

Scope: **management** of the storefront — how `web/` is built, verified, kept
honest, and kept maintainable. This continues the 2026-10-06 recon thread
(`recon-reachable-sites-2026-10-06.md`): the FanDuel mapping was already
concluded as aligned, so the next question was the health of our own
management surface, not more competitor capture.

Three of the findings are fixed in this pass (with the `npm ci` alignment
folded into the README fix); the rest are an ordered roadmap. Evidence is line-level where it was read, and this session's
verification limits are stated at the bottom — no execution shell was
available, so nothing here claims a green run it did not perform.

## Fixed this pass

### 1. `scripts/verify.py` was blind to the web app

The QC scoreboard required exactly four web paths (`page.jsx`, `layout.jsx`,
`globals.css`, `lib/api.js`). Deleting `web/app/components/CasinoHome.jsx`,
`web/next.config.js`, or `web/package.json` would still print
`check: OK`. There was also no check that the artifact the server actually
serves — `web/out/index.html` — exists, is complete, or came from the
current sources. The stale-export case is the worst one: `demo/server.py`
serves `web/out`, a stale export silently serves yesterday's lobby, and
every past session asserted freshness by hand (`"served chunk contains …"`).

Now `verify.py` additionally:

- requires `web/app/error.jsx`, `web/app/components/CasinoHome.jsx`,
  `web/app/components/SportsHome.jsx`, `web/next.config.js`,
  `web/package.json` (9 web files total required);
- fails if `web/out/index.html` is missing (build: `cd web && npm run build`);
- parses every `src=`/`href=` reference to `/_next/…` in the built HTML and
  fails if the referenced file is absent from `web/out` — a half-built or
  partially copied export can no longer pass;
- fails if any file under `web/app`, `web/lib`, `web/public` (or
  `next.config.js` / `package.json`) is newer than `web/out/index.html`
  (1 s tolerance) — this turns AGENTS workflow step 5 ("rebuild the
  frontend whenever modifying `web/app`") from a prose rule into an
  executable one;
- scans web sources for `TODO|FIXME|XXX|HACK` with the same
  "finish the code, do not annotate it" rule Python sources already follow
  (`.js`/`.jsx`/`.css` under `web/`, `node_modules`/`.next`/`out` skipped;
  `.svg` artwork excluded — `hs-rip-city-dice.svg` legitimately contains
  "HACKSAW GAMING").

The bash mirror `scripts/verify.sh` (`make check`) gained the same required
web-file list including `web/out/index.html`, and `verify.py`'s docstring
now says "superset" instead of "mirror" — the two were already diverging
demo-vs-frame before this pass, and only `verify.py` carries the export
integrity/freshness/markers checks.

Static validation of the new checks against the current tree: the built
[web/out/index.html](../web/out/index.html) references 9 distinct `/_next`
assets (1 CSS + 8 JS chunks) and all 9 exist under
`web/out/_next/static/` (12 files incl. manifests); `web/app`, `web/lib`
and `web/next.config.js`/`web/package.json` carry no fragment markers;
`web/README.md` is not counted as a source, so documenting the app does not
trigger the freshness check.

### 2. `Makefile` had no target for the demo suite

AGENTS workflow step 4 runs `python -m unittest demo.test_demo` (66
checks), but `make` only exposed `selftest` (frame). Added `demo-test` and
listed it in `.PHONY`, so the two suites are one keystroke each.

### 3. `web/README.md` had drifted from the app it documents

- Claimed "Next 15 App Router"; `web/package.json` pins `next ^16.3.8`
  (upgraded in the p9 audit).
- Claimed the providers "refuse to be framed, so the section **links out**"
  to four provider pages. Reality since decision 0006 + the theater
  rewrite: titles are **embedded** via `demo_url` iframes in a
  fullscreen-capable theater; framing refusals are handled by the
  "↗ Nova Aba" escape hatch. Rewritten to match, including the
  `wallet_isolated: true` / `launchable: false` guarantees.
- The `CasinoHome` section list described sections that no longer exist in
  the component ("Ao vivo", "Preço turbinado", "Jogos oficiais" block,
  standalone "Promoções"/"Jogados recentemente" rows — those migrated to
  the promos view, the provider-demo grid, and the Recentes/Favoritos tabs).
  Rewritten to the real order: hero → chips → sidebar → Destaques → Todos
  os Jogos → Quentes e frios → Jackpot → Super Odds → Torneios → Notícias.
- Added a "Quality control" section documenting the new `verify.py` web
  checks and the no-JS-test-runner limitation.
- Build/run now says `npm ci` (reproducible, lockfile-backed) with
  `npm install` reserved for dependency changes — matching the AGENTS
  node_modules prune/restore loop. This was roadmap item F8; done here.

## Findings not fixed here (roadmap, in priority order)

### F1 — `page.jsx` is a 1,334-line god component

One `Page()` owns ~35 `useState` hooks, the topbar/header/nav, five views
(casino, sport, promos, account + the slot game view), four modals
(cashier, account, game detail, official-game theater), the betslip tray,
the chat widget, the footer, and every action handler (deposit, withdraw,
spin, bet, claim, chat, favorites, recents). Every new feature since p5
has added state at the top of this file; the render tree alone is ~900
lines.

Proposal: split into `web/app/components/` shell pieces — `Header`,
`BottomNav`, `CashierModal`, `AccountModal`, `DetailModal`,
`GameTheater`, `Betslip`, `ChatWidget` — with props passed from a slim
`page.jsx`, and shared state (player/profile/history/busy) lifted into a
`useSession` hook in `web/lib/`. Expected result: `page.jsx` under ~250
lines, each modal independently readable and testable.

### F2 — duplicated category logic inside `CasinoHome.jsx`

The category switch is implemented twice: once in `matches()` (drives the
grid) and again inline in the sidebar count badge. "Jackpots", for
example, is spelled as `category === "Slots" || olympus || bonanza || wolf`
in both places. Adding or correcting a category means two edits that can
drift apart — the exact class of bug that shipped in p11 (the sidebar
filtered on a field the API never sent).

Proposal: one exported `matchesCategory(game, category, { recent, favs })`
used by the grid, the sidebar counts, and any future rail.

### F3 — polling is copy-pasted seven times

`CasinoHome` has five near-identical `useEffect` + `setInterval` +
`api().then(set…)` polls (jackpot 15 s, sports 15 s, trending 60 s,
tournaments 60 s, news 60 s) and `page.jsx` has two more (settle 10 s,
sports 15 s) — seven in total, plus a standalone banner timer. Each copy
re-implements mount/unmount cleanup and swallows errors the same way.

Proposal: `usePoll(path, ms)` in `web/lib/` — one place for abort, pause
while `document.hidden`, and (from the recon lesson) a single cadence
table so poll intervals are declared next to each other instead of being
rediscovered per block.

### F4 — no frontend lint or tests

`npm run build` is the only thing standing between a JSX edit and the
served site; the Python suites cover the API contract but nothing covers
the UI. Proposal: add `eslint` + `eslint-config-next` as devDependencies
(lockfile must regenerate: `npm install -D …`, then prove `npm ci` stays
clean), plus a `node --test` smoke over `web/lib/api.js` (BRL formatting,
timeout error mapping, non-JSON refusal). Blocked this session — no shell
available to run npm (see limits).

### F5 — two frontends to keep in sync

`demo/index.html` (zero-build fallback) duplicates lobby behavior by hand;
`web/out` is the real site. Every new block is a chance for the fallback to
lie about what exists. Proposal: keep the fallback deliberately minimal by
policy and add a size/marker guard to `verify.py` so it cannot silently
grow into a second implementation.

### F6 — `window.alert()` is the interaction surface

Betslip confirmations, bonus claim receipts, deposit/withdraw errors, and
self-exclusion feedback all use blocking `alert()`. Real operators use
toasts, and `alert()` freezes the polling timers behind it. Proposal: a
small toast component styled from `globals.css` with an `alert()` shim in
`lib/api.js` during migration.

### F7 — small React hygiene items

- `news.items.map(… key={n.title})` — titles can collide; use index+title.
- Favorites use a `favTick` counter + `void favTick` to force re-reads of
  `localStorage`; a `useLocalStorage(key)` hook would replace both the tick
  and the three hand-rolled `try/catch JSON.parse` readers in `page.jsx`
  and `CasinoHome.jsx`.
- The betslip's "remove leg" filter logic is written twice (per-leg button
  and clear-all paths construct the same predicate differently).

## Addendum (same day): "management" clarified — admin panel + layout

The user clarified that "management of the web app" means an **admin
panel** (dashboard, top winners, percentage of returns) and that the
layout must use the full screen across device resolutions. Shipped the
same day — details in the `PROGRESS.md` entry "Full-width responsive
layout + admin panel":

- **Layout**: fluid container (1120 -> 1720px cap, `clamp()` gutters),
  230px rail, two-column casino main at >=1400px, mobile hardening at
  <=640px. Because no shell was available to rebuild, the rules were
  mirrored into the built stylesheet so the served site updates now;
  the next `npm run build` regenerates the mirror from source. F1-F7
  above remain the maintainability roadmap.
- **Admin panel**: `GET /api/admin` (`Demo.admin_dashboard()`),
  `web/app/components/AdminPanel.jsx`, header "Painel" button, and 4 new
  `AdminDashboardTest` cases. Read-only, and every figure derives from
  the round ledger / double-entry books / players file — the honesty
  rules of decisions 0012-0015 now apply to the operator view too:
  realized RTP excludes pending and sports rows, leaderboards exclude
  pending stakes, the 7-day series buckets real timestamps.
- Layout was not on the original F-list — the screenshot review caught
  the 1120px cap that the audit missed; recorded here so the scoreboard
  stays complete.
- Same-day follow-up: the painel is now **gated behind a real login** —
  `demo/auth.py` (salted SHA-256 credentials, default `admin`/`admin`,
  12h bearer sessions, admin/viewer roles), `/api/admin` answering 401
  to anonymous callers, a hidden Ctrl+Shift+A entry, and credential
  management (own-password change, create/reset/remove users) inside
  the panel itself. 6 new `AuthTest` cases cover it (unrun — no shell).

## Verification limits of this session (2026-10-06)

- **No execution shell on this host**: `run_terminal_command` fails with
  "Bash is required but was not found on this Windows system", and
  file-change hooks are unsupported in SDK mode. Therefore
  `python scripts/verify.py`, `python -m frame.selftest`,
  `python -m unittest demo.test_demo`, and `cd web && npm.cmd run build`
  were **not executed** for this pass.
- What was verified instead, statically:
  - `scripts/verify.py` was re-read in full after editing — the added
    blocks are plain `os`/`re` use with CRLF preserved and no new top-level
    names colliding with later loops;
  - every `/_next/…` reference in the current `web/out/index.html` was
    cross-checked against a directory listing of `web/out/_next/static`
    (all present);
  - the fragment-marker scan was cross-checked against the current web
    sources (clean in `.js`/`.jsx`/`.css`);
  - markdown links in this document resolve relative to `docs/` (the rule
    `verify.py` enforces).
- First command to run when a shell exists: `python scripts/verify.py`.
  If it reports `stale export`, the fix is the documented one:
  `cd web && npm.cmd run build`. Then the two suites
  (`make selftest`, `make demo-test`) before taking F1–F3.
