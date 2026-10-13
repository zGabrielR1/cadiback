# 0028 — Pragmatic Play (the main focus): why it fails and the options

Date: 2026-10-12. Status: researched hard, **not working**. Newest file wins.

## Where PP stands

21 lobby titles, all **wallet-isolated free play** — none settle on our books.
The blocker is PP's own client, and it is now characterised precisely.

## The evidence

PP's launcher (`gs2c/openGame.do` → 302 → `gs2c/html5Game.do`) serves a
**Unity-exported JS client** (`build.js`, ~3.2 MB) whose importer runs inside
the page. On PP's own origin it renders the full game, **0 errors**. Served
through our proxy it fails, and *which* error depends on the run:

| Where the client runs | Result |
|---|---|
| PP's origin (direct) | full game, 0 errors |
| our origin, everything proxied | importer deserializes an **empty game root** (`GameRoot.children.len=0`) |
| our origin, assets from the CDN, only money URLs rewritten | advances further; then `ServerInterface.ParseConfigFile` (`configFile.text` undefined), `WidgetColorAnimator.Start` / `SpriteSizeAnimator.Awake` (`animationCurve.keys` undefined), then `internalContinueImporting` (`ret.objects[JsonTypes.indexOf(1)]` undefined) |
| in an iframe (how the storefront embeds it) | same failure |

Two things were ruled out as causes:

- **Not the money rewrite.** With `MONEY_PATHS` disabled the *other* error
  returns — the failure exists without it.
- **Not synchronous XHR.** The bundle's resource loads are `async=true`; the
  one synchronous `open()` is a WebAudio capability probe.
- **Not our WebSocket hook** (PP opens no socket).

The importer resolves references by **hard-coded index**
(`ret.objects[JsonTypes.indexOf(0)]`, `[…(1)]`, `roots[1]`), and those indices
only line up when every JSON resource arrives in the publisher's own order.
Off-origin the resource set/order differs, so the lookups land on the wrong
object — hence a *different* error each run.

## What I tried this session

Re-applied the two well-understood, target-verified fixes (they are real, not
guesswork — each matches the live bundle) plus one generic one:

- `internalContinueImporting` / scene-root lookups: search every root object
  for the one carrying `LocalizationRoot` instead of trusting the index.
- `ParseConfigFile`: fall back to `xtLayer` when the config TextAsset arrives
  without its text.
- **All ~42 `…animationCurve.keys` reads** routed through one helper that
  substitutes a flat curve when the data is missing, instead of guarding each
  site.

They advance the client past each error in turn (verified: the served bundle
has every fix applied and parses cleanly), but it lands on the *next* index
lookup. Patching symptoms here is a moving target — see "The actual cause"
below for why.

## The actual cause: the client is origin-coupled

Option 4 (reproduce the publisher's load order) was tested and is a **dead
end**: two loads of PP's *own* page complete their 37 JSON resources in
**different orders**, and PP renders fine both times. The importer is not
order-sensitive, so there is no order to reproduce.

The real cause was found by elimination. Serving the document from our origin
with **nothing else changed** — no bridge injected, no URL rewritten, a pure
passthrough — still fails. So it is not our modifications; it is the
document's **origin**. And the client is origin-coupled *by design*:

```js
ServerInterface.GetDomain = function(){ return UHT_LOCAL ? ServerInterface.domain : location.host }
if (!UHT_LOCAL) ServerOptions.serverUrl = location.protocol + "//" + ServerInterface.GetDomain();
```

Everything the client calls "the server" is derived from `location`, so on our
origin its whole server identity changes — its loader input included, which is
where the failures surface (`configFile.text`, `animationCurve.keys`,
`ret.objects[JsonTypes.indexOf(1)]`).

## Why the earlier index lookups were a moving target

The importer resolves references by hard-coded index and the client assumes it
runs on its own host; off-origin the pieces it indexes are not the ones it
expects. Each symptom fix moved the failure to the next lookup — a loop, not
progress.

## The one technical door left (unexplored)

Split the client's **identity** from where its calls **go**:

- make `ServerInterface.GetDomain()` return the publisher's host (so the
  client believes it is on PP's origin and its internal indices line up), and
- keep `ServerOptions.serverUrl` pointed at **us**, so the actual server calls
  still come through our proxy and can be settled on our books.

That is a small, targeted client patch (two expressions) rather than a
whack-a-mole, and it is the only variant that addresses the coupling instead
of its symptoms. Untested.

## Options (the owner picks)

1. **Keep PP as labelled free play.** It renders and plays today — the lobby
   embeds PP's own page. Honest, free, zero risk.
2. **Try the identity/calls split above** — narrow, targeted, plausible; the
   only remaining technical idea, and it may still fail if the client checks
   its own origin elsewhere.
3. **Vendor operator account** — PP's RGS then calls *our* wallet
   server-to-server and the client legitimately runs on PP's origin. The real
   integration; commercial (track retired in 0007).
4. ~~Reproduce the publisher's load order~~ — **tested, dead end.**

**Recommendation:** option 1 now; option 2 is worth exactly one bounded
attempt before accepting option 3 or leaving PP as free play.


## What landed (code, kept)

`game_proxy.patch_unity_client` — the three fixes above, applied only to
Pragmatic Play bundles, each substitution verified against the live bundle.
They do not complete PP; decision 0025's "assets stay on the CDN" rewrite
still stands.
