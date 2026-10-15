# Turnstile (Cloudflare) — runbook

The player **login** and **signup** surfaces are gated by a Cloudflare Turnstile
challenge, verified server-side by the **foundry** kit's `turnstile` module over
stdlib `urllib`. Nothing is installed; the module is vendored at `foundry/` (see
`decisions/0048`).

The gate is *gate, don't replace*: `Demo.require_turnstile` runs before the
handler reads any credential, and the existing login/signup logic is unchanged.

## Credentials

Three variables, all optional:

| Variable | Secret? | Meaning |
|---|---|---|
| `TURNSTILE_SECRET_KEY` | **yes** | the widget's Secret Key (dashboard > Turnstile > your widget) |
| `TURNSTILE_SITE_KEY` | no — public | which widget the page renders |
| `TURNSTILE_HOSTNAMES` | no | comma-separated hostnames siteverify must return |
| `TURNSTILE_DEV_HOSTNAMES` | no | extra hostnames for local work (`localhost`) |

They live in the gitignored **`.env.turnstile`** at the repository root. Never
commit the secret: `render.yaml` carries only `sync: false` placeholders, and
`scripts/render_deploy.py` carries the real values from `.env.turnstile` (or the
environment) at deploy time. `TURNSTILE_DEV_HOSTNAMES` is **never** carried — a
production allowlist must not contain loopback.

```bash
# .env.turnstile   (gitignored)
TURNSTILE_SECRET_KEY=0x...
TURNSTILE_SITE_KEY=0x4AAAAAAFX5o_Oc75RuRFDo
TURNSTILE_HOSTNAMES=cadiback.onrender.com
TURNSTILE_DEV_HOSTNAMES=localhost,127.0.0.1
```

## How the rail behaves

- **No secret** → the verifier is **disabled**: `/api/health` shows
  `turnstile.provider = "none"`, `turnstile.enabled = false`, and the gate is a
  no-op. A deploy without credentials stays healthy and local work is unaffected.
- **Secret + a hostname** → `SiteverifyVerifier`. `/api/health` shows
  `turnstile.provider = "turnstile"`, `turnstile.enabled = true`, and the
  storefront renders the widget (the public site key comes from `/api/config`).
- **Secret but no hostname** → treated as unconfigured, not "enabled but always
  refuses": a verifier that could never accept a token would turn every login
  into a 403. Set `TURNSTILE_HOSTNAMES` to arm it.

The gate is also switchable from the painel (`turnstile_login`, default **on**):
**Configurações → "Exigir verificação anti-bot no login e no cadastro"**, or

```bash
curl -X POST https://<host>/api/admin/settings \
  -H 'Authorization: Bearer <admin token>' \
  -H 'Content-Type: application/json' \
  -d '{"turnstile_login": false}'
```

## What is checked

`verify()` enforces Cloudflare's canonical policy, not just `success === true`:

1. `success` is true,
2. the returned `action` equals the surface's action (`login` or `register`),
3. the returned `hostname` is on `TURNSTILE_HOSTNAMES`.

A token minted on someone else's page with the public site key is
`success: true` and fails checks 2 and 3. A missing, oversized, replayed, or
expired token is refused before the handler runs (HTTP **403**).

## Widget domains

The widget only renders on the hostnames registered on it (dashboard > Turnstile
> your widget > Domains). Register `cadiback.onrender.com`; add `localhost` and
`127.0.0.1` too if you want to exercise the widget locally. `TURNSTILE_HOSTNAMES`
must list the same hostnames the backend expects.

## Turning it on live

1. Put the Secret Key in `.env.turnstile`.
2. `python scripts/render_deploy.py --yes` — it carries the three production
   values and prints `carrying 3 Turnstile setting(s)`.
3. Confirm `/api/health`: `turnstile.enabled` true, `hostnames` =
   `["cadiback.onrender.com"]`.
4. Open the storefront login, solve the challenge, and sign in. A missing token
   is refused with a clear message.

## Tokens are single-use

The storefront renders the widget explicitly (`web/app/components/TurnstileWidget.jsx`)
and resets it after every submit attempt, because a token is redeemed exactly
once at siteverify. A retry that reuses a token is refused — by design.
