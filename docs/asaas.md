# Asaas Pix rail — runbook

The operator takes **real Pix** through Asaas when it is configured, and falls
back to the instant demo credit when it is not. The double-entry books stay the
source of truth: a charge is a *request* to move money, and a deposit reaches a
player's balance only after Asaas independently confirms the payment.

Design rationale: [decision 0045](../decisions/0045-asaas-pix-rail.md).
Implementation: [`demo/asaas.py`](../demo/asaas.py).

## Credentials

Four settings, from the environment or a gitignored `.env.asaas` beside the
repository root. `.env.asaas` is never committed (`.gitignore` excludes
`.env.*`).

| Setting | What it is |
|---------|------------|
| `ASAAS_API_KEY` | the account's API key (`$aact_hmlg_…` on sandbox) |
| `ASAAS_CUSTOMER_ID` | the Asaas customer a charge is billed to (`cus_…` / id) |
| `ASAAS_WEBHOOK_SECRET` | the `authToken` Asaas echoes back in `asaas-access-token` |
| `ASAAS_BASE_URL` | `https://sandbox.asaas.com/api/v3` (default) or `https://api.asaas.com/v3` |

The rail is considered configured only when a key, a customer, and an **https**
base are all present. An `http://` base is treated as unconfigured rather than
used, so the account key can never go out in cleartext. `GET /api/health`
reports `asaas.configured` and `asaas.env` (`sandbox` | `production`).

Example `.env.asaas` (sandbox):

```text
ASAAS_API_KEY=$aact_hmlg_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ASAAS_CUSTOMER_ID=9387205
ASAAS_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ASAAS_BASE_URL=https://sandbox.asaas.com/api/v3
```

## Production (live 2026-10-19)

Production credentials live in the gitignored `.env.asaasprod`. The file must
be **complete**: `scripts/render_deploy.py` resolves the first complete
credential file among `.env.asaas` / `.env.asaasprod` / `.env.asaas.sandbox`,
and an empty `ASAAS_BASE_URL` makes the production file incomplete — the
sandbox file then wins silently. That trap was hit once; the fix is the
explicit line:

```text
ASAAS_BASE_URL=https://api.asaas.com/v3
```

Two production facts the sandbox hid:

- **A customer is per-account.** The sandbox customer id 404s in production,
  so a collection customer had to be created there. Asaas reads the CPF/CNPJ
  from the customer, not from the charge, so `POST /customers` carries the
  account holder's own `cpfCnpj` (read from `GET /myAccount`).
- **The webhook had been registered at the root.** Asaas was posting to
  `https://cadiback.onrender.com/`, which our handler does not serve. It now
  points at `https://cadiback.onrender.com/api/webhooks/asaas`, with
  `enabled: true`, `hasAuthToken: true`, and the token equal to
  `ASAAS_WEBHOOK_SECRET`.

The keys are never committed: they travel from `.env.asaasprod` into the
Render service's environment through the API, **additively** — a full-set
`PUT` replaces every variable and would drop the dashboard-only ones
(Better Auth, Turnstile, Resend, Supabase). `GET /api/health` reports
`asaas: {configured: true, env: "production"}` once the process has restarted.

The one step that needs a human is the first paid charge: create a R$5,00 Pix
deposit in the storefront and pay it. The webhook alone should credit the
saldo (no poll), and the poll must then agree without double-crediting.

## Before the first charge: provision the customer

Asaas refuses a charge when the billed **customer** has no CPF/CNPJ
(`invalid_object: … preencher o CPF ou CNPJ do cliente`), and an inline
`cpfCnpj` on `POST /payments` does **not** substitute — Asaas reads it from the
customer. Provision the configured customer once:

```bash
curl -sS https://sandbox.asaas.com/api/v3/customers/$ASAAS_CUSTOMER_ID \
  -H "access_token: $ASAAS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"cpfCnpj": "52998224725"}'
```

On the sandbox any valid-format CPF works; in production it is the operator's
(or, in a per-payer design, each player's) real CPF/CNPJ. Asaas also enforces a
**R$5,00 minimum** per charge — a smaller deposit is refused with a clear 400
rather than created. If the payer should be the player rather than one
collection customer, the production path is an Asaas customer per player
(storing the CPF is then required); the single configured customer is the
sandbox-first default.

## How a deposit flows

1. The player taps **Depositar** with the Pix method while `asaasAvailable` is
   true. The front end calls `POST /api/deposit/pix` with a client
   `deposit_id` and the amount.
2. The server opens a Pix charge (`POST /payments`) and reads its QR
   (`GET /payments/{id}/pixQrCode`). The charge is stored as **pending**; it is
   **not** a balance.
3. The cashier shows the QR and the copia-e-cola, and polls
   `POST /api/deposit/pix/status` every 5s.
4. When the money lands, either the webhook (`POST /api/webhooks/asaas`) or the
   poll notices. **Both** re-read the charge from Asaas, require a paid status
   and a matching amount, then post the deposit **once** through
   `_confirm_asaas_charge` (idempotent on `demo:deposit:{player}:{deposit_id}`).

A pending charge survives a restart (`$OPERATOR_DATA_DIR/asaas_charges.json`)
without crediting anyone. A webhook that fails the token check answers 401; a
transient server fault answers 5xx so Asaas retries; a body that can never be
accepted (unknown deposit, wrong reference, wrong amount) is acknowledged with
200 and dropped so Asaas does not retry it forever.

## Register the webhook

The webhook points at the public host — **Render**
(`https://cadiback.onrender.com`), not Fly. Register it after the deploy, once,
with the same token the server holds in `ASAAS_WEBHOOK_SECRET`:

```bash
curl -sS https://sandbox.asaas.com/api/v3/webhooks \
  -H "access_token: $ASAAS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "operator-deposits",
        "url": "https://cadiback.onrender.com/api/webhooks/asaas",
        "email": "you@example.com",
        "enabled": true,
        "interrupted": false,
        "authToken": "whsec_xxx_same_value_as_the_server",
        "sendType": "SEQUENTIALLY",
        "events": ["PAYMENT_RECEIVED", "PAYMENT_CONFIRMED",
                   "PAYMENT_OVERDUE", "PAYMENT_REFUNDED"]
      }'
```

`GET /v3/webhooks` lists what is registered; the sandbox starts at
`totalCount: 0`. Asaas validates a webhook by reaching the URL, which is why
the server answers `GET /api/webhooks/asaas` as well as the POST.

To simulate a paid Pix without waiting, confirm the charge in the sandbox
(`POST /v3/sandbox/payment/{id}/confirm`, sandbox only), which drives it through
the real statuses and fires the real webhook — exercising both the webhook and
the poll. (The `simulate` sub-path under `/payments` does not exist; the
sandbox action lives under `/sandbox/payment`.)

## Swap to production

1. Replace `ASAAS_API_KEY`, `ASAAS_CUSTOMER_ID`, and `ASAAS_WEBHOOK_SECRET`
   with production values and set `ASAAS_BASE_URL=https://api.asaas.com/v3`.
2. Re-register the webhook on the production account (same URL, same token).
3. Confirm `GET /api/health` reports `"env": "production"`.

## Deploy plumbing

The container needs the four settings at runtime, and they must not be
committed:

- `render.yaml` declares them as `sync: false` placeholders (Render prompts for
  the values in the dashboard and never stores them in the repository).
- `scripts/render_deploy.py` carries them from the gitignored `.env.asaas` (or
  the environment) to the host at deploy time. A missing value is simply not
  sent, so a deploy without credentials stays on the demo-credit fallback
  instead of half-configuring the rail.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Cashier still credits instantly | `asaas.configured` is false — missing key/customer, or a non-https base. Check `/api/health`. |
| QR never appears | `POST /api/deposit/pix` returned 400 — a non-Pix method, an unknown player, or a bad amount. |
| 400 `preencher o CPF ou CNPJ do cliente` | the configured Asaas customer has no CPF/CNPJ — provision it (see above). |
| 400 `não pode ser menor que R$ 5,00` | below Asaas's R$5,00 minimum charge. |
| Paid but no balance | The webhook token does not match, the amount does not match, or the charge ref is different. The poll should still credit within 5s. |
| Asaas retries the webhook | The server answered 5xx (a transient fault). Retries are expected and safe: confirmation is idempotent. |
