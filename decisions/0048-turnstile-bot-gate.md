# 0048 — Turnstile on the player login and signup surfaces

Date: 2026-10-15
Status: accepted

## Context

The player login (`POST /api/player/login`) and signup (`POST /api/player`) are
open to bots: nothing on the way in separates a person from a script. Cloudflare
Turnstile is the chosen CAPTCHA replacement — a widget on the storefront hands
the browser a token, and the *server* exchanges it at siteverify.

The operator may not `pip install` anything, so the integration cannot reach for
Cloudflare's SDK or a web framework. The check is one form-encoded POST, which
is exactly what the foundry kit exists to hold once — and the widget is already
created (site key `0x4AAAAAAFXu9FH01TH3LPSF`).

## Decision

### 1. `foundry.turnstile` — the canonical check, as a module

A stdlib core around `POST https://challenges.cloudflare.com/turnstile/v0/siteverify`,
built to the kit's contract: injected transport (default `urllib`), a frozen
`Verification`, and one `resolve_verifier()`. Full rationale in
`projects/foundry/decisions/0003`.

The policy is the canonical one and is **stricter than `success === true`**:
`success`, the expected `action`, and a `hostname` on the allowlist. A token
minted on someone else's page with our *public* site key is `success: true`;
the action and hostname checks are what reject it. An empty allowlist refuses.

### 2. The gate is a no-op when unconfigured

`resolve_verifier()` with no `TURNSTILE_SECRET_KEY` returns a **disabled**
verifier. `Demo.turnstile_enabled()` is `self.turnstile.enabled and
settings["turnstile_login"]`; when either half is off, `require_turnstile` does
nothing. So:

- local work, the test suite, and a deploy with no credentials keep working;
- a configured deploy gates both surfaces.

This mirrors the mail module exactly: **"unconfigured" is a normal state, not a
crash.** The alternative — always gate, refuse without a secret — would take the
whole site's login down on a missing env var.

### 3. Gate, don't replace

`Demo.require_turnstile(body, action, remote_ip)` runs at the route, before the
handler reads a credential, and raises `TurnstileError` → **HTTP 403**. The
existing `login_player` / `register_player` logic is untouched. `action` is
`"login"` or `"register"`, matching the widget's `data-action`.

### 4. The widget is explicit, and resets after every attempt

The account modal mounts after the page loads, so Turnstile's implicit scan
never sees the div. `web/app/components/TurnstileWidget.jsx` renders the widget
by hand, keeps its id, and resets it after every submit attempt — a token is
single-use, so a retry must mint a fresh one. The storefront renders it only
when `/api/config` says the rail is live (`turnstile_enabled` + a site key), so
the site key never appears on a deploy that is not gating.

### 5. Loopback is kept out of production by construction

`TURNSTILE_HOSTNAMES` is the production allowlist (`cadiback.onrender.com`);
`TURNSTILE_DEV_HOSTNAMES` is a separate key for local work. `render_deploy.py`
carries the first and **never** the second, so a production allowlist cannot
silently contain `localhost`.

## Alternatives considered

1. **A `demo/turnstile.py` one-off.** Fastest. Rejected: the request was
   explicitly to put it in foundry *as a template* as well; the check is the
   same shape for any host.
2. **Trust `success` alone.** Rejected: it accepts a token solved on any page
   that embeds the public site key.
3. **Gate by default even when unconfigured (fail closed).** Rejected: it takes
   login down on a missing env var, against the kit's "unconfigured is normal"
   rule. The gate arms itself the moment the secret and a hostname are present.
4. **Protect the admin painel login too.** Out of scope for this request (the
   owner asked for *user* login/session auth). The admin surface is
   staff-facing; adding an `admin_login` action later is a two-line change.
5. **`TURNSTILE_SITE_KEY` committed in the repo.** It is public, but it is kept
   in the gitignored `.env.turnstile` and served through `/api/config` so a
   deploy without the secret never ships a widget that cannot be verified.

## Notes

- Kit: 45 checks green (`projects/foundry/scripts/verify.py`). Operator:
  `demo` suite green (+6 Turnstile), `verify.py` 0.
- `turnstile_login` is a painel-flippable setting (default **on**), visible in
  `/api/config` and `/api/admin/settings`, exactly like `mail_welcome`.
- `/api/health` reports `turnstile: {provider, enabled, configured, site_key,
  hostnames, login_required}`. The secret is never surfaced.
- The Secret Key is not retrievable from this machine (no Wrangler, no
  Cloudflare API token), so it is stored through the project's own secret flow:
  `.env.turnstile` (gitignored), carried to Render by `render_deploy.py`.
- Runbook: `docs/turnstile.md`.
