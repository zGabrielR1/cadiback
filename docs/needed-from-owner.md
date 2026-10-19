# Needed from the owner

The one list of things that are waiting on you. Everything not here is either
done and live, or code I can still work on without you.

Last updated: 2026-10-19 (Better Auth replaces Authgear).

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

## 3. PG Soft in production — nothing needed (fixed in code)

PG's client only accepts money calls when they reach a document on the same
origin: its api host CORS-allows `*.pg-demo.com` and nothing else. That used
to make a custom domain the only way in. It no longer does.

The injected bridge now rewrites PG's own money XHRs (`/web-api/…`,
`/game-api/…`) onto the document's own origin, and our server forwards them to
the api host the mint named. That is same-origin from the browser's point of
view, so there is no preflight and no CORS — on `cadiback.onrender.com` and on
the Vercel storefront, with no DNS work. Verified live with no steering: every
money call 200, rounds settle on our books, including wins.

You do **not** need to do anything. A custom domain remains supported and
optional: if you ever want `pg.<your-domain>` and `api.<your-domain>`, follow
the steps below and set `PG_PUBLIC_HOST=pg.<your-domain>`
(`PG_AO_HOST=api.<your-domain>` is optional) — `/api/health` will then report
`pg_soft.routing.production_ready: true`.

<details>
<summary>Optional custom-domain steps (no longer required)</summary>

1. In your DNS, create two records pointing at `cadiback.onrender.com`
   (CNAME is fine):
   - `pg.<your-domain>`   (the document)
   - `api.<your-domain>`  (the money calls)
   A wildcard `*.<your-domain>` works too.
2. In the Render dashboard, add both `pg.<your-domain>` and
   `api.<your-domain>` as custom domains of the `cadiback` service (Render
   provisions TLS for them).
3. Set two env vars on the service:
   - `PG_PUBLIC_HOST=pg.<your-domain>`
   - `PG_AO_HOST=api.<your-domain>`   (optional: derived as `api.<domain>`
     when omitted)
4. Redeploy.

</details>

## 4. Better Auth — paste the three provider credentials

Social login now runs on **Better Auth**, self-hosted in the container; the
Authgear dependency is gone. The wiring, the sidecar, the signed bridge and
the CPF flow are done and verified locally. What is still needed is the three
providers' own credentials, which only your accounts can issue:

- **Google**: OAuth client ID + secret (Web application).
- **Facebook**: App ID + App Secret.
- **Apple**: Services ID, Team ID, Key ID, and the `.p8` private key (a paid
  Apple Developer account is required; Apple does not accept `localhost`).

Put them in the gitignored `.env.betterauth` (the bridge/server secrets are
already generated there), then merge them into the Render service
additively — the same rollout as Asaas, not the full env-var sync. Register
these exact callbacks with each provider:

- `https://cadiback.onrender.com/api/betterauth/callback/<provider>`
- `https://cadiback-web.vercel.app/api/betterauth/callback/<provider>`

`GET /api/health` prints `betterauth.callback_urls` computed from the host you
call, so the string to paste is never a guess. Until the credentials are in,
each provider is simply hidden; the rest of the site is unaffected.

The optional `BETTER_AUTH_API_KEY` you already supplied is wired; it loads the
Better Auth infrastructure dashboard when present.

Full runbook: `docs/oauth.md`.

## 5. Nothing else

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
ones (Better Auth, Turnstile, Resend, Supabase). New secrets are merged in
additively through the Render API instead.
