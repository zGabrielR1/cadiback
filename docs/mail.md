# Email (Resend) — runbook

The operator sends email through the **foundry** kit's `mail` module, which
calls the Resend API over stdlib `urllib`. Nothing is installed; the module is
vendored at `foundry/` (see `decisions/0047`).

## Credentials

Two variables, both optional:

| Variable | Meaning |
|---|---|
| `RESEND_API_KEY` | the Resend key (`re_…`). No key → console mailer. |
| `MAIL_FROM` | the verified sender, e.g. `candibet <nao-responda@seudominio.com>` |
| `MAIL_FROM_NAME` | optional display name if `MAIL_FROM` is a bare address |
| `MAIL_PROVIDER` | `resend` \| `console` \| `none` (usually unset — auto) |

They live in the gitignored **`.env.resend`** at the repository root. Write it as
`KEY=value` lines, or as a single bare key on one line (the shape `.env.render`
already uses) — both are read, and a variable exported in the environment always
wins over either. Never commit a key: `render.yaml` carries only `sync: false`
placeholders, and `scripts/render_deploy.py` carries the real values from
`.env.resend` (or the environment) at deploy time.

```bash
# .env.resend   (gitignored)
RESEND_API_KEY=re_xxxxxxxx
MAIL_FROM=candibet <nao-responda@seudominio.com>
```

Until a sending domain is verified with Resend, `MAIL_FROM=onboarding@resend.dev`
is the working placeholder — Resend accepts it and delivers only to the account
owner's own address, which is enough to prove the rail and receive the test send.

## How the rail behaves

- **No key** → the **console mailer**: every send prints one line to stderr and
  sends nothing. The deploy is healthy and `/api/health` shows
  `mail.provider = "console"`, `mail.enabled = false`.
- **Key present** → `ResendMailer`. `/api/health` shows
  `mail.provider = "resend"`, `mail.enabled = true`.
- **`MAIL_PROVIDER=resend` with no key** → `NullMailer` (do nothing). This is a
  misconfiguration, so it is *not* quietly downgraded to the console.

Neither state can break a request: the welcome email is best-effort (a mail
error is swallowed), and the admin test-send returns the error to the panel.

## Reserved addresses are refused locally

The module refuses to send to `example.com` / `example.org` / `example.net` and
any `.invalid`, `.test`, `.localhost`, `.local`, `.internal` address **before the
request leaves the process**. The demo's own test signups use `example.com`
addresses, and handing a provider a list of addresses that can never be
delivered is the fastest way to damage a sending domain's reputation.
`allow_reserved=True` on the mailer is the deliberate override; it is off by
default.

## Turning on the welcome email

The welcome email is **off by default** (`mail_welcome` in the settings store).
Turn it on in the painel: **Configurações do cadastro → "Enviar email de
boas-vindas no cadastro"**, or

```bash
curl -X POST https://<host>/api/admin/settings \
  -H 'Authorization: Bearer <admin token>' \
  -H 'Content-Type: application/json' \
  -d '{"mail_welcome": true}'
```

It is idempotent per player (`Idempotency-Key: welcome:<player_id>`), so a
retried registration cannot send a second welcome.

## Verifying the key end to end

Use the panel's **"Enviar um email de teste"** box, or:

```bash
curl -X POST https://<host>/api/admin/mail/test \
  -H 'Authorization: Bearer <admin token>' \
  -H 'Content-Type: application/json' \
  -d '{"to": "voce@seudominio.com"}'
```

A `200` returns the provider message id; a `400` returns the provider's own
reason (a bad `MAIL_FROM`, an unverified domain) without ever echoing the key.

## Sending domain

Resend only delivers from a domain you have verified (DNS records for SPF/DKIM).
Until that is done, use `MAIL_FROM=onboarding@resend.dev` (what `.env.resend`
currently carries) — Resend accepts it and delivers only to the account owner's
address, which is enough to verify the rail and to receive the test-send. Switch
to your own domain before sending to real players.

## What is *not* email

Deposit and withdrawal receipts are **not** sent yet. The rail is wired, tested
and observable; adding another trigger is a small, separate change (build the
`Message`, call `self.mailer.send` best-effort, add the idempotency key).
