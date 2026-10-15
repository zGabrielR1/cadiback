# 0045 — Asaas Pix rail: a real charge, provider-confirmed before a centavo posts

Status: built, unit-tested, and **live-verified in the Asaas sandbox** (a real
R$5 charge → QR → provider confirm → webhook credit → replay-safe). The webhook
is registered after the deploy; until then the operator runs the instant demo
credit exactly as before. Sandbox first.

## The rule that shapes everything

A deposit is *two* facts, and they are not the same fact:

- a charge exists, and the player is looking at a QR code (`POST /payments`), and
- the money actually arrived.

Only the provider can testify to the second. So the webhook is treated as a
**hint that something happened, never as proof that it did**. Every confirmation
— from the webhook or from the poll — re-reads the charge from Asaas
(`GET /payments/{id}`), requires a terminal status (`RECEIVED`/`CONFIRMED`) and
requires the amount to match what we asked for. A replayed event, a forged body,
or a webhook fired by an unrelated charge credits nothing.

This is the same posture as the publisher-game taps (0032/0043/0044): read
truth from the side that owns it, never from the message that announces it.

## Why the operator, not wall-e

The platform is a single stdlib-only container (0038/0039) whose own
double-entry ledger is the source of truth. Routing deposits through the
separate `wall-e` service would split one money path across two systems (two
ledgers, two crash domains, two things to keep in sync) to buy nothing the
operator needs. So the rail is direct: `demo/asaas.py`, stdlib `urllib` only,
which keeps the "no `pip install`" deploy rule and keeps one ledger.

## What was built

- **`demo/asaas.py`** — `AsaasConfig` (env / gitignored `.env.asaas`, https
  enforced, sandbox-vs-production named from the URL), `AsaasClient`
  (create charge, read charge, `pixQrCode`, constant-time webhook check),
  `Charge`, `resolve_webhook`, a four-outcome status map
  (`PENDING`/`PAID`/`EXPIRED`/`CANCELLED`/`REFUNDED`), and a transport that is
  injectable so the whole path is testable with no network and no key. A
  cross-host redirect is refused, so the account key can never be replayed to
  another origin.
- **`demo/server.py`** — `create_pix_deposit`, `pix_deposit_status`,
  `_confirm_asaas_charge`, `asaas_webhook`; routes `POST /api/deposit/pix`,
  `POST /api/deposit/pix/status`, and `POST|GET /api/webhooks/asaas` (routed
  *before* the same-origin gate — Asaas calls it from its own servers). The
  `asaas` block is on `/api/health`; pending charges persist under
  `$OPERATOR_DATA_DIR/asaas_charges.json`.
- **Frontend** — `useSession` exposes `asaasAvailable`; the cashier shows the
  QR and the copia-e-cola with a copy button and polls the status endpoint
  every 5s while it is on screen; with no rail configured it keeps the instant
  demo credit unchanged.

## Idempotency, in three places

1. The client sends `Idempotency-Key: dep:{deposit_id}`, so a retried create
   does not open a second charge.
2. `create_pix_deposit` is idempotent on `deposit_id` — a retried request
   returns the same charge.
3. The books post under `demo:deposit:{player}:{deposit_id}` inside the
   `books.lock`, and `_confirm_asaas_charge` returns early if the charge is
   already `posted`. The webhook and the poll share that one path, so the two
   can race without paying twice.

Lock order is fixed: `_asaas_lock` (an `RLock`) taken before `books.lock`.

## Sandbox vs production

One field moves the rail:

| | sandbox | production |
|---|---|---|
| base URL | `https://sandbox.asaas.com/api/v3` | `https://api.asaas.com/v3` |
| key | `$aact_hmlg_…` | production key |
| customer | sandbox customer id | production customer id |

Nothing else changes. `env` on `/api/health` reports which one is configured.
The runbook is `docs/asaas.md`.

## Two constraints the fake transport could not see

The unit suites passed while the rail was still unusable against the real API,
because a canned transport never refuses. The live smoke found both:

- **The billed customer must carry a CPF/CNPJ.** `POST /payments` answers
  `invalid_object: … preencher o CPF ou CNPJ do cliente` — and an inline
  `cpfCnpj` on the payment does **not** substitute; Asaas reads it from the
  customer. Provisioning is one call (`POST /customers/{id} {"cpfCnpj": …}`),
  documented in `docs/asaas.md`. The sandbox customer was a bare `Cliente`;
  it now has one.
- **Asaas enforces a R$5,00 minimum per charge.** R$1 is refused
  (`não pode ser menor que R$ 5,00`), which the smoke hit second time round.
  A smaller deposit surfaces the provider's 400 rather than creating anything.

The live smoke also pinned the sandbox confirm action to
`POST /v3/sandbox/payment/{id}/confirm` (an earlier guess, `/payments/{id}/
simulate`, is a 404).

## Honest limits

- **Live-verified in the sandbox, not in production.** A real sandbox charge was
  created, confirmed provider-side and credited through the webhook once, with a
  replay crediting nothing and the books balanced. Production swaps the three
  credentials and re-registers the webhook (the runbook covers it).
- **The webhook is registered after the deploy.** Nothing is registered in
  Asaas until then (`GET /v3/webhooks` → `totalCount: 0`), so the earlier "does
  the callback point at Fly or Render?" question was moot. Render
  (`https://cadiback.onrender.com`) is the host; Fly is down and uncommitted.
- **The payer is one configured customer, not the player.** The sandbox-first
  default charges `ASAAS_CUSTOMER_ID`; a per-payer design (an Asaas customer per
  player, CPF stored) is the production path and is deliberately not built yet.
- **Secrets never enter the repository.** The host gets the four `ASAAS_*`
  values from `render_deploy.py` (reading the gitignored `.env.asaas`) or from
  the Render dashboard; `render.yaml` carries `sync: false` placeholders only.
