# Player sessions

How a player's account is proven on every request (decisions `0069`, `0070`).
Replaces the old `{"player": "player-…"}` body field and
`GET /api/player?id=`: the id is derived from the CPF, so it was never a
credential.

## The shape

```
X-Player-Token: ps1.<base64url(payload)>.<base64url(hmac-sha256)>
```

The payload carries the player id, the row's `session_epoch`, a session id,
the issue and expiry instants, and whether "lembrar de mim" was chosen. The
session id names a row in the live-session list (`data/player_sessions.json`),
which is what makes "sair deste dispositivo" real (decision `0070`).

- **12 h** ordinary login; **30 d** when the form sends `remember: true`.
- Signed with HMAC-SHA256 over a fixed context prefix, compared in constant
  time.
- Stateless signing: no per-request write. The live-session row is read on the
  same pass as the player row and touched at most once per 10 minutes.

## Where it is required

| Required | Optional |
|----------|----------|
| `POST /api/deposit`, `/api/deposit/pix`, `/api/deposit/pix/status`, `/api/deposit/crypto`, `/api/deposit/crypto/status` | `POST /api/play` (opening a game is presentation activity; a session, when present, still decides the player) |
| `POST /api/withdraw`, `/api/spin`, `/api/bet`, `/api/bonus` | |
| `POST /api/crash/start`, `/api/crash/status`, `/api/crash/cashout` | |
| `POST /api/wallet/launch` | |
| `POST /api/self-exclude`, `/api/self-exclude-lift` | |
| `GET /api/player`, `GET /api/history` | |
| `GET /api/player/sessions`, `POST /api/player/logout`, `POST /api/player/sessions/revoke`, `POST /api/player/sessions/revoke-others` | |

A missing, forged, expired or revoked token is **401** with
`sessão do jogador inválida ou expirada` — the same message for every refusal.
The body's `player` field is overwritten from the token, never merged. The
`?id=` / `?player=` query strings are ignored.

The token header is deliberately not `Authorization`: the painel's bearer
session uses that, and the owner can be logged into both surfaces at once.

## Live sessions and revocation

`data/player_sessions.json` holds one row per minted token: player, epoch,
created/last-seen/expires (unix seconds), remember, the opening browser's
`User-Agent` and IP. A token whose id has no row is refused, even though its
signature still verifies.

| Action | Effect |
|--------|--------|
| `GET /api/player/sessions` | The caller's own rows, newest first, with the current one marked |
| `POST /api/player/logout` | Deletes the caller's row — this device only |
| `POST /api/player/sessions/revoke` `{session_id}` | Deletes another row of the caller; a stranger's id is a 401 and leaves it alive |
| `POST /api/player/sessions/revoke-others` | Every row of the caller except the current one |

A player keeps at most 20 live rows; the oldest is dropped at the cap, and
expired rows are pruned on writes and on every list.

`session_epoch` lives on the player row (0 for accounts created before 0069).
A token names the epoch it was minted under; when the row's value differs, the
token is refused. The epoch is bumped — and the player's rows deleted — by:

- `POST /api/player/password/reset` (the self-service link, decision `0068`);
- the operator's test-account password reset;
- the operator's test-account deletion;
- a legacy `upsert_player` that writes a new password.

Deleting the row invalidates every token for it immediately. Disabling test
accounts in the painel does the same at the next request.

A password reset is all-or-nothing by design; everything else is per device.
A token minted before 0070 (no session id) is refused: that player logs in
once.

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

The account view lists the live sessions ("Sessões ativas"): device label from
the user agent, start, last use, expiry, the current row marked, an "Encerrar"
per row and "Encerrar as outras sessões". "Sair da conta" now calls
`POST /api/player/logout` before clearing the local copy, so the token is dead
on the server too.

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

# the list, then end this device: the same token is refused afterwards
curl -s http://127.0.0.1:8765/api/player/sessions -H "X-Player-Token: $TOKEN"
curl -s -X POST http://127.0.0.1:8765/api/player/logout -H "X-Player-Token: $TOKEN"
curl -s -o - -w '\n%{http_code}\n' http://127.0.0.1:8765/api/player \
  -H "X-Player-Token: $TOKEN"      # 401
```

After a password reset, the profile call must answer 401 as well.

## Tests

`demo.test_demo.PlayerSessionTest` (8) and `PlayerSessionHttpTest` (4):
minting at every door, both lifetimes, tampered/foreign/expired tokens, reset
and operator-reset revocation, deleted rows, derived key, 401 without a token,
token-beats-body on a deposit, `?id=` ignored, and crash-round ownership.

`DeviceSessionTest` (9) and `DeviceSessionHttpTest` (4): every mint is a row,
the list marks the caller, logout ends one device only, a stranger cannot
revoke by id, "revoke others" keeps the caller, the 20-row cap, the throttled
touch, expiry pruning, a 0069-shaped token without a session id, an operator
reset emptying the list, and the four routes answering 401 without a token.
