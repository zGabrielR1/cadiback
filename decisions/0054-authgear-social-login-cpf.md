# 0054 — Google and Facebook login through Authgear, with a CPF step

Date: 2026-10-17
Status: accepted

## Context

Player onboarding is username/email/CPF + a salted SHA-256 password, and the
wallet id is derived from the CPF (`player-<slug(cpf)>`) — one wallet per
person. The repository already shipped an unused `.env.authgear`
(`AUTHGEAR_ENDPOINT`, `AUTHGEAR_CLIENT_ID`, `AUTHGEAR_REDIRECT_URI`) but no code
read it: there was no social login anywhere.

The ask was Google and Facebook sign-in **with CPF verification**. A social
provider returns an email and a stable subject, never a CPF, and a CPF is what
keys the wallet here — so a social sign-in cannot create an account by itself.
Authgear was chosen as the broker (one OIDC integration, both providers
configured in its portal) rather than two direct OAuth integrations.

## Decision

### 1. A foundry module: `oauth` (OIDC Authorization Code + PKCE)

`projects/foundry/foundry/oauth/` is a provider-agnostic OIDC client — the same
five steps every host rewrites, stated once: discovery, the authorize redirect,
the code exchange, the userinfo read, and the CSRF `state` that ties them
together. It follows the kit contract exactly: stdlib only, an injectable
transport defaulting to `urllib`, frozen values (`OAuthConfig`, `Provider`,
`Identity`), one `resolve_oauth(env=…)`, and a `DisabledOAuth` whose `enabled`
is False when unconfigured — the same "unconfigured is a normal state" rule the
mail and turnstile modules follow. Vendored into the operator with
`scripts/vendor.py --modules envfile,mail,turnstile,oauth`.

**The identity is read from the userinfo endpoint, not from a signed
`id_token`.** Verifying an RS256 JWT means RSA and a JWKS fetch — third-party
crypto the kit's stdlib-only rule forbids — and userinfo, reached with the
access token over TLS, carries the same `sub` and `email` from the same party.
The module trades an id_token verification for a round-trip and no crypto.

### 2. The operator wires it as a rail

`demo/server.py` gains `authgear_env()` (the `.env.authgear` file, environment
on top), `Demo.oauth` resolved at boot (injectable for tests), `oauth_status()`
for `/api/health` and `/api/config`, and four routes: `GET
/api/auth/oauth/start` (303 to the provider), `GET /api/auth/callback` (303 back
to the storefront), `POST /api/auth/oauth/session`, `POST
/api/auth/oauth/complete`. Unconfigured, `oauth_enabled()` is False and the
storefront hides the buttons — nothing else changes.

### 3. Linking is `provider:subject`, then email

A callback resolves the identity to a player by the `provider:subject` link
first (stable across a rename), then by email (an account the player already
made with a password). Either way the link is recorded in `oauth_links.json` and
the player is handed a one-time **handoff token**. A brand-new email is handed
the same token with `needs_profile: true`.

### 4. CPF is the wallet key, so a new social account must supply one

`oauth_complete_profile` requires a CPF that passes `validate_cpf` (check
digits) **and** is unique, plus a username and Pix key — the very rules
`register_player` already enforces — and only then writes the player row. The
verification is structural (check digits + uniqueness); a Receita Federal
ownership lookup needs a credential we do not have and is not claimed.

### 5. The handoff travels in the URL hash, not a query

The callback 303-redirects to `/#social=<token>`; a hash is never sent to the
server, so the one-time token stays out of request logs and referrers, and the
storefront clears it after exchanging it. Player identity stays the existing
`player_id` in `localStorage` — no new session cookie, no player bearer.

### 6. Secret delivery follows the house rule

`.env.authgear` is gitignored; `render.yaml` carries only `sync: false`
placeholders; `scripts/render_deploy.py` carries the endpoint, client id, secret
and provider list to Render. `docs/oauth.md` is the runbook, including the
Authgear-portal steps for enabling the Google and Facebook identities.

## Alternatives considered

1. **Direct Google + Facebook OAuth (no broker).** Rejected: two client
   secrets, two token endpoints, two userinfo shapes to keep in sync for no gain
   here — the broker is one integration and the providers are its concern.
2. **Verify the `id_token`.** Rejected: RS256 verification pulls RSA and JWKS
   handling into a stdlib-only kit for no additional trust over the userinfo
   read.
3. **Create the account from the provider's email alone.** Rejected: the wallet
   key is the CPF; an account without one cannot receive a payout, so the CPF
   step is mandatory, not a nicety.
4. **A new server-side session/cookie for players.** Deferred: the player
   session is `player_id` today; changing it is a separate decision (0049's
   session port), not this one.

## Notes

- Suites: frame 50/50, demo 300/300 (+10: `OAuthTest` x6, `OAuthHttpTest` x2,
  overround/tilt/overlay x3 minus the two rewritten in `SportsShowcaseTest`),
  foundry kit 57/57; `verify.py` 0; export rebuilt. Decision 0054.
- Files: `projects/foundry/foundry/oauth/*` (+ `vendor.py`, `verify.py`,
  `docs/MODULES.md`, `tests/test_oauth.py`), `operator/foundry/oauth/*`,
  `VENDOR.foundry.json`, `demo/server.py`, `.env.authgear`,
  `scripts/render_deploy.py`, `render.yaml`, `demo/test_demo.py`,
  `docs/oauth.md`, `web/lib/useSession.js`, `web/app/page.jsx`,
  `web/app/components/AccountModal.jsx`, `web/app/globals.css`.
- Deferred: an `oauth_links` Postgres table when the player store moves to
  Postgres (decision 0049 continues). `players` are still file-backed, so a
  table the app does not read would be dead weight today.
