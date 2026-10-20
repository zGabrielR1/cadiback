# 0068 — Self-service password reset over email

Date: 2026-10-19. Status: **shipped and unit/HTTP-verified**; the live mail
rail can deliver it, but no real inbox has been used yet.

Follows 0047 (the Resend rail), 0054 (the hash-in-the-URL handoff), 0066
(password + social login). It closes the last ordinary account gap: a player
who forgot a password had no way back in except asking the operator for an
admin reset.

## The gap this closes

Player accounts have had email + password since the strict signup, and the
mail rail has been live since 0047. But there was no `forgot password`: the
only reset was `POST /api/admin/users/reset`, which needs an admin session and
a human. A player who lost the password was simply locked out. Adding a reset
is not a new mechanism so much as finishing the credential story the signup
already tells.

## Decision

### 1. Two surfaces, one purpose

- `POST /api/player/password/request` — `{identifier}` (the storefront sends
  the account email; the server also accepts username/CPF through the same
  `_find_player` used by login).
- `POST /api/player/password/reset` — `{token, password}`.

Both are ordinary same-origin writes. The request is gated by Turnstile when
the rail is configured, with its own `password_reset` action, so a bot cannot
use the form as a mail amplifier. The reset itself is not gated: possession of
a 32-byte token is the proof, and a second bot gate would only add friction.

### 2. The request answer is not a membership oracle

A known account with an email mints a link; an unknown identifier, an account
without an email, a request inside the cooldown, and an address over its
hourly budget all get the same body:

```json
{"requested": true}
```

after the same fixed 250 ms delay the login surface already pays. The
storefront says "if an account exists, we sent a link", which is true in every
branch. A mail outage is swallowed exactly like the welcome email: an account
is never confirmed or denied by whether the provider answered.

### 3. The token exists raw in two places, and neither is ours

`secrets.token_urlsafe(32)` is placed in the email link and in the browser's
URL hash:

```
https://<storefront>/#reset=<token>
```

A hash never reaches the server, request logs, or a referrer, the same reason
0054 used one for the social handoff. The server keeps only
`sha256(token)` in `data/password_resets.json`, so a copy of the data
directory cannot be turned into a working link. On boot the page strips the
hash from the address bar and holds the token only in component state.

The **base** of that link never comes from an untrusted request header.
`_our_origin()` is proxy-aware, which is right for game assets and callback
URLs but would let a caller-supplied `X-Forwarded-Host` choose where a
one-time token is sent. `public_site_url()` therefore prefers the configured
`PUBLIC_SITE_URL`, accepts only the known storefront hosts and loopback, and
falls back to `https://cadiback-web.vercel.app` otherwise. The deploy sets
`PUBLIC_SITE_URL`; the fallback keeps an older service from ever emitting an
attacker-chosen host.

### 4. One live link, single use, thirty minutes

- TTL: **30 minutes**.
- A new request invalidates every older link for the account.
- The token row is removed **before** the new password hash is written, so two
  races on one link cannot both succeed; the loser gets the ordinary "invalid
  or expired" message.
- Expired rows are pruned on every request.
- Cooldown: one mint per account per **60 seconds**; per-client budget:
  **5 per hour**. The client budget is in memory (a restart forgives it), which
  is honest for a single-process deployment but not a distributed limiter.

### 5. The UI is a mode, not a new screen

`AccountModal` gains `forgot` and `reset` modes:

- **forgot** — the email field, the Turnstile widget with action
  `password_reset`, and a neutral success line.
- **reset** — new password + confirmation, reached by opening the link; the
  login mode shows "Esqueci minha senha" only when the server says a mail rail
  can deliver it (`password_reset_enabled` in `/api/config`). With no Resend
  key the console mailer is a development aid, not a player surface, so the
  link is hidden rather than promising an email that will never arrive.

The server still validates the password policy it always did
(`validate_player_password`), removes a legacy `pw_salt`, and returns only
`{reset: true, username}`. It never returns the new hash or logs the token.

## What ships

- `demo/server.py`: `request_password_reset`, `_send_password_reset`,
  `reset_player_password`, `public_site_url`, the two routes, the reset
  store/lock, the `password_reset_enabled` public flag, and the constants
  above.
- `render.yaml` / `scripts/render_deploy.py`: `PUBLIC_SITE_URL`, the canonical
  storefront origin a reset link may use.
- `demo/test_demo.py`: `PasswordResetTest` (6), `PasswordResetHttpTest` (2),
  and the host-poisoning check in `SameOriginTest`.
- `web/app/components/AccountModal.jsx`: forgot/reset modes and the login link.
- `web/app/page.jsx`: `#reset=<token>` boot handling and the two submits.
- `web/app/globals.css`: the success line style.
- `docs/mail.md`: the second trigger on the rail.

## Verification

`PasswordResetTest` proves the request is the same answer for known, unknown
and cooling-down accounts; the raw token is absent from disk while its digest
is present; the reset changes the password, rejects the old one and cannot be
replayed; a newer request kills the older link; expired and unknown links are
refused and expired rows are pruned; a mail failure still returns the neutral
answer and leaves the link available to a retry; and `/api/config` hides the
surface when the rail is disabled.

`PasswordResetHttpTest` proves the route wiring: a missing Turnstile token is
a 403 with the anti-bot message, a valid one answers `{"requested": true}`
even for an account that does not exist, and an unknown reset link is a 400.
`SameOriginTest` adds the poisoning guard: an arbitrary forwarded host falls
back to the canonical storefront, while the real storefront, the Render host
and loopback are accepted, and `PUBLIC_SITE_URL` wins over all of them.

## Alternatives considered

1. **A short numeric code in the email.** Easier to type, but a 6-digit code is
   a brute-force surface and needs attempt counters; a 32-byte token in a
   one-click link is both stronger and less UI.
2. **A signed stateless token (HMAC with the server secret).** No store, but
   "single use" and "new request invalidates the old one" become impossible
   without a store anyway. The store is one JSON file.
3. **Reveal whether the account exists.** Better UX ("email not found"), but
   it turns the public form into an account enumerator. Rejected.
4. **Reset by CPF only.** The CPF is public-ish and is the wallet key; it is a
   login identifier, not a recovery secret. Rejected.
5. **Turn the reset link into a session.** Tempting, but player sessions are
   still the `player_id` the storefront keeps (see Limits); a reset link that
   also logs in would widen that surface, not narrow it.

## Limits

- **The player surface is still id-based.** `/api/player?id=` and the other
  player actions do not require a bearer session; this decision changes the
  password credential, not the session model. Moving players onto signed
  sessions is a separate, larger change (and would give a password change
  something real to revoke).
- **No server-side player sessions to revoke.** An admin password reset has
  the same property today. The password is the only player credential.
- **In-memory client budget.** A process restart forgives the hourly count; the
  per-account cooldown is persisted with the token row.
- **Deliverability is the provider's job.** Reserved addresses are refused by
  the foundry mail module, and a real player needs a real inbox. The live
  smoke test used the existing Resend rail only for health, not a real reset.
- **A stolen inbox can reset the account.** That is the standard trust model
  for email reset; the 30-minute, single-use link limits the window.
