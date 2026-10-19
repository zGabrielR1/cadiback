# Social login (Authgear) — runbook

Google and Facebook sign-in for players, brokered by **Authgear** (an OIDC
provider), with a mandatory **CPF** step for new social accounts. Nothing is
installed; the module is vendored at `foundry/oauth/` (see
`decisions/0054-authgear-social-login-cpf.md`).

The rail is **config-gated**: with no credentials the OAuth client reports
itself disabled and the storefront simply does not render the social buttons.
A deploy without credentials stays healthy and local work is unaffected.

## Credentials

| Variable | Secret? | Meaning |
|---|---|---|
| `AUTHGEAR_ENDPOINT` | no | your Authgear project endpoint, e.g. `https://<project>.authgear.cloud` |
| `AUTHGEAR_CLIENT_ID` | no | the *Traditional Web Application* client id |
| `AUTHGEAR_CLIENT_SECRET` | **yes** | that application's client secret |
| `AUTHGEAR_REDIRECT_URI` | no | optional; when unset the backend derives `https://<origin>/api/auth/callback` from the request |
| `AUTHGEAR_PROVIDERS` | no | which buttons to offer, e.g. `google,facebook` |

They live in the gitignored **`.env.authgear`** at the repository root. Never
commit the secret: `render.yaml` carries only `sync: false` placeholders, and
`scripts/render_deploy.py` carries the real values from `.env.authgear` (or the
environment) at deploy time.

```
AUTHGEAR_ENDPOINT=https://<project>.authgear.cloud
AUTHGEAR_CLIENT_ID=<client id>
AUTHGEAR_CLIENT_SECRET=<client secret>
AUTHGEAR_PROVIDERS=google,facebook
```

## How the rail behaves

- **No endpoint / client id / secret → disabled.** `/api/health` reports
  `oauth.enabled = false`, `/api/config` reports `oauth_enabled = false` with an
  empty provider list, and the storefront hides the buttons. `GET
  /api/auth/oauth/start` is refused with a 400.
- **Half a configuration is still disabled**, not "enabled but always refuses":
  a missing client secret means the code exchange would be rejected, so the rail
  stays off rather than offering a login that cannot complete.

## The flow

1. **Start** — `GET /api/auth/oauth/start?provider=google` mints a PKCE verifier,
   a CSRF `state`, stores them in memory (10-minute TTL), and 303-redirects to
   Authgear's authorize endpoint.
2. **Provider** — Authgear shows Google / Facebook (configured in its portal)
   and redirects back to `GET /api/auth/callback`.
3. **Callback** — the state is consumed (single-use), the code is exchanged, and
   the identity is read from the **userinfo** endpoint. Then:
   - a `provider:subject` link, or an existing account with the same email,
     logs the player straight in;
   - otherwise the backend 303-redirects to `/#social=<one-time token>`.
4. **Handoff** — the storefront reads the token from the URL **hash** (which
   never reaches the server), calls `POST /api/auth/oauth/session`, and either
   logs in or opens the **CPF completion** step.
5. **Complete** — `POST /api/auth/oauth/complete` carries the CPF (plus username
   and Pix key) and creates the wallet.

## CPF is the wallet key

A social sign-in does **not** create an account on its own. The completion step
requires a CPF that passes the check-digit validation **and** is unique — the
same rule the password signup enforces — because the wallet id is derived from
the CPF (`player-<slug(cpf)>`). One wallet per CPF, one per email, one per
username. This is a *structural* verification (check digits + uniqueness); a
Receita Federal ownership lookup is not used.

## Identity comes from userinfo, not a verified id_token

Verifying a signed `id_token` means RSA and a JWKS fetch — third-party crypto
the kit's stdlib-only rule forbids. The userinfo endpoint, reached with the
access token over TLS, carries the same `sub` and `email` from the same party,
so the module reads it there and does no JWT crypto.

## Setting it up in Authgear (the Google/Facebook half)

1. In the Authgear portal create a **Traditional Web Application**; copy its
   client id and secret.
2. Add **every** redirect URI it is allowed to return to. This is an exact
   string match, path included, no wildcards:
   - local: `http://127.0.0.1:8765/api/auth/callback`
   - the Render host: `https://cadiback.onrender.com/api/auth/callback`
   - the Vercel storefront (when it proxies `/api` to Render):
     `https://cadiback-web.vercel.app/api/auth/callback`
   A custom domain needs its own entry, `https://<your-domain>/api/auth/callback`.
3. Enable the **Google** and **Facebook** identities; each provider's own
   Google/Facebook client id and secret go there, not in this repository.
4. Put the endpoint, client id and secret into `.env.authgear`; deploy with
   `python scripts/render_deploy.py --yes`.

## Troubleshooting: "redirect URI is not allowed"

Authgear returns this **before** Google or Facebook is contacted, and the
browser sees `Invalid OAuth authorization request: error: invalid_request /
redirect URI is not allowed`. It is not a client-id or PKCE problem: the exact
callback the app sent is missing from the application's authorized list.

1. Ask the live deploy what it sends:
   `curl -s https://cadiback.onrender.com/api/health | jq .oauth.redirect_uri`
   (or the same on the storefront host). `/api/health` computes it from the
   request's public origin, so it shows the value for the host you called.
2. Paste that exact string into Authgear → Applications → your Traditional Web
   Application → **Authorized Redirect URIs**. Add both hosts if both are used;
   the callback keeps the browser on the host it started from, so the session
   lands on the right origin.
3. Retry the button. If a reverse proxy rewrites the host, either register the
   forwarded host or pin `AUTHGEAR_REDIRECT_URI` to the public callback.

The app cannot fix this from code: Authgear's application settings are the
allow-list, and changing them needs portal access (or its Management API key,
which is not part of the OAuth client credentials).


## What is stored

Social links live in `oauth_links.json` (one `provider:subject → player_id` map)
under `$OPERATOR_DATA_DIR`. In-flight `state`s and handoff tokens are in memory
only — a restart mid-flow just means "sign in again". When the player stores
move to Postgres (`decisions/0049` continues), an `oauth_links` table joins the
migration; today `players` are still file-backed, so a table the app does not
read would be dead weight.
