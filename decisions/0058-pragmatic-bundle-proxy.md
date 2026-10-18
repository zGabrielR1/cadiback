# 0058 — Pragmatic Play was running the publisher's bundle unpatched

Date: 2026-10-18
Status: accepted

## Context

`demo/game_proxy.py` has long carried `patch_unity_client` /
`CLIENT_PATCHERS["pragmatic_play"]`, a set of body fixes for the Pragmatic
Unity client that boots off the publisher's origin:

- the importer resolves a couple of post-import references by hard-coded index
  (`ret.objects[JsonTypes.indexOf(0)]`, `roots[1]`) and picks the wrong object
  when the load order shifts;
- `ServerInterface.ParseConfigFile` reads `this.configFile.text`, which can
  deserialize without its text, and blindly `.split("\\n")`s it;
- ~42 animator call sites read `X.animationCurve.keys[...]`, and the curve can
  deserialize without its keys, throwing on the first frame.

These fixes were dead code. `patch_unity_client` is applied by `rewrite_urls`,
which only ever sees a *proxied* body — and decision 0028 deliberately keeps
the asset tree on the publisher's CDN, so the browser fetched `build.js`
straight from `demogamesfree.pragmaticplay.net` and ran it byte-for-byte as
shipped. Verified by CDP: the running bundle's URL was the publisher's, and the
served body contained no `__acKeys` helper.

The consequences were visible in a local reproduction (see below): an uncaught
`TypeError: Cannot read properties of undefined (reading 'time')` in
`WidgetColorAnimator.Start` (from the operator-logo bundle overriding `Awake`)
and `... (reading 'transform')` in `internalContinueImporting` — both cases the
dead patches were written to fix — after which the render loop died and the
loader parked on the splash at ~90%.

The client loads its own bundle through `loadScript()` in `bootstrap.js`:

```js
function loadScript(url){
  if(url.indexOf("build.js")==-1) url=UHT_CONFIG.GAME_URL+url+"?key="+...;
  else url=UHT_CONFIG.GAME_URL+window["UHT_SCRIPTS_SIZE"].split(":")[0];
  var xmlhttp=new XMLHttpRequest; ... xmlhttp.open("GET",url,true); xmlhttp.send();
}
```

— an `XMLHttpRequest` for an absolute URL on the publisher's host.

## Decision

**Route exactly that one request through the proxy.** The bridge already wraps
`XMLHttpRequest.prototype.open` at document start (for the bet URL), so it is
the right place: `pp_proxied_client_script` rewrites an absolute
`demogamesfree.pragmaticplay.net/.../build.js?key=...` into the equivalent
`/g/<game_id>/_abs/...` path, and rewrites nothing else.

Only the bundle moves. Every other asset — the import JSONs, the textures, the
styles — stays on the CDN on purpose (decision 0028): proxying the asset tree
is what changes the import order and breaks the deserializer. The bundle is a
script, not an import input, so moving it is inert with respect to ordering.
`rewrite_urls` then serves `patch_unity_client(original)`; a byte comparison in
Python confirms the served body is *exactly* the patched original and nothing
else (no host rewriting leaks into it).

The proxy adds no new endpoint: `_abs` already exists and is the same path the
money calls use.

## Consequences

- Boot-time exceptions reach **zero** (previously one flaky error per run:
  `WidgetColorAnimator.Start` `.time`, `internalContinueImporting` `.transform`,
  or `ServerInterface.ParseConfigFile` `.split`, varying run to run).
- All 93 textures load and the import completes; the XT layer's connection
  callbacks (`evtConnectionReady`, `evtInitRequest`) now **fire**, and the XT
  registration counter moves from 14 events to 34–70. Before this change they
  never fired at all off-origin.
- The loader still parks on the splash. The remaining gap is upstream of the
  bundle: `GameLogicRuntime.listOfStages` is an array of cross-file component
  references that deserializes **empty** off-origin, so `GameLogicRuntime.Start`
  never calls the stage `UHTInit`s, so `XT.RegisterAndInit` never runs and
  `Evt_ToServer_RequestInit` is never registered. The bundle patches address
  the importer's index lookups, not this reference resolution; injecting the
  stage list at runtime does not restore registration either. That is the next
  item (recorded in 0057, not fixed here).
- `ServerOptions.serverUrl` is now pinned to the document origin when it names
  any host other than the document's own. The client builds it as
  `https://GetDomain()`, so on a plain-http development origin (local
  `http://127.0.0.1:<port>`) it points at an unreachable TLS target and the
  client makes no server calls at all. The live service already served from
  `https://cadiback.onrender.com` and is unaffected — it is a no-op there —
  but it is what makes a local reproduction possible.

## Reproduction

Run the operator locally and point a CDP browser at it. Two traps, both of
which cost real time:

1. **Mint a fresh launcher token after every server restart.** Wallet tokens
   live in memory, so a restarted server silently serves the game document
   *without* the bridge and `__WALLET__` — the symptoms then look like a bridge
   bug.
2. Drive `/g/<game_id>?token=...` directly. The parent frame that answers the
   wrapper protocol is absent, so adapter-routed calls report
   `StatusCode 0`; that is expected and not evidence about the wallet.

The publisher's own `openGame.do` URL for the same symbol boots in the same
browser and is the control.
