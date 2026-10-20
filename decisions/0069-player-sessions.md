# 0069 — Signed player sessions

Date: 2026-10-20. Status: **shipped and unit/HTTP-verified**; deployed with the
next push. Follows 0068 (password reset) and closes the limit that decision
recorded: the player surface was keyed on `player_id`, so there were no player
sessions to revoke.

## The gap this closes

Every player write carried the account id in its body — `{"player":
"player-…", "stake_minor": 200}` — and `/api/player?id=` read a profile. The
password protected the login form; it protected nothing after it. Two facts
made that worse than a demo convenience:

1. `player_id` is **derived from the CPF** (`player-` + a hash of the CPF), and
   a CPF is a semi-public document in Brazil. Anyone who knows a person's CPF
   knows their wallet key.
2. The checks that existed compared a player to *itself* (`exclusions`,
   balance lookups, the bonus ledger). None asked whether the caller was that
   player.

So a request could read another person's profile and history, spend their
balance on bets and spins, claim their bonuses, or open and settle rounds on
their wallet. `casino` rounds are ours, not a publisher's, so the money moved
for real inside the demo ledger.

## Decision

### 1. The token is the credential

`demo/player_session.py` mints a compact, signed token:

```
ps1.<base64url(payload)>.<base64url(hmac-sha256(context + "ps1." + payload))>
```

The payload is `{p: player_id, e: session_epoch, iat, exp, r}`. The signature
is HMAC-SHA256 over a fixed context prefix, so a secret shared with another
signer cannot mint a player session and an edited payload is refused before it
is read. Verification is constant-time; the clock and the secret are
injectable, so the tests neither sleep nor read this machine's credentials.

Stateless is a deliberate trade, the same one the Better Auth bridge makes
(0066): no session table to port, no per-request disk write, and a restart does
not log every player out.

### 2. Two lifetimes, both absolute

- **12 hours** for an ordinary login.
- **30 days** when the form sends `remember: true` ("Lembrar de mim").

The server decides the expiry; the browser's `localStorage`/`sessionStorage`
choice only decides whether the token survives a tab close. A token is valid
until its `exp`, not until the browser forgets it.

### 3. Every door mints, every route derives

`register_player`, `login_player`, `oauth_session` (social existing account)
and the social CPF completion all return `player_token` and
`player_token_expires_at` beside the profile.

On the HTTP side a single helper resolves it and **overwrites** the body's
`player` field:

```python
body = self._body()
body["player"] = DEMO.player_from_token(self._player_token())
```

The token travels in `X-Player-Token`, a header of its own rather than
`Authorization`: the owner can be logged into the painel and the storefront in
the same browser, and the two credentials must never shadow each other.

- **Required** on: deposit (instant/Pix/crypto), Pix/crypto status polls,
  withdraw, spin, crash start/status/cashout, wallet launch, bet, bonus,
  self-exclude and its lift, `GET /api/player`, `GET /api/history`.
- **Optional** on `POST /api/play` (opening a game is presentation activity and
  may be anonymous; a session that rides along still decides the player).
- **Untouched**: catalog, sports, config, health, auth/login/register/password
  reset, webhooks, and the game proxy's own wallet token.

`GET /api/player?id=` and `GET /api/history?player=` are gone. The query string
is ignored rather than honoured, so an old bundle cannot keep reading a wallet
while pointing at somebody else.

A crash round was already keyed on a random handle, but the handle travelled in
the body and any player could poll or cash out a round they did not open. Both
now compare the round's `player` to the session, and a stranger's handle reads
as `{"status": "unknown"}` — never "forbidden", because that would confirm the
round exists.

### 4. Revocation is one integer

The player row carries `session_epoch` (0 for every existing account, set at
signup from now on). Every token names the epoch it was minted under; a token
whose epoch differs from the row's no longer verifies.

The epoch is bumped by exactly the events that must invalidate a credential:
the self-service reset (0068), the operator's test-account reset, and a legacy
`upsert_player` that writes a new password. This is the "something real to
revoke" that 0068 could not offer. A deleted player fails the row lookup; a
test account disabled from the painel stops working at its next request.

### 5. The signing key needs no owner step

`PLAYER_SESSION_SECRET` is the proper value. When it is absent the already
deployed `BETTER_AUTH_SECRET` is **derived** into a player-only key
(HMAC-SHA256 with a fixed context), so this change works on the live service
today and a token minted here can never be accepted as a Better Auth cookie.
A local run with neither writes `data/player_session.key` once, so a restart
keeps its sessions. That file is the last resort, not the recommendation: on an
ephemeral host it changes per boot and players log in again.

### 6. The storefront carries it and drops the old shape

`web/lib/api.js` stores `{player_id, token}` and sends `X-Player-Token` on
every `api()` call. A stored entry without a token is a pre-0069 leftover: it
is dropped on boot, so the player logs in once and continues. `useSession` and
the boot effects stopped composing `?id=` URLs.

The `player` prop is still passed to panels and still travels in bodies as a
convenience — the server ignores it. Removing it everywhere would be a larger
UI change with no security value; the field is now documentation, not authority.

## What ships

- `demo/player_session.py`: the signer, the derived-key rule, the key-file
  fallback, `PlayerSessionError`.
- `demo/server.py`: `session_env`, `Demo.player_sessions`, `session_epoch`,
  `issue_player_token`, `player_from_token`, the epoch bumps, the token on
  every door, `Handler._player_id` / `_player_body` / `_optional_player`, and
  the crash-owner check.
- `web/lib/api.js`, `web/lib/useSession.js`, `web/app/page.jsx`: the header, the
  `{player_id, token}` session, the boot refresh without ids, `remember`.
- `demo/test_demo.py`: `PlayerSessionTest` (8) and `PlayerSessionHttpTest` (4).

## Verification

`PlayerSessionTest` proves every door mints a token the server accepts; the
two lifetimes are 12 h and 30 d; an edited payload, a foreign key, an empty
string and a non-token are all refused; expiry is absolute with an injected
clock; a password reset kills the old token and a fresh login works, with the
epoch at 1; an operator test-account reset revokes too; a deleted row cannot
keep using a token; and the derived key is stable, 64 hex chars and different
from its source.

`PlayerSessionHttpTest` proves the route wiring end to end: `/api/player` and
`/api/history` answer 401 without a token (even with `?id=` naming a real
player); a deposit sent with Ana's token but Bia's id credits Ana and leaves
Bia untouched; the profile route returns the token's player; and a crash round
opened by Ana reads as unknown and refuses cash-out for Bia while Ana can still
settle it.

Suites: `frame` 50/50 · `demo` 411/411 · `verify.py` 0.

## Alternatives considered

1. **An opaque session table (like the admins' `SessionBook`).** Per-device
   logout and a "sessions" screen become possible, but the table must be
   ported to Postgres (0049), survives only on a persistent disk, and a
   per-request read is the cost. The epoch already covers the case that
   matters — a password change — and a stateless token cannot drift from its
   store.
2. **A cookie instead of a header.** Automatic on every same-site request, but
   the Vercel proxy and the game iframes already share this origin; a cookie
   widens CSRF surface, and the storefront's own writes are the only place
   this credential is needed. The explicit header is the narrower shape.
3. **Sign into `Authorization: Bearer`.** One header fewer, but it collides
   with the painel's bearer token in a browser that is logged into both.
4. **Keep `?id=` and add a check server-side.** The check is exactly what was
   missing; the id in the URL is the problem, so the URL went away.
5. **Client-generated device ids.** Unverifiable by construction.

## Limits

- **All-or-nothing revocation.** A password reset kills every device, not one.
  That is the honest consequence of a stateless token; per-device revocation
  needs a store.
- **A stolen token is a session until `exp`.** Same trust model as any bearer
  credential. The 12 h default bounds it; TLS and the same-origin write guard
  are the transport protections.
- **`player` still rides in request bodies.** It is ignored, not removed; the
  UI still uses it as a prop. A future cleanup can drop the field entirely.
- **The key file is per-disk.** Without `PLAYER_SESSION_SECRET` or
  `BETTER_AUTH_SECRET`, an ephemeral host logs players out on every restart.
  The deploy has the latter, so the live service is unaffected.
- **The wallet token is a separate rail.** The game bridge talks to us with the
  per-launch wallet token (server-minted, embedded in the URL), not the player
  session; that boundary is unchanged.
