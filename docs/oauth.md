# Social login (Better Auth) — runbook

Google, Facebook and Apple sign-in for players, with a mandatory **CPF** step
for new social accounts. Better Auth (a TypeScript library we run ourselves)
owns the OAuth dance; the Python backend owns the wallet. Nothing is sent to
a hosted identity broker, and the provider secrets never leave the Node
process.

The rail is **config-gated**: with no provider credentials the auth server
reports itself disabled and the storefront does not render the buttons. A
deploy without credentials stays healthy, and local work is unaffected.

## Shape

```
browser ── /api/betterauth/* ──▶ Python (public listener)
                                   │ same-origin proxy
                                   ▼
                              Node auth server (loopback:3100)
                                   │ Better Auth callback
                                   │ POST signed identity
                                   ▼
                              Python /api/auth/betterauth/session
                                   │ one-time handoff token
                                   ▼
                              /#social=<token> → player session / CPF step
```

- The **Node sidecar** (`auth-server/`) holds the provider credentials and the
  OAuth state. It is stateless: no database, sessions and state live in signed
  cookies.
- The **Python server** proxies `/api/betterauth/*` to it, preserving the
  public Host and every `Set-Cookie`, so cookies and callback URLs stay on the
  host the browser is actually on.
- The **bridge** is the only trust boundary: the Node process signs the
  identity (`provider`, `subject`, `email`, `name`, `ts`) with
  `BETTER_AUTH_BRIDGE_SECRET`, and Python verifies it with the same secret
  (`foundry.betterauth.verify_bridge`: constant-time HMAC over the exact bytes
  plus a 120 s window).

## Credentials

All of them live in the gitignored **`.env.betterauth`** at the repository
root. `scripts/render_deploy.py` carries them to Render, merging them over the
service's existing environment so dashboard-only keys survive; never commit
them.

| Variable | Secret? | Meaning |
|---|---|---|
| `BETTER_AUTH_URL` | no | public origin, e.g. `https://cadiback.onrender.com` |
| `BETTER_AUTH_SECRET` | **yes** | ≥ 32 high-entropy chars (session/state encryption) |
| `BETTER_AUTH_BRIDGE_SECRET` | **yes** | shared with the Python verifier |
| `BETTER_AUTH_TRUSTED_ORIGINS` | no | comma-separated origins allowed to finish a flow and receive the browser |
| `BETTER_AUTH_PROVIDERS` | no | the list the backend reports before the sidecar is reachable |
| `BETTER_AUTH_API_KEY` | **yes** | optional `ba_…` key for the Better Auth infrastructure dashboard |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | secret | Google OAuth web client |
| `FACEBOOK_CLIENT_ID` / `FACEBOOK_CLIENT_SECRET` | secret | Facebook app id / secret |
| `APPLE_CLIENT_ID` | no | Apple **Services ID** |
| `APPLE_TEAM_ID` / `APPLE_KEY_ID` | no | Apple developer team and key identifiers |
| `APPLE_PRIVATE_KEY` | **yes** | the `.p8` contents, newlines as `\n` |
| `APPLE_APP_BUNDLE_IDENTIFIER` | no | optional, only for native iOS ID-token sign-in |

A provider with incomplete credentials is simply not offered. An unconfigured
rail is a normal state, not an error.

## Register the callbacks

Register **every** public host with each provider, exactly:

- `https://cadiback.onrender.com/api/betterauth/callback/google`
- `https://cadiback-web.vercel.app/api/betterauth/callback/google`
- the same for `facebook` and `apple`
- local (Google/Facebook only): `http://127.0.0.1:8765/api/betterauth/callback/google`

`GET /api/health` reports `betterauth.callback_urls` computed from the host you
called, so there is no guessing. A mismatch is a provider-side
`redirect_uri_mismatch`, not a code defect.

### Google

1. Google Cloud Console → APIs & Services → Credentials → **Create
   credentials** → OAuth client ID → **Web application**.
2. Add the authorized redirect URIs above.
3. Put the client id and secret in `.env.betterauth`.

### Facebook

1. developers.facebook.com → your app → Settings → Basic: copy **App ID**
   (`FACEBOOK_CLIENT_ID`) and **App Secret** (`FACEBOOK_CLIENT_SECRET`).
2. Add the redirect URIs under Facebook Login → Settings → Valid OAuth
   Redirect URIs.
3. Facebook may omit the email even with the permission granted; the template
   writes a reserved `.invalid` placeholder and links on the stable account id.

### Apple

Apple requires a paid developer account and HTTPS — it does **not** accept
`localhost` or plain HTTP return URLs.

1. Create an **App ID** with the *Sign in with Apple* capability.
2. Create a **Service ID**; that identifier is `APPLE_CLIENT_ID`.
3. Configure the Service ID: primary App ID, domains, and return URLs
   (`https://<host>/api/betterauth/callback/apple`).
4. Create a **Key** with *Sign in with Apple*; download the `.p8` once, note
   its Key ID and your Team ID.
5. Put the three values and the `.p8` contents (`\n` escaped) in
   `.env.betterauth`. The client secret JWT is generated at process start with
   a 180-day expiry (Apple's limit is six months).

Apple sends the email only on the first consent. The stable `sub` is what
links the wallet afterwards.

## How the flow behaves

1. The storefront posts `/api/betterauth/sign-in/social` with the provider and
   `callbackURL=/api/betterauth/bridge?return=<origin>`. The auth server
   answers with the provider URL and sets the OAuth state cookie.
2. The provider sends the browser to `/api/betterauth/callback/<provider>`.
   Better Auth exchanges the code and sets its session.
3. It redirects to the bridge. The bridge reads the session, signs the
   identity, and POSTs it to the Python host.
4. Python verifies the claim, then:
   - a `provider:subject` link, or an existing account with the same email,
     logs the player straight in;
   - otherwise it returns a one-time handoff and the storefront opens the
     **CPF completion** step.
5. The browser lands on `/<#social=<token>>`; the storefront exchanges it at
   `POST /api/auth/oauth/session` and either logs in or shows the CPF step.

## CPF is the wallet key

A social sign-in does **not** create an account on its own. The completion
step requires a CPF that passes the check-digit validation **and** is unique —
the same rule the password signup enforces — because the wallet id is derived
from the CPF. One wallet per CPF, one per email, one per username.

## Stateless means: the provider subject is the link

With no database, Better Auth does not remember a user between sign-ins. The
bridge therefore keys the wallet on `provider:subject`, not on a Better Auth
user id. `mapProfileToUser` captures the provider's stable id into
`providerSubject`/`providerId`; every client-writable user path is disabled so
a browser cannot change them. If you add one of those paths back, move the
subject behind a database hook first.

## Local development

```bash
# terminal 1 — the auth server (fake or real credentials)
cd auth-server
npm ci            # once
npm test          # Apple's client-secret JWT, with a throwaway key
node server.mjs   # reads the process env; BETTER_AUTH_URL for local

# terminal 2 — the operator
python -m demo.server
```

Set `BETTER_AUTH_URL=http://127.0.0.1:8765`,
`BETTER_AUTH_TRUSTED_ORIGINS=http://127.0.0.1:8765`,
`BETTER_AUTH_INTERNAL_URL=http://127.0.0.1:3100` and
`NODE_ENV=development` (so Better Auth does not mark its cookies `Secure` on
plain HTTP). Without the sidecar, `/api/betterauth/providers` fails cleanly
and the buttons stay hidden.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `redirect_uri_mismatch` | the exact callback is not registered for that host. Ask `/api/health` for `betterauth.callback_urls` and paste it. |
| `state_mismatch` | the browser lost the state cookie: the flow crossed hosts, or `BETTER_AUTH_TRUSTED_ORIGINS` is missing the origin. Add it and retry. |
| Buttons missing | `/api/betterauth/providers` returned `enabled:false`. Check the sidecar log: no credentials, no `BETTER_AUTH_SECRET`, or the process is not running. |
| `502 servidor de autenticação indisponível` | the Python server cannot reach `BETTER_AUTH_INTERNAL_URL:3100`; start the sidecar. |
| `#social_error=sessão social não encontrada` | the bridge ran without a Better Auth session cookie; usually a callback URL host mismatch. |
| Apple login works once, then asks for the CPF again | the provider subject was not captured. Check that `mapProfileToUser` and `providerSubject` are intact and the user paths stay disabled. |
| `#social_error=...` on a brand-new account | expected until the CPF step is completed. |

## What is stored

Better Auth is stateless: no user, session or account table is written. The
Python host stores only `oauth_links.json` (`provider:subject → player_id`)
under `$OPERATOR_DATA_DIR`, and in-flight handoff tokens in memory. Provider
access/refresh tokens stay in the encrypted account cookie (or nowhere, after
the bridge), never in the wallet database.

## Migrating from Authgear

The old `.env.authgear` is no longer read and the old `/api/auth/callback`
route is gone. `GET /api/auth/oauth/start` survives only as a compatibility
shim for a storefront bundle built before 0066: it starts the same Better Auth
flow and redirects to the provider, so an un-redeployed front end still works.
`foundry.oauth` remains in the kit as a generic OIDC module, but the operator
no longer vendors it. Remove the old Authgear client once the new callbacks
are registered; the two flows must not share a host at the same time.
