# Player sessions

How a player's account is proven on every request (decision `0069`). Replaces
the old `{"player": "player-…"}` body field and `GET /api/player?id=`: the id
is derived from the CPF, so it was never a credential.

## The shape

```
X-Player-Token: ps1.<base64url(payload)>.<base64url(hmac-sha256)>
```

The payload carries the player id, the row's `session_epoch`, the issue and
expiry instants, and whether "lembrar de mim" was chosen.

- **12 h** ordinary login; **30 d** when the form sends `remember: true`.
- Signed with HMAC-SHA256 over a fixed context prefix, compared in constant
  time.
- Stateless: no session table, no per-request write. A restart does not log
  players out (the token is its own proof until `exp`).

## Where it is required

| Required | Optional |
|----------|----------|
| `POST /api/deposit`, `/api/deposit/pix`, `/api/deposit/pix/status`, `/api/deposit/crypto`, `/api/deposit/crypto/status` | `POST /api/play` (opening a game is presentation activity; a session, when present, still decides the player) |
| `POST /api/withdraw`, `/api/spin`, `/api/bet`, `/api/bonus` | |
| `POST /api/crash/start`, `/api/crash/status`, `/api/crash/cashout` | |
| `POST /api/wallet/launch` | |
| `POST /api/self-exclude`, `/api/self-exclude-lift` | |
| `GET /api/player`, `GET /api/history` | |

A missing, forged, expired or revoked token is **401** with
`sessão do jogador inválida ou expirada` — the same message for every refusal.
The body's `player` field is overwritten from the token, never merged. The
`?id=` / `?player=` query strings are ignored.

The token header is deliberately not `Authorization`: the painel's bearer
session uses that, and the owner can be logged into both surfaces at once.

## Revocation

`session_epoch` lives on the player row (0 for accounts created before 0069).
A token names the epoch it was minted under; when the row's value differs, the
token is refused.

The epoch is bumped by:

- `POST /api/player/password/reset` (the self-service link, decision `0068`);
- the operator's test-account password reset;
- a legacy `upsert_player` that writes a new password.

Deleting the row invalidates every token for it immediately. Disabling test
accounts in the painel does the same at the next request.

Revocation is all-or-nothing: a reset logs every device out. Per-device logout
would need a session table.

## The signing key

Resolution order, in `demo/player_session.py:resolve_secret`:

1. `PLAYER_SESSION_SECRET` — the proper production value.
2. A **derived** key from `BETTER_AUTH_SECRET` (already carried to Render for
   `0066`): `HMAC-SHA256(BETTER_AUTH_SECRET, "operator.player-session.derive.v1")`.
   Domain-separated, so a player token and a Better Auth cookie can never be
   confused. This is why the rail works on the live service with no new owner
   step.
3. `data/player_session.key`, generated once on a local run with neither.

To pin an explicit key, add the line to the gitignored `.env.betterauth` (the
deploy carries that file) or set it in the Render dashboard, then deploy:

```
PLAYER_SESSION_SECRET=<48+ random chars>
```

On an ephemeral host, step 3 means a new key per boot and players log in again;
steps 1–2 are stable. The live deploy has `BETTER_AUTH_SECRET`, so it is stable
today.

Rotating the key logs **every** player out — that is the intended effect of a
compromise. There is no dual-key window.

## The storefront

`web/lib/api.js` keeps `{player_id, token}` in `localStorage` ("lembrar de mim")
or `sessionStorage` (not remembered), sends the header on every `api()` call,
and drops a stored entry that has no token (a pre-0069 leftover) on boot. The
boot refresh calls `GET /api/player` with no id; a rejected token clears the
session.

The `player` prop still travels to panels and into bodies for convenience. The
server ignores it — the token decides.

## Smoke checks

```bash
# no token: 401
curl -s -o - -w '\n%{http_code}\n' http://127.0.0.1:8765/api/player

# login returns player_token; the same call with the header answers the profile
TOKEN=$(curl -s -X POST http://127.0.0.1:8765/api/player/login \
  -H 'Content-Type: application/json' \
  -d '{"identifier":"ana.souza","password":"ana1234"}' | python -c 'import json,sys;print(json.load(sys.stdin)["player_token"])')
curl -s http://127.0.0.1:8765/api/player -H "X-Player-Token: $TOKEN"
```

After a password reset, the second call must answer 401.

## Tests

`demo.test_demo.PlayerSessionTest` (8) and `PlayerSessionHttpTest` (4):
minting at every door, both lifetimes, tampered/foreign/expired tokens, reset
and operator-reset revocation, deleted rows, derived key, 401 without a token,
token-beats-body on a deposit, `?id=` ignored, and crash-round ownership.
