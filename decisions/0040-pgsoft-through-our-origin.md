# 0040 — PG Soft through our own origin: boot, catalog, and the money API

**Date:** 2026-10-14
**Status:** accepted — 92 PG Soft titles serve from our origin with the wallet
bridge, and the money API is now mapped. The money **tap** is not built; §5
says exactly why and what is left.

Decision 0035 assessed PG Soft and recommended leaving it trial-only. Four
things it did not know, all found by capturing a real session rather than by
reading anything, changed the answer.

## 1. The mint, exactly

`https://public.pg-demo.com/demo/?gi=<id>` is a launcher SPA. It POSTs the
game's own query, form-encoded, to

```
POST https://public-api.pg-demo.com/web-api/operator-proxy/v2/Game/GetTrialLaunchURLHTML
Content-Type: application/x-www-form-urlencoded
gi=126&lang=pt
```

The answer is **raw HTML**, not JSON — `Content-Type: text/plain`, 29 831
bytes for gi=126 — carrying an inline `<script type="module">` whose tail is
a base64 blob. That blob is msgpack, and it is the only place the session
exists.

## 2. The hosts are not all dynamic (0035 said they were)

0035 recorded a "per-session dynamic host allowlist" for "random-letter
`<session>.com` hosts". The capture says otherwise: **every mint returns
three candidate triples** and the launcher picks one by weighted random.

| | game | static | money |
|---|---|---|---|
| stable | `m.pg-demo.com` | `static.pg-demo.com` | `api.f26xzzc7c.com`, `api.8jkxzybcq.com` |
| session A | `m.rhzzzvqpd.com` | `static.rhzzzvqpd.com` | `api.9zzzzz9q9.com`… |
| session B | `m.eajzzxhro.com` | `static.eajzzxhro.com` | … |

`parse_session` prefers the stable triple. So the allowlist does **not**
churn per player — the rolling hosts stay a fallback, which is what makes
this shippable at all.

A second, harder constraint: **every asset URL is signed**
(`…/8270b42ff8.2b98c.json?verify=1791981164-yBSObb%2F…`). The signature
covers the path, so the proxy forwards the query byte-for-byte and cannot
cache a signed URL under a key that drops it.

## 3. The headless User-Agent was the blocker (§4 of 0035, revised)

0035's open frontier said the client was "origin-coupled" by an environment
check and that capturing it needed a real browser. **It did not need a real
browser. It needed a real User-Agent.**

Headless advertises `HeadlessChrome`, and PG's engine refuses to lay out
under it. Measured, same code, same 1280x800 viewport:

| | `#GameCanvas` | requests | money-host calls |
|---|---|---|---|
| default headless UA | `0x0@0,0` | 56 | 3 (all `/healthcheck`) |
| ordinary Chrome UA | `450x800@415,0` | 332 | 13 |

One `--user-agent=` flag took the capture from "the engine never starts" to
"the whole money sequence". `capture_session.mjs` now sets it by default and
keeps `--ua none` for the comparison. This is the same class of mistake as
decision 0028's "the importer is not order-sensitive" — a conclusion drawn
from a probe that was broken in a way nobody had checked.

## 4. The money API, in full

With the engine running, the sequence is short, form-encoded, and returns
JSON — except the game config, which is binary:

```
POST <api>/web-api/auth/session/v2/verifySession
     btt=2&vc=2&pf=1&l=pt&gi=126&tk=null&otk=<ot>
  -> {"dt":{"tk":"<access token>","geu":"game-api/fortune-tiger/",
            "bau":"web-api/game-proxy/","occ":{"tcm":"You are playing Demo."}}}
POST <api>/web-api/game-proxy/v2/GameName/Get
     lang=pt&atk=<tk>&btt=2&pf=1&gid=126
  -> {"dt":{"31":"Baccarat Deluxe"}}          <-- "31" is a LOCALIZATION KEY
POST <api>/web-api/game-proxy/v2/Resources/GetByResourcesTypeIds
POST <api>/game-api/fortune-tiger/v4/GameInfo/Get      (BINARY)
POST <api>/web-api/game-proxy/v2/GameWallet/Get
     isagw=true&btt=2&wk=0_C&atk=<tk>&pf=1&gid=126
  -> {"dt":{"tb":100000.00,"pb":0.00,"cb":100000.00,"ch":{"cb":100000.00,"k":"0_C"},...}}
```

`occ.tcm` = *"You are playing Demo."* — the session is a trial session, so
the 100 000 is the publisher's, not ours. That is the thing to change, and
it is a balance, not an RNG.

**`GameName/Get`'s `"31"` is not the game name.** It answers "Baccarat
Deluxe" for *every* title probed — it is a localization key that falls back
to a default. This nearly caused a wrong catalog: the only real per-game
identifier in the handshake is the slug from `geu`.

## 5. What ships

* **92 PG Soft titles** (from 2), discovered by
  `scripts/discover_pgsoft_demos.py`: mint → `verifySession` → read `geu`'s
  slug. The full numbering is **gi 1–135** (nothing above 135 answers; 92
  live, 43 dead ids — re-probed serially to confirm they were dead and not
  throttled). Titles are derived from the slug, which is what PG's own lobby
  does, because the localized title lives inside the binary `GameInfo/Get`.
  `gi=126` → slug `fortune-tiger` → "Fortune Tiger", which is what the
  catalog already said.
* `demo/pg_proxy.py` mints and binds; `game_proxy` consults it in
  `_allowed_host`; `Demo.pg_launch` builds the launch.
  * **The session id lives in our path** — `/g/pg:fortune-tiger/pg/<session>/`.
    That is what makes the per-session hosts resolvable without a standing
    rule about somebody else's domain, and it is the one genuinely new
    mechanism PG needed (0035 §2.2).
  * **A minted host is `<prefix>.<label>.com` or nothing.** Binding a host is
    permission to fetch it server-side, so the shape is checked where the
    name leaves a publisher's answer — which also refuses
    `m.attacker.com.evil.net`, that a suffix check would wave through.
  * **The document is sent verbatim.** `pg_target` returns the minted URL
    unchanged rather than merging the client's query into it, so a player's
    wallet token cannot reach PG by that path.
  * **All the money hosts get bound**, not just the chosen triple's: the
    client health-checks both before committing, so binding one would break
    its own failover.
* The measured endpoints are written into `pg_proxy` as constants with the
  shapes beside them, so the tap builds URLs from evidence.

Verified live through `/g/`, spying on what leaves the process:

```
document : https://m.pg-demo.com/126/index.html?ot=…&l=pt&btt=2   1 035 781 b, bridge injected
asset    : https://m.pg-demo.com/loader/06.js?verify=abc%3D       111 971 b
wallet token sent to PG: False
asset signature preserved: True
```

Provider sweep (`demo/_sweep.py`, real launchers through `/g/`): **16/16**,
six different PG titles included. Before this, both PG rows answered
`no-launch` — they were never served through `/g/` at all.

## 6. Why there is still no money tap

Two reasons, one of them real work rather than a wall:

1. **The spin is a binary protocol.** `GameInfo/Get` is protobuf-ish, so a
   tap that has to *re-encode a spin* is a different job from one that has to
   rewrite a number. The **balance** side is the easy half — plain JSON in
   `GameWallet/Get`, and `rewrite_balance` already exists for exactly this
   shape. Nobody has captured a spin yet: reaching one needs a tap on the
   spin button's canvas coordinates, which is now plausible (§3 fixed the
   engine) but is the next capture, not a fact.
2. **We do not hold a session.** `verifySession` issues the `atk` that every
   later call carries, and PG ties it to the trial session it just minted.
   Settling through our books means either running the RGS ourselves (which
   decisions 0006/0008/0020 refuse) or mirroring the publisher's outcome,
   which is the Hacksaw pattern and needs step 1 first.

PG Soft therefore stays `wallet_isolated` — honest trial play, now served
from our origin with our bridge, our HUD and our catalog.

## 7. The one general proxy bug this found

`rewritable()` decided "is this a document?" from the last path segment, and
an empty segment — which is what **every** sub-path ending in `/` produces —
fell through to `if "." not in tail: return False`. So a document served at a
trailing-slash path got no `<base>` repair and **no wallet bridge**: the game
booted with nothing in front of it and, from our side, looked fine. Every
provider that launches on such a path had been silently un-bridged; PG is
just the first one whose URL shape exposed it.

`frame` 45/45, `demo` 205/205 (+14 PG), `verify.py` 0 problems, sweep 16/16.
