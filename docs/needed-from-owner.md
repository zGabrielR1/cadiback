# Needed from the owner

The one list of things that are waiting on you. Everything not here is either
done and live, or code I can still work on without you.

Last updated: 2026-10-19 (Asaas production live).

## 1. Asaas production — configured, one paid deposit to close the loop

The Pix rail is now **configured for production**:

- `.env.asaasprod` (still gitignored, never committed) holds the production
  key, customer and webhook secret, with
  `ASAAS_BASE_URL=https://api.asaas.com/v3`.
- The four `ASAAS_*` values were merged **additively** into the Render service
  (the other variables were preserved; the full-set sync was not used), and
  the deploy reports `asaas: {configured: true, env: "production"}`.
- The production account had no collection customer, and the sandbox customer
  id does not exist there (404), so one was created from the account's own
  `/myAccount` name/CPF. Asaas needs that customer to carry a CPF/CNPJ.
- The pre-existing webhook pointed at `https://cadiback.onrender.com/` — the
  root, which our handler does not serve. It now points at
  `https://cadiback.onrender.com/api/webhooks/asaas` with `hasAuthToken: true`
  and the local secret.

What is still waiting on you: **one real R$5,00 Pix deposit through the
storefront**, paid from your bank app. That is the only step that proves the
provider-confirmed credit on the production account; everything up to the QR
was verified with read-only calls, and nothing moves until you pay it.

Full runbook: `docs/asaas.md`.

## 2. Cryptocurrency — already done, nothing needed

You put the NOWPayments API key and the IPN secret in `.env.crypto` (as two bare
lines). That is now loaded and **live on production**: `/api/config` reports
`crypto_enabled: true` with 6 coins, and a real invoice opens through the
deploy. Each invoice carries its own `ipn_callback_url` pointing at our host, so
you do **not** need to set the IPN URL in the NOWPayments dashboard (doing so
anyway is harmless). Runbook: `docs/crypto.md`.

If you ever rotate the key or secret, just replace the two lines in
`.env.crypto` and push.

## 3. Nothing else

- Test deposits, the admin win/loss control (+ win-rate slider) and the wallet
  saldo are live and verified.
- Sports (icons, bigger selections, count markets from live stats) is live.
- Roda da Sorte (the new original, 97% RTP) is live.
- Provider wallets: the harness proves our wallet answers + debits for all
  sampled games. Two items are **code**, not credentials, and I keep working
  them: Pragmatic Play's client parks on its splash off-origin, and Spribe
  settles its round over a binary socket our tap does not decode.

## How a deploy works (so you can do it too)

The live service builds from `github.com/zGabrielR1/cadiback` (`main`,
`autoDeploy` on). So: commit, push, and Render rebuilds in about two minutes.
Do **not** run `scripts/render_deploy.py`'s env-var sync against the live
service — it replaces the whole variable set and would drop the dashboard-only
ones (Authgear, Turnstile, Resend, Supabase). New secrets are merged in
additively through the Render API instead.
