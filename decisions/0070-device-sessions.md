# 0070 — Device sessions

Date: 2026-10-20. Status: **shipped and deployed** (commit `9c2659e`, live on
`cadiback.onrender.com`; unit/HTTP-verified locally, the four routes re-probed
against the live service, and the served bundle carries the session list).
Closes the limit 0069 recorded: "a single device cannot be logged out alone" —
a logout was a browser-side clear, and a stolen token stayed valid until `exp`
unless the password was reset, which logged every device out.

## The gap this closes

0069 made the token the credential and revocation one integer on the player
row. That integer is all-or-nothing by construction: a password reset, an
operator reset or a deleted account kills every token at once. Two ordinary
things had no answer:

1. **"Sair da conta" did not end the session.** It cleared
   `localStorage`/`sessionStorage`; the token itself remained valid, and a copy
   of it kept working. The button was a convenience, not a logout.
2. **"It was not me" had no per-device answer.** The only remedy was the
   password reset, which signs out the phone, the laptop and the TV at once.

A player-facing platform needs both, and the alternative — shorter lifetimes
plus refresh tokens — only shrinks the window; it does not revoke.

## Decision

### 1. The token names a row, the row decides

Every minted token carries a session id `s` in the signed payload. The host
keeps one row per token in `data/player_sessions.json`:

```json
{"sessions": {"<sid>": {
  "player": "player-…", "epoch": 0,
  "created": 1760000000, "seen": 1760000000, "expires": 1760432000,
  "remember": false, "user_agent": "Mozilla/5.0 …", "ip": "203.0.113.9"}}}
```

Verification is still the signature and the epoch; the row is the **allowlist**.
A correctly signed token whose id has no row is refused. That is what makes a
logout real without giving the token a server-side payload: the row holds only
what the list needs, never the credential.

The trade 0069 avoided is paid honestly: one more small JSON read on the same
pass as the player row the host already reads per request, and **no write on a
read-only request**. `touch` (last seen) writes at most once per 10 minutes.

### 2. Four endpoints, one owner

| Route | Effect |
|-------|--------|
| `GET /api/player/sessions` | The caller's rows, newest first, current marked |
| `POST /api/player/logout` | Delete the caller's row — this device |
| `POST /api/player/sessions/revoke` `{session_id}` | Delete one of the caller's rows |
| `POST /api/player/sessions/revoke-others` | Delete every row except the current |

All four require the token, derive the player from it, and refuse a stranger's
session id with the same 401 message as a forged token — revoking is not a way
to ask "does this id exist?".

Rows are keyed by session id, which is public: the signature is the credential,
so knowing an id buys nothing. The list exposes the id so another device can
name the row it wants to end.

### 3. The epoch still means "all devices"

`session_epoch` keeps its job: a password reset, an operator reset, or a test
account deletion bumps it **and** deletes the player's rows, so nothing dead
lingers in the file. Disabling test accounts still refuses at the next request.
The two mechanisms answer different questions — "this device" (row) and "this
credential" (epoch) — and neither replaces the other.

### 4. Bounded, pruned, throttled

- At most **20** rows per player; the oldest falls off at the cap (a login loop
  on a broken browser cannot grow the file without bound).
- Expired rows are pruned on every write, on every list, and on lookup.
- `touch` updates `seen` only when it is ≥ 10 minutes stale, so a busy tab does
  not write on every request.
- A row is deleted, never rewritten with a new token: rotation is a new login.

### 5. The storefront shows the list

`web/app/components/AccountView.jsx` gains "Sessões ativas": a compact
browser · OS label derived from the user agent (the raw string is noise), the
IP, start, last use and expiry, the current row marked, an "Encerrar" per row,
and "Encerrar as outras sessões". "Sair da conta" now calls
`POST /api/player/logout` before clearing the local copy, and revoking the
current row from the list logs the tab out.

## What ships

- `demo/player_session.py`: `s` in the payload, `PlayerSession.session_id`,
  `new_session_id()`, and `SessionRegistry` (record, lookup, touch, active,
  revoke, revoke_others, revoke_player, prune).
- `demo/server.py`: the registry on `Demo`, `device` threaded through the four
  mint doors, `player_session()` (signature → row → epoch → registry),
  `player_sessions_view`, `logout_player`, `revoke_player_session`,
  `revoke_other_sessions`, the epoch bumps revoking rows, and the four routes.
- `web/app/components/AccountView.jsx`, `web/app/page.jsx`: the list and the
  server-side logout.
- `docs/sessions.md`: the endpoints, the row shape, the cap and the smoke
  checks.
- `demo/test_demo.py`: `DeviceSessionTest` (9) and `DeviceSessionHttpTest` (4).

## Verification

`DeviceSessionTest` proves every mint is a row and the list marks the caller;
logout ends one device while the other token keeps working (and the signature
still verifies — the row is what refuses it); a stranger cannot revoke by id;
"revoke others" leaves exactly the current row; the cap keeps the newest two;
`touch` is throttled; an expired row is pruned and refused; a correctly signed
0069-shaped token without a session id is refused; an operator reset empties
the list.

`DeviceSessionHttpTest` proves the wiring: the list and logout over HTTP, a
revoke by id taken from the list, "revoke others" leaving one row, and all four
routes answering 401 without a token — plus a stranger's revoke being 401 while
the victim keeps working.

Suites: `frame` 50/50 · `demo` 424/424 · `verify.py` 0.

## Alternatives considered

1. **A full session table (like the admins' `SessionBook`) with server-side
   payloads.** The natural next step, but the token would stop being the proof
   and every request would read (and sometimes write) the store. The allowlist
   buys the behaviour that matters — per-device revocation — without moving the
   credential into the database.
2. **A denylist of revoked ids.** Smaller file, but it grows forever, needs the
   same lookup, and "absent means valid" is the wrong default for a logout.
3. **Short TTL + refresh token.** Bounds a stolen token's life but cannot
   revoke on demand, and adds a rotation protocol to get wrong.
4. **A cookie with a server session.** The same table cost, plus the CSRF
   surface 0069 rejected.
5. **Keep 0069 as is and document the limit.** Honest, but it leaves a "Sair"
   button that does not sign out — a button that lies is worse than no button.

## Limits

- **The registry is per process, in one file.** The deploy runs one container,
  so that is consistent with the rest of the demo store; a second replica would
  need the Postgres seam (0049).
- **Ephemeral host, ephemeral sessions.** On the free plan `data/` is rebuilt
  at each deploy, so every deploy logs players out. That is the same lifetime
  the player rows already have there; a persistent disk or Postgres fixes both.
- **A stolen token is still a session until its row is revoked or it expires.**
  The list makes revocation possible, not automatic.
- **20 rows, 10-minute `seen` granularity.** Deliberate bounds; a real platform
  would page the list and tighten the window.
- **The list stores user agent and IP.** That is what makes "is that me?"
  answerable; it is also personal data kept beside the session. It dies with
  the row.
- **No rotation on use.** A token keeps its id for its whole life; the expiry
  is absolute, as in 0069.
