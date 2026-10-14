# 0041 — the games you opened, kept on this machine

**Date:** 2026-10-14
**Status:** accepted.

## What was wrong

The Recentes tab stored a list of `game_id`s in `localStorage` and then
rendered by filtering whatever `/api/catalog` had returned:

```js
return JSON.parse(window.localStorage.getItem("casa-recent") || "[]")
```

It was a **pointer to the lobby, not a copy of it**. So the tab you open in
order to play something was the one tab that could come up empty: on a cold
Render instance (~30s of it), on one bar of signal, with the server asleep,
or simply before the catalog request came back. Meanwhile the server-side
history (`/api/history`) only knows about *in-house* rounds, so for 182
publisher titles the local list was the only record that they had ever been
opened — and it was useless exactly when it was needed.

## What it is now

`web/lib/localCache.js` stores the game itself: `game_id`, `title`,
`provider`, `category`, `cover`, `rtp`, `demo_url`, `notes`, with the open
time. `CasinoHome` builds the Recentes list from the catalog where the two
overlap and from the cache where the catalog is silent, so the lobby stays
authoritative and the cache is what is left when it is not.

The tab says which it is showing — *"N deste(s) veio do cache deste
dispositivo — o catálogo ainda não respondeu"* — because a row served from
this machine is not a fresh catalog row and the player should not have to
guess.

## Three things that had to be got right

**Order comes from `ts`, not array position.** Every writer appends at the
front, but "newest first" should not depend on that staying true: a future
writer that appends at the end would silently invert the tab. An entry with
no usable `ts` sinks to the bottom, which is the honest reading of "we do not
know when".

**Both storage shapes are readable.** v1 wrote a bare array; v2 writes
`{v, entries}`. An upgrade reads what an older build wrote instead of
starting blank, so a returning player keeps their recents.

**Only a real `game` counts as a cached game.** Trimming the entry itself
would turn an id-only v1 record into a "game" with nothing but an id, which
then renders as a blank card instead of being recognised as "ordered, but we
do not have it". Caught by the first run of the checks.

## Storage is a convenience and says so

`localStorage` can be absent (private mode), full (quota), or hold bytes a
previous version wrote. Every read is total and every write is swallowed;
on a quota error the cached metadata is dropped and the ids kept, so the
list survives even when the copy does not. A recents list must never take the
lobby down with it.

## Checks

`localCache` has 21 execution checks (round trip, reorder without
duplication, cap, trim, both legacy shapes, six kinds of garbage, missing
key, quota fallback, missing `window`, id-less games). They found two real
bugs on their first run — both of the "shape" mistakes above.
