# 0106 — X (Twitter) social login

Date: 2026-11-05. Status: **implemented; locally verified, not deployed** (provider callbacks to
register in the X portal; live sign-in pending).

Follows 0066 (Better Auth sidecar) and 0072 (direct social signup).
Requested X login; owner has an X Developer Basic account.

## Context

0066 left three providers: Google/Facebook/Apple. Better Auth already ships
a built-in `twitter` OAuth 2.0 provider (X's API v2), so no Python OAuth
code is needed — the sidecar/bridge/proxy shape from 0066 is unchanged.

X has three quirks worth recording, not smoothing over:

- **Confidential client.** A Web App confidential client gets a Client
  Secret; a public client (SPA/native) has none and cannot complete
  Better Auth's token exchange.
- **No email requested.** This integration uses identity/read scopes without
  email access. Same as Facebook/Apple, the template writes a
  reserved `.invalid` placeholder and links on the stable numeric user
  id — `provider:subject` stays the key.

## Decision

### Provider id `twitter`, label `X`
Better Auth's provider id is `twitter`, so the callback is
`.../api/betterauth/callback/twitter` and the bridge claims `provider:
"twitter"`. The storefront label is `X` (owner choice). `PROVIDER_LABELS`
in `demo/server.py`, `PROVIDERS` in `auth-server/auth.mjs` and the foundry
template all carry `{id:"twitter",label:"X"}`.

### Credentials `TWITTER_CLIENT_ID` / `TWITTER_CLIENT_SECRET`
Confidential-client OAuth 2.0 Client ID / Client Secret from the X portal,
read only by the Node sidecar (same rule as the other providers). Python
never sees them; `BETTER_AUTH_PROVIDERS` gains `twitter` and the deploy
script carries the two vars. With no credentials the button is hidden —
the rail stays config-gated.

### Minimum scopes
`scope: ["tweet.read","users.read","offline.access"]` — what X requires to
identify the user, and nothing beyond (no like/write/follow scope for a
login button). `mapProfileToUser("twitter")` captures the numeric id into
`providerSubject` and the placeholder email into `email`.

### Callbacks
Both production hosts plus local, exact match (X is strict, max 10):

- `https://cadiback.onrender.com/api/betterauth/callback/twitter`
- `https://cadiback-web.vercel.app/api/betterauth/callback/twitter`
- `http://127.0.0.1:8765/api/betterauth/callback/twitter` (X wants
  `127.0.0.1`, not `localhost`)

`GET /api/health` → `betterauth.callback_urls["twitter"]` prints the exact
strings.

### No wallet or bridge change
`social_login()` already accepts any `PROVIDER_LABELS` key; `oauth_links`
keys on `twitter:<subject>` with no migration. The bridge contract,
handoff and `ps1.…` session are untouched.

## Verification

- Node: `enabledProviders`/`providerList` offer `twitter`/`X` only when
  both values are present (`twitter.test.mjs`, plus existing
  `apple.test.mjs`); mixed env keeps Google + X order.
- Python: foundry config defaults now include `twitter`; operator
  `test_signup_cashier` covers `twitter` direct signup; `test_demo` covers
  withheld-email link-by-subject and the X callback URL.

## Limits

- **Callbacks must be registered in the X portal** — until they are, the
  flow fails with `Callback URL not approved` (code 415), not a code bug.
- **Rotate the Client Secret** if the leaked `xclientid.txt` copy is not
  deleted; it must never be committed (`.env.*` is already gitignored).

## Continuation 2026-11-06

- Corrected the API v2 mapping: Better Auth passes `{data:{id,...}}`, so
  the X mapper unwraps `data` before extracting the stable subject.
- Set `disableDefaultScope` so Better Auth does not add email access to
  the three configured scopes. A real provider regression checks the
  nested subject/placeholder, authorization scopes and S256 PKCE.
- Gates passed: core 50; backend/signup/deploy 442; auth Node 7;
  frontend Node 58; component renders 73; production export; structure
  verifier and Render preflight both zero problems.
- Deployment attempted with `python scripts/render_deploy.py --yes`,
  stopped before any remote mutation because no Render API key is available
  on this machine. X client credentials are present in ignored `.env.local`.
- Live consent and provider callback registration remain unverified.
