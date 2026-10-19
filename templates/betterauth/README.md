# Better Auth — social login that the host actually owns

`templates/betterauth/` is the TypeScript half of a small, self-hosted social
login. It is a **template**, not a package: copy the files into a Node/Next
host, install the three dependencies, and point it at a Python (or any)
backend with the signed bridge.

## Why a template instead of a Python module

Better Auth is TypeScript. A Python host cannot run it, and re-implementing
Google/Facebook/Apple OAuth by hand is exactly the fragile code this kit
exists to avoid. So the split is:

| Piece | Language | Owns |
|---|---|---|
| `auth.mjs`, `server.mjs`, `client.js` | TypeScript/Node | provider credentials, OAuth state/PKCE, the provider callback, the session cookie |
| `foundry.betterauth` (the Python module) | Python stdlib | the signed bridge verifier: HMAC over the exact body + a 120 s window |
| the host | its own | what a signed-in identity may do (create an account, demand a CPF, link a wallet) |

The two halves share **one secret** and **one JSON contract** — nothing else.
Provider credentials never reach the Python process.

## Files

| File | What it is |
|---|---|
| `auth.mjs` | `createAuth(env)`: stateless Better Auth, dynamic base URL, Google/Facebook/Apple, optional infrastructure dashboard |
| `server.mjs` | the Node HTTP adapter, `GET /providers`, `GET /health`, `GET /bridge` |
| `client.js` | a dependency-free `socialSignIn(provider)` helper |
| `env.example` | every key, with the console steps |
| `package.json` | the three dependencies (`better-auth`, `jose`, `@better-auth/infra`) |

## Setup

1. Copy this directory next to the host's web server (the operator uses
   `auth-server/`).
2. `npm ci` (or `npm install`) inside it.
3. Copy `env.example` to the host's gitignored `.env.betterauth` and fill the
   providers you want.
4. Register **every public host** with each provider, at the exact callback:
   - `https://<render-host>/api/betterauth/callback/google`
   - `https://<vercel-host>/api/betterauth/callback/google`
   - the same for `facebook` and `apple`
5. Run the server on a loopback port and have the host's web server proxy
   `/api/betterauth/*` to it. `basePath` is `/api/betterauth`; the proxy must
   preserve the browser's cookies and answer with every `Set-Cookie`.
6. Set `BETTER_AUTH_BRIDGE_URL` to the host's own origin (loopback is fine)
   and `BETTER_AUTH_BRIDGE_SECRET` to the same value the Python side reads.

The storefront button calls `socialSignIn("google")`; the bridge redirects
back to the page with `#social=<token>`, which the host exchanges for its own
session. The token never travels to the provider and never appears in a
query string.

## Stateless means: key on the provider subject

With no database Better Auth keeps the session and OAuth state in signed
cookies. It does **not** remember a user between sign-ins, so the host must
key its accounts on the provider's stable subject (`sub`/`id`), not on a
Better Auth user id. `mapProfileToUser` writes `providerSubject` and
`providerId` into the session's user object for exactly this reason.

Those fields are declared `input: true` because Better Auth ignores mapped
values for `input: false` fields. To keep them server-owned, `auth.mjs`
disables every client-writable user path (`/update-user`, `/sign-up/email`,
`/link-social`, …). Only the provider callback writes them. If you add one of
those paths back, move the provider subject behind a database hook instead.

## Provider notes

- **Google**: `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, web application.
- **Facebook**: `FACEBOOK_CLIENT_ID` / `FACEBOOK_CLIENT_SECRET`. Facebook may
  omit `email`; the template writes a reserved `.invalid` placeholder and
  links on the stable `id`.
- **Apple**: a Services ID, the Team ID, the Key ID, and the `.p8` private
  key. The client secret is a JWT signed at process start (180-day expiry,
  under Apple's six-month limit). Apple sends `email` only on the first
  consent; the stable `sub` is what links an account afterwards. Apple does
  not accept `localhost` or plain HTTP for return URLs.
- **Infrastructure dashboard** (optional): set `BETTER_AUTH_API_KEY`
  (`ba_…`). `@better-auth/infra` is loaded dynamically; a missing package or
  a bad key logs a warning and never breaks sign-in.

## Multi-host deployments

`baseURL` is an object with `allowedHosts`, so one instance can serve a Render
backend and a Vercel storefront. Each host's `/api/betterauth/*` must reach
this server (same-origin proxy or a server-side rewrite), and the request must
arrive with `X-Forwarded-Host` / `X-Forwarded-Proto` when a reverse proxy
changes the Host. `advanced.trustedProxyHeaders` is on for that reason.
Register each derived callback with the provider.

## The bridge contract

The Node server POSTs this JSON to
`<BETTER_AUTH_BRIDGE_URL>/api/auth/betterauth/session`:

```json
{"provider":"google","subject":"1234567890","email":"a@b.com",
 "email_verified":true,"name":"Ana","ts":1760000000}
```

with `x-betterauth-signature: sha256=<hex HMAC-SHA256 of the exact bytes>`.
The host verifies it with `foundry.betterauth.verify_bridge(body, header,
secret)` and answers `{"token": "<one-time token>"}` (or
`{"error": "..."}`). A missing secret, a bad signature, a body that is not
JSON, or a `ts` outside ±120 s is a refusal.

## Failure modes that are deliberate

- No provider credentials → `createAuth` returns null, `/providers` answers
  `[]`, the buttons disappear, and the rest of the site is unaffected.
- No `BETTER_AUTH_SECRET` in production → the same disabled state, not a
  crash.
- The Python backend unreachable → the bridge redirects with
  `#social_error=…`; the storefront shows the message.
- Apple/Facebook without an email → the reserved placeholder keeps Better
  Auth's user creation valid; the host still links on `subject`.
