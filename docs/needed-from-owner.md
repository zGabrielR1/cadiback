# Needed from the owner

The one list of things that are waiting on you. Everything not here is either
done and live, or code I can still work on without you.

Last updated: 2026-10-18 (session 2).

## 1. Asaas production keys (the only hard blocker)

The Pix rail is wired and running on **sandbox** right now
(`GET /api/health` → `asaas: {configured: true, env: "sandbox"}`). To go to
production, drop the three production values into `.env.asaasprod`:

```
ASAAS_API_KEY=<your production key>
ASAAS_CUSTOMER_ID=<your production customer id>   # already filled in
ASAAS_BASE_URL=https://api.asaas.com/v3
ASAAS_WEBHOOK_SECRET=<your production webhook secret>
```

`scripts/render_deploy.py` picks the first **complete** credential file among
`.env.asaas` / `.env.asaasprod` / `.env.asaas.sandbox`, so a half-filled prod
file keeps sandbox running instead of pairing a prod customer with a sandbox
key. Once the file is complete:

1. push to `github.com/zGabrielR1/cadiback` (`main`) — that is the deploy;
2. register the Asaas webhook →
   `https://cadiback.onrender.com/api/webhooks/asaas` (`hasAuthToken: true`).

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

The working tree is not a git checkout; the live service builds from
`github.com/zGabrielR1/cadiback` (`main`, `autoDeploy` on). So: commit, push,
and Render rebuilds in about two minutes. Do **not** run
`scripts/render_deploy.py`'s env-var sync against the live service — it replaces
the whole variable set and would drop the dashboard-only ones (Authgear,
Turnstile, Resend, Supabase). New secrets are merged in additively through the
Render API instead.
