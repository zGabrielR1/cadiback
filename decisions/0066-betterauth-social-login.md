# 0066 — Better Auth replaces the Authgear broker

Date: 2026-10-19. Status: **shipped; local end-to-end verified** (provider
credentials pending from the owner).

Follows 0054 (Authgear social login + CPF), 0049 (Supabase/Vercel) and the
PG Soft bridge work in 0065.

## Context

0054 put social login behind Authgear, a hosted OIDC broker. It worked, but
the owner did not want the dependency: a hosted identity portal to configure,
a client secret to rotate, an "authorized redirect URIs" list to keep in
sync, and a login UX that is somebody else's page. Better Auth is the
alternative: a TypeScript library the project runs itself, with first-class
Google/Facebook/Apple providers and no hosted identity service.

Better Auth is not a Python library. The operator is a stdlib-only Python
container. The integration therefore has to answer three questions: where
Better Auth runs, how it stays stateless (the free Render instance has no
persistent disk), and how a verified social identity reaches the wallet.

## Decision

### One self-hosted Node process, proxied same-origin

`auth-server/` is a small Node process started beside the Python server in
the same container. It owns the provider credentials, the OAuth state and the
session cookie. The Python server — the only public listener — proxies
`/api/betterauth/*` to `127.0.0.1:3100`, preserving:

- the public host as `X-Forwarded-Host`, so Better Auth's **dynamic baseURL**
  derives the right callback per host (Render and Vercel can share one
  instance);
- **every** `Set-Cookie` header (a dict collapses them and breaks OAuth);
- `Origin`, so Better Auth's own CSRF check runs against the real browser.

On Vercel, the existing `/api/:path*` rewrite already carries
`/api/betterauth/*` to Render, so both front doors use the same auth server
and the same callbacks.

### Stateless, keyed on the provider subject

Better Auth runs with **no database**. Sessions and OAuth state are signed
cookies; a free Render instance that resets its disk still logs people in.
The trade-off is that Better Auth does not remember a user between sign-ins,
so the wallet link cannot key on a Better Auth id. `mapProfileToUser` captures
the provider's stable subject into `providerSubject`/`providerId` (custom user
fields). Those fields are `input: true` because Better Auth ignores mapped
values for `input: false` fields, so every client-writable user path is
`disabledPaths` — only the provider callback can write them.

Apple/Facebook email gaps are handled with reserved `.invalid` placeholders;
the subject still links the wallet.

### The bridge is the trust boundary

After the provider callback, the bridge reads the Better Auth session and
POSTs the identity to the Python host with an HMAC-SHA256 signature over the
exact JSON bytes:

```json
{"provider":"google","subject":"…","email":"…",
 "email_verified":true,"name":"…","ts":1760000000}
```

The Python side (`foundry.betterauth.verify_bridge`) compares in constant time
and rejects a claim older or newer than 120 s. Then the existing linking logic
runs: `provider:subject` → email → CPF completion. The provider credentials
never reach Python, and Python never has to understand OAuth.

### The kit gets both halves

`foundry/betterauth/` is the Python verifier (stdlib-only), and
`templates/betterauth/` is the reusable TypeScript server (Better Auth config,
Node adapter, provider list, bridge, client helper, env example, runbook).
`vendor.py` copies both; the operator's `auth-server/` is the first host copy.

## Verification

- Foundry: 91 checks green, including the bridge's refusal paths (tampered
  body, wrong secret, expired/future timestamp, malformed payload).
- Operator: `BetterAuthTest` + `BetterAuthHttpTest` (8 checks) cover the
  unconfigured no-op, provider reporting, a signed claim for a known email, a
  new identity's CPF completion, forgot/stale claims, and the proxy's
  multi-`Set-Cookie` forwarding.
- The full local path was exercised with fake Google/Facebook credentials:
  `/api/betterauth/providers` → enabled; `/sign-in/social` → 200 with the OAuth
  state cookie and a callback derived from the public host; a signed claim →
  CPF step → wallet created; a second claim → straight in.
- Suites: `frame` 50/50, `demo` (see PROGRESS), `verify.py` 0, frontend build.

## Limits (recorded, not hidden)

- **Provider credentials are owner-supplied.** The Authgear broker kept the
  Google/Facebook client ids inside its portal; they are not exportable from
  this machine, and Apple needs a paid developer account. The rail is
  config-gated until the keys are pasted into `.env.betterauth`.
- **Stateless sessions cannot be revoked server-side** beyond rotating
  `BETTER_AUTH_SECRET` (which logs everyone out). Acceptable for a hobby
  deploy; a database would fix it.
- **The sidecar is a second process.** If it fails to start the site stays
  up and the buttons disappear; the container's CMD starts it best-effort.
- **`NODE_ENV=production` marks cookies `Secure`.** Local HTTP runs must set
  `NODE_ENV=development`, otherwise the browser drops the state cookie.
- **The infrastructure dashboard (`BETTER_AUTH_API_KEY`) is optional.** The
  `dash()` plugin is loaded dynamically; a missing package or bad key logs a
  warning and never blocks sign-in.

## Alternatives rejected

- **Keep Authgear.** The owner's objection is the product, not a bug.
- **Run the Next server on Render for its API routes.** The storefront is a
  static export by design; a whole Next runtime for one auth route is more
  moving parts than a loopback sidecar.
- **A database-backed Better Auth.** The free Render plan has no persistent
  disk, and the wallet is still file-backed; a requirement for Postgres would
  make social login fail exactly where the rest of the app works.
- **Re-implement Google/Facebook/Apple OIDC in Python.** Apple's client-secret
  JWT, Facebook's email gaps and the three provider quirks are exactly the
  code Better Auth already maintains.
- **Serve Better Auth from Vercel only.** The Render origin is the primary
  live site; a second-host dependency would make social login vanish when
  Vercel is not the front door.
