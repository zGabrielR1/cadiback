New card deposits use demo/embedded_card.py and web/app/components/EmbeddedCard.jsx: official secure Card Payment fields, server-owned deposit amounts, provider idempotency and independently verified wallet credit. Legacy hosted references remain readable through demo/card_checkout.py. See decision 0113 and docs/card-payments.md.

CryptAPI now handles new cryptocurrency invoices via demo/cryptapi.py; only configured receiving networks are offered. Private invoice metadata stays in crypto_charges; signed callbacks and polling independently verify provider logs before the existing idempotent wallet transaction. Legacy NOWPayments invoices retain their original provider client for settlement. Configuration and domain verification: docs/cryptapi.md; decision 0112.

# ARCHITECTURE — operator

Database crypto invoices use the `crypto_charges` IdentityDocument and join wallet confirmation transactions. `demo/publisher_state.py` persists publisher tokens, session bindings, pending stakes/wins and Pragmatic baselines/sequences under a shared wallet operation. The RGS tap settles and removes pending state in that operation. Publisher locks precede wallet locks; wallet_credit's publisher decorator stays outermost. Wallet backups include both documents and are created privately. SQL integration verification remains pending; see docs/durable-payment-and-publisher-state.md.


Daily deposit limits derive from UTC-dated deposit postings, so restarts share the journal's totals. Asaas charge stores use `demo/db_context.py` to join the wallet transaction; acknowledgements flush with the credit and expose success after commit. File-backed payment acknowledgements update memory only after their file save succeeds. Database rollback/concurrency verification for these changes remains pending (2026-11-08).


Database round methods use `demo/wallet_operation.py` to keep spins, sports placement and publisher settlements with their history and promo writes in the outer wallet transaction. Sports settlement appends its receipt under the wallet lock and rechecks settlement keys against stale snapshots. Sports completed identities include the player and round ID. Database integration verification remains pending (2026-11-08).


Database crash operations use `demo/crash_state.py` to acquire the wallet transaction before refreshing durable pending rounds. Stake/settlement postings, promotions, history and pending changes share that transaction. New workers preserve active rounds; the sweep settles expired rounds from their original clock/draw. File-backed mode keeps its legacy refund recovery. Database integration verification for this continuation is pending (2026-11-08).


Sports availability is shared by `matchState` in `web/lib/sports.mjs`: board, detail, builder, discovery and slip use the same unavailable/live/final precedence and labels. Board/featured controls also pause during refresh errors; draft/slip contents remain reviewable (decision 0100).

Public upcoming match calendar downloads use `web/lib/match-calendar.mjs` for scheduled-match eligibility and one-time UTF-8 iCalendar serialization. MarketDetail displays local kickoff/timezone, pauses export on feed failures, and downloads a public-only event with a stable fixture UID (decision 0099).

Public copied match links optionally carry validated market category/search through `matchFiltersFromUrl`; MarketDetail restores these after mount. Navigation clears old match filters, and sharing excludes private selection state (decision 0098).

Match-detail market discovery uses `web/lib/market-discovery.mjs` for labels, categories and conjunctive local search/selected-market filtering. MarketDetail owns these view filters independently of global fixture search and slip state; unknown market kinds remain discoverable. Tablet research stacks the supporting panels below the market column (decision 0097).

Betslip feed-price review uses `applyPriceChanges` in `web/lib/sports-slip.mjs` to update prices only after explicit acceptance. BetslipTray compares prices/returns and supports unavailable-selection recovery; placement still uses the server quote and receipt contracts. Accepting a server quote refreshes the board snapshot (decision 0096).

Sports discovery offers an explicit all-sports scope; Favorites and new searches enter that scope before optional narrowing. `web/lib/sports.mjs` filters current feed fixtures and recognizes localized sport names. SportsHome keeps Favorites in browser storage, synchronizes tabs, retains missing fixture keys, and groups competitions by country/sport/name (decision 0095).

Public match links use `?match=<fixture key>` through `web/lib/match-link.mjs`. SportsHome synchronizes detail with browser history; MarketDetail offers clipboard/manual sharing. Links resolve against the current feed, with explicit loading/error/missing states (decision 0094).

The public sports transaction seam is `demo/sports_quotes.py`: current-board canonical selection/price validation, exposed by `/api/sports/quote` and enforced by `/api/bet`. `web/lib/sports-slip.mjs` shares board/slip selection and availability rules; receipt retries are resolved by player/request ID before consulting moved markets. See decision 0077.

A 1:1 high-fidelity hobby simulation of a modern betting platform and casino for personal usage.
The frame outlives the model: `core/` never imports `verticals/` or `models/`;
verticals and pricing providers plug into one frame instead of forking it.

## Layout

```text
operator/
├── AGENTS.md / ARCHITECTURE.md / PROGRESS.md / CURRENTTASK
├── Makefile / scripts/verify.py / scripts/verify.sh
├── decisions/ / docs/
├── frame/            the money core + verticals (stdlib only)
├── demo/             playable product: HTTP server, slot, Pix, risk, sports seam,
│                     Better Auth bridge (routes + oauth_links store)
├── auth-server/      self-hosted Better Auth (Google/Facebook/Apple, stateless)
├── foundry/          vendored kit modules (envfile, mail, turnstile, auth, betterauth)
├── web/              Next.js storefront (React 19), builds to web/out
├── probes/           captured live-feed evidence & provider demos
└── frame/
    ├── core/money.py        integer minor units, largest-remainder allocation, payout math
    ├── core/ids.py          single identity: fixture keys, refusal-to-guess matching
    ├── core/ledger.py       append-only hash-chained JSONL, write-once / fill-once
    ├── core/devig.py        margin analysis + 4 fair-price methods (mult/power/additive/shin)
    ├── wallet/books.py      double-entry journal, idempotent postings, player views
    ├── validation/gates.py  freshness, odds sanity, margin bounds, duplicates, settlement
    ├── compliance/sigap.py  game registry, exclusions, limits
    ├── models/registry.py   fair-price provider registry (devig methods registered)
    ├── verticals/sports/    SportsEngine contract + stub + real feeds
    │                        (Flashscore primary; shared marketboard + locale_pt;
    │                        Livescore then ESPN fallbacks. pricing.py is a
    │                        per-market book — exact overround, dnb/ah, a live
    │                        score tilt — and ESPN's published moneyline is the
    │                        one real price served, tagged `market`)
    ├── verticals/casino/    CasinoAggregator contract + deterministic stub
    ├── ops/scheduler.py     tiered loop, per-subject cooldown, daily cap, receipts
    ├── ops/notifier.py      ntfy fan-out (fail-open) + local file double for tests
    ├── ops/health.py        receipt freshness + ledger integrity + books balance
    └── tests/test_frame.py  45 execution checks; the executable spec

demo/
    ├── server.py            HTTP+JSON API, static serve (web/out → index.html)
    ├── arcade.py            crash, plinko, mines, dice, keno — sha256 draws, derived ladders
    ├── slot.py              6-tier paytable engine, SHA256 draw; one paytable per title (95.90 / 94.95 / 96.60)
    ├── casino.py            European single-zero roulette: deterministic ball, 35:1 straight, 1:1 even-money, RTP 97.30%
    ├── payments.py          CPF/CNPJ, Pix key, own-name bank, payout, allowlist
    ├── asaas.py             Asaas Pix rail: charge, QR, provider-confirmed credit (stdlib)
    ├── risk.py              velocity, stake spikes, loss-chase, RTP drift, dupes
    ├── sports_data.py       live-fixture seam (probes/) with stub fallback
    ├── vendor.py            official-content seam: https-only, gated titles
    ├── provider_demos.py    publisher-hosted demos: https + host allowlist
    ├── game_proxy.py        same-origin front for publisher games: wallet sync, /g/<game_id>
    ├── pg_proxy.py          PG Soft: a minted trial session, the hosts it
    │                        binds, and the measured money-API endpoints
    ├── player_session.py    signed player sessions: HMAC token, 12h/30d, per-device rows, epoch revocation (0069, 0070)
    ├── index.html           zero-build fallback storefront
    └── test_demo.py         411 execution checks

web/                        React 19 + Next 16 App Router (static export)
    ├── app/page.jsx        shell: casino, sports, embedded official game player, cashier
    ├── app/components/SportsHome.jsx   sport tabs, country→league groups, live scoreboard + odds
    ├── app/components/BetBuilder.jsx   match research, team counts, market groups and selection drafts
    ├── app/components/OddsButton.jsx   quote-derived transient directional feedback
    ├── app/apex.css                   Precision Noir tokens, sports rail and responsive betslip
    ├── lib/bet-builder.mjs             missing-data semantics and current-quote draft reconciliation
    ├── lib/useSportsFeed.js           sequential refresh, visible retry and last-successful board
    ├── app/components/CasinoHome.jsx   lobby: unified cards + official demos
    ├── app/globals.css     dark default + light toggle
    └── lib/api.js          shared fetch helper
```

## Three seams, one frame

| Seam | Module | Contract held fixed |
|------|--------|--------------------|
| Sports | `frame/verticals/sports/contract.py` `SportsEngine` | fixtures, markets, quote, accept, settle, void |
| Casino | `frame/verticals/casino/stub.py` `CasinoAggregator` | catalogue, launch, bet, wallet_credit, round_history |
| Payments | `demo/payments.py`, `demo/asaas.py` | Pix allowlist, own-name validation, two-step payout; a real Pix deposit credits only once Asaas confirms it |

The publisher-game proxy keeps one rule above the other two: **we never serve
bytes we cannot describe.** A body the proxy rewrites (document, money answer,
client bundle) is not revalidated against the publisher's validator, in either
direction; a body it passes through unchanged keeps the publisher's `ETag`
and answers 304. `GET /api/health` reports what the proxy did — a game that
does not load otherwise leaves no trace on the server — beside the PG mint
counters, so "the game did not open" is answerable as *the mint failed* or
*the proxy failed*, which are not visible in each other.

One publisher does not fit a suffix allowlist. PG Soft mints its hosts per
session (`m.<label>.com`, `api.<label>.com`) and signs every asset URL, so
the host binding is made by the process that asked for it: `pg_proxy.mint`
binds the exact strings the answer names, the session id travels in our own
path, and a host that is not `<prefix>.<label>.com` is never bound.

In-house originals (decision 0021): every launchable demo
game draws from `SHA256(game_id:round_id)` — slots through
their own paytable, roulette through the single-zero wheel
— and settles through `Books.place_bet` →
`settle_bet_win|loss` like any other bet. The live pulse
(`GET /api/live`) reads the plays log (15-minute window)
and the round ledger (newest wins, masked labels) only.

Concurrency and identity are part of the seam contract:
`Books` holds one `RLock` across the duplicate check, the balance guard, and the
append, so a request thread can never interleave a check with another thread's
posting. Payout destinations come from stored profile state.

## The lifecycle (money path)

`deposit` → `place_bet` → `settle` (win/loss) → `withdraw` (two-step: request then pay).

Every step posts a balanced journal entry under an idempotency key; every step is
gated (`validation/gates.py`); every close fills the integrity ledger exactly once.

## Wallet accounts

| Account | Meaning |
|---------|---------|
| `player:balance` | What the house owes the player (liability) |
| `player:bonus` | Bonus funds not yet released |
| `bonus:issued` | Contra for granted bonuses |
| `operator:cash` | House cash asset |
| `payable:player` | Approved withdrawals awaiting execution |
| `bet:staked` | Clearing: stakes awaiting settlement |
| `ggr:revenue` | Gross gaming revenue accumulator |
| `bonus:revenue` | Forfeited bonus accumulator |
| `adjustment:operator` | Manual corrections, always with a reason |

Invariant: the books sum to zero at all times. `assert_balanced()` enforces it.

## Execution substitutes

- `CURRENTTASK` is the objective; `PROGRESS.md` is the state.
- `decisions/` is the audit trail: newest file wins on conflict.
- `frame/tests/` is the spec: if it isn't tested by execution, it isn't true.

## Storefront appearances (0087)

`web/app/page.jsx` owns the `classic` / `blue` appearance independently of the light/dark theme. `Header.jsx` supplies the Visual selector; `variants.css` scopes Blue tokens/layouts over the original globals/workspace/apex baseline. `SportsHome.jsx` shares feed/filter/favorite/detail/selection state between both compositions. `casa-design` stores the browser choice and `?visual=classic|blue` takes precedence when opening a link. Switching changes React state and CSS, not routes or player sessions. The superseded Clubhouse stylesheet is not imported. See DESIGN.md and decision 0087.

## Durable identity (0071)

`Demo(db=factory)` selects SQL-backed account/social-link snapshots and device
rows. `identity_store.py` rejects stale writes using a revision counter;
`device_store.py` locks per player for device creation/revocation and updates
activity conditionally. `scripts/import_identity.py` performs an explicit atomic
file cutover into an empty database. No implicit restore runs on boot. Wallet
books and other unported state remain file-backed.

## Signup and payment minimums (0072)

Manual accounts select PF/CPF or PJ/CNPJ. Social accounts derive identity from
signed provider/subject claims and sign in directly, collecting Pix only at
withdrawal. The browser consumes a one-time social handoff; the obsolete CPF
completion flow is removed. Document validators live in `demo/payments.py`
and `web/lib/validation.js`; they cover numeric/alphanumeric CNPJ check digits.
`GET /api/deposit/limits` supplies authenticated provider/network minimums.
The UI gates and clamps amounts; provider clients enforce them again before
charge creation. Display quotes cache briefly; invoice creation refreshes the
NOWPayments quote. See decision 0072 for validation, privacy and flow limits.


## Separate local Tournament Blue (0088)

Normal builds remain Classic. NEXT_PUBLIC_LOCAL_BLUE=1 selects Blue at compile time in root layout and page; query/storage cannot select appearances. scripts/local_blue.py copies storefront sources and installed dependencies into a separate temporary build, exports Blue there, and serves it on localhost:8766 with an independent local account/books directory and database disabled. Production deploy was the approved Original snapshot taken before this local-only work. The prior runtime Visual selector documented in0087 is retired.

## Auteur Sports desk (0091)
Normal builds now select data-design=auteur. The scoped auteur.css layer and self-hosted Archivo/Source Sans3 fonts provide one frontend system across the existing working components; separate NEXT_PUBLIC_LOCAL_BLUE builds remain local Blue. SportsHome uses real feed score/context data, and account/cashier reuse current session/ledger/provider semantics. Financial/account UI is conditionally rendered only for a validated authenticated profile; logout clears selection state and private views. The neutral Entrar door and public match research remain. Vercel publication is frontend-only; backend and proxy contracts are unchanged.

## Interaction and member-access repair (0092)
Casino/catalog use validated authenticated state independently of the optional portal. Header/mobile builder intent invokes the existing SportsHome/BetBuilder workflow; the logo performs root document navigation. useSportsFeed exposes slow/error/empty recovery and passes a cancellation signal to api.js so retry/unmount aborts the current request. usePanelResize.js shares viewport-bound pointer/keyboard sizing between search and betslip. AccountView renders only the selected icon tab; cashier and session/ledger APIs are unchanged. Portal configuration is documented in docs/data-portal.md.

## Sports feed boundary (0103)

web/lib/sports-feed.mjs validates fixture identities and rendered header/score fields, plus source/note metadata, before useSportsFeed replaces its successful board. Invalid refreshes throw into the existing error/retry path: the board and timestamp remain intact and existing feed-error controls pause sports selection. Valid empty feeds remain successful. The validator returns the original payload without identity/label/price coercion; validMarkets separately isolates malformed market collections and outcomes (0102). CasinoHome applies the same reader before storing its independently fetched sports recommendations and retains its previous data on rejection. This is a display/header boundary, not a validator for every optional nested field.

## Casino sports feed recovery (0104)

CasinoHome now consumes its own useSportsFeed(true) instance instead of the former setInterval/empty-catch sports poll. CasinoSports presents its feed state: first-load/slow/error/retry, retained-data notice and successful timestamp, refreshing state and valid-empty calendar. Cards remain read-only navigation to the sports board through onSport(false), including during feed failures. The existing price validator and three-card limit remain. Reusing the hook provides sequential refreshes, abort-on-retry/unmount and last-successful retention without modifying other casino feeds. The superseded independent poll documented in0103 is removed.

## Recent-game cache isolation (0105)

localCache.js treats persisted recent-game entries as untrusted display data. Valid IDs remain available for the live catalog to resolve; only a complete typed snapshot with a matching ID is eligible for cached rendering. Numeric/string timestamps are converted safely and nonfinite/malformed values sort as unknown time (zero). Invalid rememberGame input leaves existing stored bytes intact. Valid labels and metadata are preserved exactly; existing ordering, limit, format decoding and quota id-only fallback remain. No server or catalog contract changes.
