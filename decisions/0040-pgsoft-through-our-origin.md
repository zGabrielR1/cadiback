# 0040 — PG Soft through our own origin: the boot half

**Date:** 2026-10-14
**Status:** accepted — PG Soft serves from our origin with the wallet bridge.
The money tap is **not** built, and §4 says why not.

Decision 0035 assessed PG Soft and recommended leaving it trial-only. Two
things it did not know, both found by capturing a real session rather than by
reading anything, changed the answer for the boot half.

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

## 3. What ships

`demo/pg_proxy.py` mints and binds; `game_proxy` consults it in
`_allowed_host`; `Demo.pg_launch` builds the launch.

* **The session id lives in our path** — `/g/pg:fortune-tiger/pg/<session>/`.
  That is what makes the per-session hosts resolvable without a standing rule
  about somebody else's domain, and it is the one genuinely new mechanism PG
  needed (0035 §2.2). The binding is only ever added by *this process* asking
  PG for it.
* **A minted host is `<prefix>.<label>.com` or nothing.** Binding a host is
  permission to fetch it server-side, so the shape is checked where the name
  leaves a publisher's answer — which also refuses
  `m.attacker.com.evil.net`, that a suffix check would wave through.
* **The document is sent verbatim.** `pg_target` returns the minted URL
  unchanged rather than merging the client's query into it, so a player's
  wallet token cannot reach PG by that path. The token rides our own query
  and is stripped on the way out.
* **The money hosts all get bound**, not just the chosen triple's: the client
  health-checks both of them before committing to one, so binding a single
  host would break its own failover. They are all hosts this publisher named
  in this answer.

Verified live through `/g/`, spying on what leaves the process:

```
document : https://m.pg-demo.com/126/index.html?ot=…&l=pt&btt=2   1 035 781 b, bridge injected
asset    : https://m.pg-demo.com/loader/06.js?verify=abc%3D       111 971 b
wallet token sent to PG: False
asset signature preserved: True
```

And the provider sweep (`demo/_sweep.py`, one real launcher per provider
through `/g/`): **12/12**. Before this, both PG rows answered `no-launch` —
they were never served through `/g/` at all.

## 4. Why there is no money tap

The client is a 1 MB string-array-obfuscated bundle. Its endpoints are built
at runtime — the document contains no `api.`, no `spin`, no `balance`, and no
`web-api` string at all.

The capture tool (`scripts/capture_session.mjs`, built here: DevTools
Protocol over the browser already on the machine, because playwright-core is
deliberately not in the tree) boots it and drives it — tap, click, eval,
viewport, websocket frames. The result is decisive:

* the game document loads, `loader/06.js` loads, assets load, blobs render;
* **only** `/healthcheck` ever reaches a money host;
* `#GameCanvas` measures **`0x0@0,0` even with a 1280x800 viewport override**.

The engine never lays out, so there is no lobby, so there is no spin to
capture. The boot is gated on something in the environment, the same class of
blocker decision 0028/0036 hit with Pragmatic Play.

So the spin and balance request shapes are **not known**. A money tap written
against a guessed shape would be worse than none: it would look right, settle
nothing, and cost the next person a day to discover which. PG Soft therefore
stays `wallet_isolated` — it is honest trial play, now served from our origin
with our bridge and our HUD instead of an iframe of somebody else's page.

## 5. What would unblock it

A capture taken from a real, non-automated browser session — one where a
human pressed start once. `scripts/capture_session.mjs` would then have the
answer in one run, and §3's machinery is already in place to carry it. That
is a ten-minute job for a person at a keyboard and an unbounded one for a
headless one.

## 6. The one general proxy bug this found

`rewritable()` decided "is this a document?" from the last path segment, and
an empty segment — which is what **every** sub-path ending in `/` produces —
fell through to `if "." not in tail: return False`. So a document served at a
trailing-slash path got no `<base>` repair and **no wallet bridge**: the game
booted with nothing in front of it and, from our side, looked fine. Every
provider that launches on such a path had been silently un-bridged; PG is
just the first one whose URL shape exposed it.

`frame` 45/45, `demo` 203/203 (+12 PG), `verify.py` 0 problems.
