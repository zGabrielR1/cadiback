# 0062 — Pragmatic boots off-origin: the signed session table keys its field decryption

Date: 2026-10-18
Status: accepted (shipped)

## Context

Decision 0059 diagnosed why Pragmatic Play's Unity client parks on its splash off
the publisher's origin, and closed with "the missing piece is the publisher's own
obfuscated deserializer; we do not emulate it". Item 2 of 0057 stayed open across
sessions on that basis. The premise was wrong. There is no *derived-field* pass to
reproduce: the component fields in the shipped scene JSON are **encrypted**, and
their decryption is keyed to the publisher's own origin. One prepended shim
restores it.

## What the deserializer actually does

`deserializeComponentRec(source, dest, …)` (unobfuscated, top level, ~30 KB of the
bundle) runs an in-place **value decryption** over any component whose
`serializableData` carries `wasabiCode`. The branch is the whole mechanism:

| step | detail |
|---|---|
| key order | `Object.keys(source)`, sorted with `localeCompare` under `en-US` |
| permutation | `_0x104115(n, 0x64, wasabiCode ^ 0x60)` — a permutation of `0..n-1` |
| move | `_0x293c16[keys[P[i]]] = source[keys[i]]` — **values change key names** |
| offset | when `(n + wasabiCode ^ 0x60) & (1 << i)`, the value is also touched: a boolean is flipped, an integer or float gets `-= n + i` |
| `CAT_Container` | same shape, but over `events[].serializableData.actions` with `0x32` |
| id | every event's `id -= wasabiCode & 0xf` |
| cleanup | `delete source.wasabiCode`, `delete source.instanceFingerprint` |

So `GameLogicRuntime`'s shipped `"listOfStages":[]` and `"startingStage":1` are
scrambled values, and so are the `25`/`20`/`100054` seen on `StageInit`. The
straight read of the bytes is meaningless — which is exactly why 0059's
"`listOfStages` deserializes empty" looked true and why its hunt for a pass that
*fills* the field found nothing. Nothing fills it; it is *decoded*.

## What seeds the permutation

`_0x104115` mixes a deterministic core (`n*0x64 + wasabiCode`) with choices taken
from three environment functions, picked per element with `Math.random()`. Each
function returns `false` only when the environment **matches** an RSA-signed
string table the game config carries, and each begins by short-circuiting on
`UHT_GAME_CONFIG_SRC.replayMode`:

| # | reads | compared against |
|---|---|---|
| 1 | `window._634` (the bundle's own `navigator.userAgent`, captured at load) | signed `userAgent` |
| 2 | `Math.floor(Date.now() / 1000)` | signed `serverSeconds` (± 60 h) |
| 3 | `window._4025` (the bundle's own `location.hostname`, captured at load) | signed `serverHostname`; **exempt** on `localhost`/`127.0.0.1` |

The table is `UHT_GAME_CONFIG_SRC.sessionKeyV2[0]`, RSA-openable with the public
key embedded in the bundle, and the bundle caches the plaintext at
`Vars[<sessionKeyV2[0]> cleaned of /[^0-9a-z-A-Z ]/]` as a comma-joined char-code
list whose decoded text is JSON:

```json
{"serverHostname":"demogamesfree.pragmaticplay.net",
 "serverSeconds":1792360285,
 "userAgent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
```

On the publisher's origin all three return `false`, so the `Math.random()` pick is
invisible and the permutation is deterministic. Anywhere else the user agent and
the hostname mismatches return `true`, the pick becomes observable, the
permutation collides with itself, and *every* field of *every* `wasabiCode`
component decrypts to garbage. Downstream this surfaces only as
`GameLogicRuntime.Start` throwing `Cannot read properties of undefined (reading
'length')` on the stage list it never received.

## The fix

`demo/game_proxy.py::_PP_SESSION_PIN` is prepended to the Pragmatic bundle, so it
lands before the bundle captures its own two globals. It pins `_634` and `_4025`
with accessors (which also swallow the bundle's captures) and reads the signed
values out of `Vars` at call time — the deserializer writes the table before it
decrypts the first field, so the lookup always hits. The shipped constants are
only a fallback if that lookup is unavailable. The clock is left alone: the
publisher signs the current time on every mint, so the ± 60 h window always holds.

`replayMode = true` would also force all three to `false`, but it is a real game
flag with other readers; pinning the two globals changes nothing but the check.

## Proof

| signal | before | after | publisher's own page |
|---|---|---|---|
| `LoaderProgress.Localize/Blocking/Symbols/Init` | `0/0/0/0` | **`1/1/22/1`** | `1/1/22/1` |
| `EventManager.handlers` | 34 | 64 | — |
| `allObjects` after the game import | 11571 | **843** | 843 |

Local (`127.0.0.1`, no CDP injection, through the real proxy) reaches
`1/1, 0/-, 22/22, 0/1`; `InitConnection` is the one step that needs the money
round-trip, which on a plain-HTTP local origin is the proxy's own
`https://127.0.0.1:8777/_abs/…` scheme mismatch, not this. On the deployed
(`https`) origin the loader completes **and Gates of Olympus renders, spins and
runs its real UI** — the first time a Pragmatic title has booted off-origin.
Verified with `/tmp/opencode/shot.mjs` against the live launcher.

## Reproduction traps

- The three checks read **`window._634` / `window._4025`**, not `navigator` /
  `location` directly; the bundle captures them once, at its own load, by
  `eval(atob(…))`. A pin must therefore be in place *before* the bundle body runs
  — prepending to the bundle works, a script injected later does not.
- The signed table only appears in `Vars` after the first component
  deserialization, so a probe that reads it before the loader starts sees
  `undefined` and proves nothing.
- Off-origin the failure is silent and total: no boot-time exception reaches
  `window.onerror`, and the splash simply never moves.
