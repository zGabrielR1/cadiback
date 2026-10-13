# 0036 — Pragmatic Play: boot advanced to server contact, not yet playable

Date: 2026-10-13. Status: **major progress, not done** — PP boots from a
dead loader to a clean living loop with zero errors and (in good runs)
POSTs gameService through our proxy, but no session completes yet and the
game is not playable. ~40 probes; every claim below was seen live.

## What was proven (side-by-side instrumented runs)

- Own origin: `serverUrl=https://demogamesfree…`, domain
  `test1.gp16.pragmaticplay.net`, 0 errors, full render.
- Ours: identical 37 JSON bytes (sha-verified), identical bundles,
  identical 5-push import sequence — yet the import finishes with ~947
  fewer deserialized components and an unlinked scene graph. Throttling,
  config rewriting, and GetDomain/URL-query theories all ruled out by
  experiment. The `serverUrl=studio.game-service.biz` sighting is a
  CONSEQUENCE (default surviving because the frame loop dies), not a cause.

## The repair stack (shipped in the bridge, pp:-gated, live on prod)

1. **Tree repair**: reattach children bottom-up along parent links —
   clears the `internalContinueImporting` game-root throw.
2. **Animator curve guard**: flat two-point curve when keys missing —
   clears `WidgetColorAnimator.Start` (the 0028 plan, now really shipped).
3. **Config fallback with the REAL demo creds** (found in the scene data,
   game004 TextAsset `04d5591c…`): `emul / 8fd105b3fbc1b /
   test1.gp16.pragmaticplay.net / ext_test1 / <symbol> / <lang>` —
   clears `ParseConfigFile`. Previous `demo/demo` guess replaced.
4. **Sanitizers**: CAT_Infector actions array, AnimationController target,
   VS_ReelsManager validateReelSpin, ExtraCameraSettingsAnchors refs,
   GameLogicRuntime null-stage — each verified as the next blocker.
5. **Dispatch shields**: per-component isolation for Awake/Start/OnEnable
   (`callComponentCallback`, `callComponentOnEnable`) and per-frame
   Updates (`Runtime.CallOnGameObjectList`) — one bad widget no longer
   kills boot or the frame loop. All skips stay console-visible.
6. **Session kickstart**: ensure ServerLink on ServerConnector, feed the
   document's gameConfig to OnApplicationConfigReceived, fire per-symbol
   init — the client then POSTs `/gs2c/ge/v3/gameService` through our
   origin (our proxy forwards to the publisher).

## Where it stands / next

After kickstart the client emits doInit POSTs but `InitConnection`
stays 0 — the session/login response handling is the current frontier,
then the `.do` round translator (Hacksaw-sized) for wallet settlement.
Boot varies run to run (different partial missing-sets); the repairs are
all idempotent and harmless on healthy trees. PP stays labelled free
play until a session completes end to end.
