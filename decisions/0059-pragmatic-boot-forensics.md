# 0059 — Why Pragmatic Play's client cannot finish booting off-origin

Date: 2026-10-18
Status: superseded by 0062 (the diagnosis here is wrong; the boot **is** fixable)

> **Superseded.** The reading below — that the missing piece is a publisher
> "derived-field pass" we do not emulate — is incorrect. The scene's field values
> are *encrypted*, not derived, and their decryption is keyed to the publisher's
> origin via an RSA-signed session table. Pinning two globals the bundle captured
> restores it and the game boots; see decision 0062. Everything in this file about
> *how to observe* the failure (the method-wrapper probes, the swallowed `Start`
> exception, the sample-to-sample instability of `listOfStages`) still holds and
> is what made 0062 possible.

## Context

Decision 0058 fixed the dead bundle patch and proved the Pragmatic client now
runs the publisher's `build.js` from our origin with zero boot-time exceptions,
93 textures loaded, the import complete, and the XT connection callbacks firing
(`evtConnectionReady`, `evtInitRequest`). The splash still parks: the loader
never leaves `LoaderProgress.Localize_Current === 0`.

0058 recorded the working hypothesis that `GameLogicRuntime.listOfStages`
"deserializes **empty** off-origin" and that injecting the stage list at runtime
"does not restore registration". This session instrumented the client properly
and both halves of that sentence turned out to be wrong — the real mechanism is
different and is now known end to end.

## What is actually true

Measurements, ours vs the publisher's own `openGame.do` page, in the same
headless Chromium (CDP), same window size, same user agent:

| signal | ours | publisher |
|---|---|---|
| `LoaderProgress.Localize/Blocking/Symbols/Init` | `0/0/0/0` | `1/1/22/1` |
| `XT.RegisterAndInitDone` | `false` | `true` |
| `XT.variablesEvent` count | 34 | 261 |
| `Evt_ToServer_RequestInit` registered | `false` | `true` |
| import steps / `deserializeIndex` | 39 / 24621 | — (scene released) |
| `allObjects` after the game import | 11571 | 843 (later GUI package) |

Traced call path (method wrappers installed at document start):

ours
```
2330 addNewSceneRoot obj=ClientRoot ok
4250 GLR.Start stages=undef   THREW Cannot read properties of undefined (reading 'length')
4421 addNewSceneRoot obj=GameRoot ok
```

publisher
```
2807 addNewSceneRoot obj=ClientRoot ok
6881 XT.RegisterAndInit ok
6881 UHTInit XTRoot=[object Object] typeof=object ok
6882 GLR.Start stages=6 ok
7022 addNewSceneRoot obj=GameRoot ok
```

So on both origins the order is `addNewSceneRoot(GameRoot)` → `Awake`/`Start`
cascade → `GameLogicRuntime.Start` → per-stage `UHTInit` → `StageInit.UHTInit`
→ `XT.RegisterAndInit(this.XTRoot)`. The only difference is the state of the
component's fields when that happens.

`callComponentCallback` sets the component's `start_called` flag **before**
invoking `Start`, so a `Start` that throws is never retried for the life of the
page. Ours throws, and nothing downstream ever runs.

### The scene data omits fields on purpose

The shipped scene JSON is chunked (`game000.json`, `game001.json`, … are
concatenated by the loader before `JSON.parse`; each file alone is not valid
JSON). In that concatenation the sole `GameLogicRuntime` component says:

```json
"debugHistory" : [ {"fileID":340}, {"fileID":341}, …, {"fileID":345} ],
"listOfStages" : [],
"startingStage" : 1,
"wasabiCode" : 77
```

and the sole `StageInit` component says:

```json
"XTRoot" : false,
"wasabiCode" : 94
```

`listOfStages` is **not** empty because of a deserialization bug: it is `[]` in
the publisher's own bytes. The six stages are the six children of the
`GameLogicRuntime`'s own GameObject (`Logic`): `Init` (`StageInit`), `Result`,
`Spin`, `Gamble`, `ResultFreeSpin`, `Transition` — which is exactly the order
and membership of `debugHistory`. `XTRoot` must resolve to the GameObject
literally named `XTRoot`, which exists in `game000.json`.

So the publisher's client has a **derived-field pass** that turns those
placeholders into live references, driven by `wasabiCode` and by instantiation
of every `{"nestedFieldType": …}` object into a real class instance
(`internalProcessAsNestedClass` / `createNestedObject`). That pass is inside the
bundle's obfuscated section, together with a self-check that keys a string
table on a hash of the caller's own source text and on `wasabiCode`. It cannot
be reproduced from outside, and it is the only thing standing between the
imported scene and a running game.

### Negative results (each eliminates a plausible cause)

1. **Assets are not missing.** Ours fetches all 52 publisher resources — the
   same `GUI000..006`, `GUI_resources000/001`, `game000..004`,
   `main_resources000..016`, `other_resources000/001`, `client/resources.json`,
   `client/game.json`, `packages/*.json` — with identical byte counts. The
   loader's `allGameJSONSadded` is `true`, `resourcesLeft` is `0`, and
   `gameRequests` groups are all parsed.
2. **Our bundle patch is not the cause.** `PP_RAW_CLIENT=1` serves the
   publisher's bundle byte-for-byte unpatched; the failure is identical.
3. **Our bridge is not the cause.** Blocking `bridge.js` (so the document runs
   with no bridge and no bundle rewrite) gives the identical failure.
4. **Not the class registry.** `typeof` of every nested type used by the data
   (`XTVar`, `CATLink`, `Color`, `Gradient`, `UHTStage`, `XTLink`,
   `LocalizationRoot`, …) is `function` on both origins.
5. **Not a truncation or order problem.** The chunks concatenate to valid JSON;
   `nonCachedRetried` stays `false`, meaning the engine's parse never failed.
6. **Not a race that more time fixes.** Rebuilding `listOfStages` from the six
   `Logic` children and re-running `Start` over 65 s fails 414 consecutive times
   on `this.vdVariable.GetAnimatedVarName is not a function` — one of many
   components whose `{"nestedFieldType":"XTVar"}` field was never instantiated.
   The gap is systemic, not a timing window.
7. **Re-running the whole deserialization does not close the gap.** Capturing
   `componentToRawDataMap` before `clear()` wipes it, restoring the reference
   maps, and re-running `comp.deserialize(...)` over all 24621 components
   completes in 270 ms with **zero** exceptions — and still leaves the derived
   fields unset. The second pass cannot help because the pass that fills them is
   not `deserialize`.

## Decision

**Do not ship a half-repair.** A bridge-side reconstruction of `listOfStages`
and `XTRoot` is possible, was implemented and tested, and does move the boot
past `XT.RegisterAndInit` — but the very next component fails on another
underived field, so the game is still unplayable and the added code is risk
without benefit.

Keep the diagnostic capability instead:

- `PP_RAW_CLIENT=1` in the operator environment serves `CLIENT_PATCHERS`
  providers' bundles untouched. It is the switch that distinguishes "our
  integration broke it" from "the publisher's bundle broke it", which is the
  first question on this class of bug. Live deployments never set it.

Pragmatic Play's wallet layer is done and is unaffected by this: the bridge is
installed, the saldo HUD renders over the Pragmatic splash, and money calls
route through `/api/wallet/*` as for every other provider. What is missing is
the publisher's own scene activation, which their obfuscated deserializer
performs and ours (by design — we do not emulate it) does not.

## Owner-visible consequence

Pragmatic Play titles will show our saldo HUD and our wallet will debit/credit
correctly, but the reels will not spin in the embedded client. Two ways forward,
both deliberate:

1. accept the limitation and keep Pragmatic titles behind a "demo only" note, or
2. reproduce the derived-field pass: `listOfStages` ← the ordered `UHTStage`
   components on the `Logic` GameObject's children, `XTRoot` ← the GameObject
   named `XTRoot`, and every `{"nestedFieldType": T, "serializableData": S}`
   object ← `new window[T]()` then `deserialize(S)`. Step 1 and 2 are
   implemented in this session's probes and are correct; step 3 is the bulk of
   the work and needs a full audit of the nested-object schema.

## Reproduction

The traps from 0058 still apply (mint a fresh launcher token after every server
restart; drive `/g/<game_id>?token=` directly). Two additional ones, both of
which produced hours of wrong conclusions:

1. **`listOfStages` looks different on every poll.** It reads `undefined`, `[]`
   and `array:6` across runs and across moments — because the scene tree is
   assembled over ~8 s and the field is only meaningfully readable after
   `addNewSceneRoot(GameRoot)` has run. A single-sample probe of it is
   meaningless; wrap the methods and follow the call.
2. **The engine swallows `Start` exceptions.** `addNewSceneRoot` returns `ok`
   even though `GameLogicRuntime.Start` threw inside it, and
   `window.onerror` stays empty. Nothing short of wrapping
   `GameLogicRuntime.prototype.Start` and `StageInit.prototype.UHTInit` shows the
   failure.

`console.log` from the bundle is suppressed on both origins, so console capture
is only useful for browser-level warnings; the CDP harness
(`/tmp/opencode/evalc.mjs`) captures those, and the method-wrapper probes are
what actually carry the signal.
