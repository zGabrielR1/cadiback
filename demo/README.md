# demo — playable platform layout (slot + Pix). DEMO, no real money.

Clickable front-end for the house foundation: onboarding with personal info
(name + CPF + Pix key + bank account), Pix/TED/debit cashier, one working
slot behind the BR cert gate, and a working Pix payout. The PSP and the
reels are stubs; the wallet, ledger gates, and cert gate are the real frame.

## Run it

```bash
python -m demo.server      # playable demo on http://127.0.0.1:8765 (no real money)
python -m unittest demo.test_demo -v   # demo spec, 56 checks
python -m frame.selftest               # foundation spec (43 checks)
```

Vendor sandbox (route 1, decision 0003) plugs in without re-architecture:

```bash
set DEMO_AGGREGATOR=everymatrix & set DEMO_API_URL=https://sandbox.vendor.example & set DEMO_API_KEY=... & python -m demo.server
```

With the seam configured, `/api/catalog` shows a `vendor` block: official
titles are listed but stay non-launchable until their real BR certificates
are registered (ask pack: `p3/sandbox-request.md`). Until then the stub
serves the generic demo titles below.

## Layout (single page, three steps + history)

1. **Jogador** — name, CPF (check digits enforced), Pix key
   (CPF/CNPJ/email/phone/EVP classified), bank (3-digit code, agency,
   account, holder must equal the player: own-name rule, Portaria 615/2024).
2. **Caixa** — deposit via pix/ted/debit (credit, crypto, cash, boleto, and
   Pix Credito rejected by name); instant Pix payout with masked-key receipt
   and two wallet postings (request + paid) so the PSP leg stays observable.
   Deposits and payouts are idempotent on a client-supplied id, so a
   double-click is a replay rather than free money. A payout can only leave to
   the Pix key on file: the own-name rule is enforced server-side against the
   stored profile, never against the request body.
3. **Slot** — generic in-house titles only (`Neon Gems`, `Fortune Ledger`);
   `Royale Roulette` renders BLOQUEADO and the API refuses it.
   Stakes R$2/5/10/25. Deterministic `SHA256(game:round)` draw, six tiers,
   demo RTP 95.90% (illustrative, not a lab certificate).
4. **Histórico + risco** — rounds, `health()`, self-exclusion button, and
   the in-house risk flags (`risk.py`: velocity, stake spikes, loss-chase,
   RTP drift vs the 95.90% model, duplicate rounds) computed over every
   round on file and shown under the table.
## Real vendor content — publisher-hosted demos

The lobby's official content is the **publishers' own free-play demos**, served
from the publishers' own hosts. We store only facts and open their page; we do not
rehost, mirror, or copy their game code, artwork, or files (decision 0006).

- `probes/provider-demos.json` — 7 demos across Pragmatic Play, PG Soft, Hacksaw
  Gaming, Play'n GO, and Evolution, one https URL each, per-row provenance.
- `demo/provider_demos.py` — loader with two hard rules: **https only** and a
  **publisher-host allowlist**. A cleartext URL or a non-publisher host is dropped
  before it can reach the lobby.
- `/api/catalog` exposes the block as `provider_demos`; every row is
  `wallet_isolated: true` and `launchable: false`, so no stake or payout routes
  through it. Real-money play still needs a signed aggregator + per-title BR cert.

## Live sports data

`GET /api/sports` is served by the in-house odds engine
(`demo/odds_engine.py`, decision 0016): deterministic team-strength →
Poisson probabilities → 5%-margin book prices, repriced on a 30s bucket,
`source: "inhouse"`, `licensed_feed: false`. The ESPN capture
(`probes/live-fixtures.json`) survives as a fact source for the news
panel; `scripts/probe_live_feeds.py` / `scripts/fetch_live_fixtures.py`
can still refresh it.

```bash
python scripts/probe_live_feeds.py     # which feeds answer, from here
python scripts/fetch_live_fixtures.py  # bra.1 / ita.1 / nfl fixtures -> probes/
```

No third-party key required; SharpAPI.io was considered and skipped —
the engine is offline and reproducible.

5. **Demo oficial externa (opcional)** — set `DEMO_IFRAME_URL=https://…`
   to an *official provider free-play page* and the layout renders it in an
   isolated section: third-party content, no wallet link, no stakes touch
   our books. Unset by default. This is the only legitimate way to eyeball
   official games locally without a contract: their servers, their demo,
   your eyes only.

## API (JSON, same origin)

- `GET /api/catalog` → games with `certificate_id`, `launchable`, `demo_rtp`,
  plus `provider_demos` (publisher-hosted, wallet-isolated)
- `POST /api/player` → register `{name, email, cpf, password, pix_key,
  bank:{bank_code, agency, account, holder_name}}` — every field validated
  (email shape, CPF check digits, 6+ chars with letters and digits); one
  wallet per CPF and one per email
- `POST /api/player/login` → `{identifier, password}` (email or CPF) —
  failed attempts pay a fixed delay; credential hashes never leave the store
- `GET /api/player?id=` → profile + `available_minor`
- `POST /api/deposit` → `{player, amount_minor, method}`
- `POST /api/spin` → `{player, game_id, stake_minor, round_id?}` → symbols/tier/payout
- `GET /api/sports` → in-house engine fixture + markets feed (`source: "inhouse"`)
- `POST /api/withdraw` → `{player, amount_minor, pix_key, holder_name, payout_id?}` → receipt
- `POST /api/self-exclude` → `{player, until}`
- `GET /api/history?player=` (rounds + in-house risk flags)
- `GET /api/health` (read-only) · `GET /api/sports` (in-house engine + provenance)
- `POST /api/auth/login` → `{username, password}` → `{token, username,
  role}` (default admin/admin; failed attempts pay a fixed delay)
- `GET /api/auth/me` · `POST /api/auth/logout` — Bearer token sessions,
  12h TTL, dropped on restart
- `POST /api/auth/password` → change own password (requires the current
  one; revokes every session for that user, reissues this one)
- `GET /api/admin` — painel administrativo (Bearer required): totais,
  RTP, top ganhadores, maiores prêmios, série de 7 dias; tudo derivado
  dos stores
- `GET /api/admin/users` · `POST /api/admin/users` ·
  `POST /api/admin/users/reset` · `POST /api/admin/users/delete` —
  admin role only; salt/hash never leave the server
- `POST /api/self-exclude` / `POST /api/self-exclude-lift` (persisted, expiring)

Writes require `Content-Type: application/json` and a same-origin `Origin`
(header optional, for curl). Certification and exclusion failures answer 403;
unexpected errors answer 500 with the exception type only, never a path.

## What is real vs stub

Real: `Books` double-entry (every demo centavo balances), `GameRegistry`
cert gate, `ExclusionRegistry`, `Limits` (R$50.000/day demo cap), CPF/CNPJ
check digits, email shape, player password policy (SHA-256 salted, constant
time), Pix/bank shape validation, idempotent payout keys.
Stub: PSP rail (instant success after validation), slot RNG (deterministic
hash, not a lab RNG), certificates `BR-DEMO-*` (format-valid, value-void).

## Files

`server.py` (HTTP + API) · `index.html` (layout) · `slot.py` (paytable +
draw) · `payments.py` (CPF/Pix/bank + payout) · `risk.py` (in-house
fraud detection: velocity, spikes, loss-chase, RTP drift, duplicates) ·
`vendor.py` (aggregator seam: explicit-URL client, vendor titles gated
non-launchable) · `provider_demos.py` (publisher-hosted demos: https + host
allowlist) · `odds_engine.py` (in-house pricing + fixture board) ·
`sports_data.py` (capture loader for the news panel) · `test_demo.py`
(78 checks).
Runtime state lands in `demo/data/` (books, players, rounds, promos — demo only).
