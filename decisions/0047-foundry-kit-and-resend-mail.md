# 0047 — The foundry kit, and email through it (Resend)

Date: 2026-10-15
Status: accepted

## Context

Email was requested (Resend) — for the operator *and* for wall-e — and the
larger wish behind it: stop re-solving the same plumbing in every service.
Three dotenv parsers already existed here; two Asaas clients existed across the
operator and wall-e; each project had its own webhook-signature check. The
operator and wall-e have almost nothing in common (one is a stdlib-only single
container, the other a FastAPI + SQLAlchemy service), yet they keep meeting at
the same small problems.

So this was done as two things at once: **found** a reusable kit, and make
**email** the first module in it.

## Decision

### 1. `projects/foundry` — a stdlib-core module kit

A standalone project (its own git repo) of small, host-agnostic modules under
one contract:

> A module's core is stdlib-only; every outside dependency is injected.

Full rationale and the module checklist are in `projects/foundry/`:
`docs/MODULES.md`, `ARCHITECTURE.md`, `decisions/0001`. Deploy manifests for
Render, Fly.io and Vercel live there as `{{TOKEN}}` templates, stamped by
`python -m foundry.deploy <host>`.

### 2. How the operator consumes it: vendoring, not a dependency

`foundry` is copied into `operator/foundry/` by
`projects/foundry/scripts/vendor.py`, with a per-file source hash in
`VENDOR.foundry.json`. Copy, not link, and not a pip dependency:

- a pip dependency breaks the operator's **stdlib-only** contract;
- a path dependency works on this laptop and breaks on Render, because the
  build only sees files inside this repository.

The vendored modules are stdlib-only, so the operator still `pip install`s
nothing. `Dockerfile` copies `foundry/` in beside `frame/` and `demo/`.

### 3. Email is best-effort, and the welcome email is opt-in

`foundry.mail` wraps one HTTP call to Resend behind an injected transport (the
default is `urllib`). In the operator:

- `Demo.mailer` is resolved from the environment at boot; `mailer=` is
  injectable so tests never touch the network. With no key the **console
  mailer** logs instead of sending, so an unconfigured deploy stays healthy.
- The welcome email on signup is behind a new setting **`mail_welcome`,
  default off**. A sandbox full of `example.com` test signups must not be
  handed to a sending domain and bounced; the admin test-send proves the rail
  without that. `_send_welcome` is wrapped so a mail failure never fails a
  signup.
- `POST /api/admin/mail/test` (admin-only) sends one test email, so an operator
  can verify the key end to end without waiting for a real signup.
  `/api/health` reports `mail: {provider, enabled, welcome_enabled}`.
- The module itself **refuses reserved/undeliverable recipients locally**
  (`example.com`, `.invalid`, …) — the fastest way to damage a sending domain
  is to hand a provider addresses that cannot exist. Reason and escape hatch in
  `foundry/decisions/0002`.

Deploy carries `RESEND_API_KEY` / `MAIL_FROM` from the gitignored `.env.resend`
(`scripts/render_deploy.py`); `render.yaml` holds `sync: false` placeholders
only, so no secret enters the repository. Runbook: `docs/mail.md`.

## Alternatives considered

1. **A small local `demo/mail.py` instead of a kit.** Fastest. Rejected: the
   request was explicitly to make it reusable and to scale beyond the operator;
   a one-off would be the fourth copy of "call a provider over HTTPS".
2. **`httpx` in the mail module.** Would simplify wall-e and lock the operator
   out. Rejected — the injection seam costs one parameter.
3. **Welcome email on by default.** Tempting, but a demo domain receiving
   `example.com` bounces is a real (self-inflicted) reputation risk. Off by
   default, one toggle away, with a test-send to prove it works.
4. **Auto-fetching the bank account from the Pix key** (the owner's ideal,
   carried over from 0046): Asaas exposes no DICT lookup and a bank account is
   not derivable from a key. Unrelated to this decision but reaffirmed here —
   the honest resolution stays "the account is optional".

## Notes

- `frame` 45/45, `demo` 263/263 (+5 mail), `verify.py` 0. The kit's own suite is
  26 checks and `projects/foundry/scripts/verify.py` also fails the build on a
  non-stdlib import under `foundry/`.
- Wall-e consumes the same module by vendoring it into `src/foundry/` and wiring
  a best-effort operations notification on settlement.
- Next modules by the lift path: `webhooks` (signature verify), then
  `payments/asaas` and `payments/mercadopago`.
