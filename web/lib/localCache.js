/** The games you opened, kept on this machine.
 *
 * The Recentes tab used to store nothing but `game_id`, and render by
 * filtering whatever `/api/catalog` had returned. That made it a *pointer*
 * to the lobby rather than a copy of it: on a cold Render instance (about
 * 30s), on a phone with one bar, or with the server asleep, the tab you go
 * to in order to play something was the one tab that came up empty — the
 * games you had actually opened were on the other side of a request that
 * had not come back yet.
 *
 * So the cache holds the game itself: title, provider, cover, category,
 * rtp and the publisher URL, as they were when you opened it. What the
 * lobby knows wins (it is live and authoritative); the cache is what is
 * left when the lobby has not arrived.
 *
 * Everything here is best-effort by construction. Storage can be absent
 * (private mode), full (quota), or hold bytes a previous version wrote; a
 * recents list is a convenience and must never take the lobby down with
 * it, so every read is total and every write is swallowed.
 */

const KEY = "casa-recent";
const VERSION = 2;

/** How many opens we keep. A month of casual play, roughly; past that the
 * list stops being "what I was playing" and becomes the whole catalog. */
export const RECENT_LIMIT = 30;

/** Fields worth keeping. The rest of a catalog row (launch flags, notes,
 * publisher bookkeeping) is either re-derived from the live catalog or
 * not ours to cache, and a 30-entry blob of it would eat the quota for
 * nothing. `undefined` is dropped so the shape is stable. */
const KEEP = [
  "game_id",
  "title",
  "provider",
  "category",
  "cover",
  "rtp",
  "demo_url",
  "notes",
];

function storage() {
  try {
    const store = window.localStorage;
    // A private-mode window can expose localStorage and still throw on use.
    const probe = "__casa_probe__";
    store.setItem(probe, "1");
    store.removeItem(probe);
    return store;
  } catch (e) {
    return null;
  }
}

const hasWindow = () => typeof window !== "undefined";

/** The cached game row, trimmed to the fields above. A game with no id is
 * not a game; a game with only an id is a legacy entry and is kept as a
 * bare id so it still orders correctly against the live catalog. */
function trim(game) {
  if (!game || typeof game !== "object" || !game.game_id) return null;
  const out = {};
  for (const field of KEEP) {
    if (game[field] !== undefined && game[field] !== null) out[field] = game[field];
  }
  return out.game_id ? out : null;
}

/** Every stored entry, newest first, deduplicated by id.
 *
 * Accepts both shapes on purpose: v1 entries were `{game_id, ts}` with no
 * `game`, and an upgrade must not throw those away — they still say "this
 * was opened recently", which is the ordering half of the feature.
 *
 * Order comes from `ts`, not from array position. Every writer here appends
 * at the front, but "newest first" should not depend on that staying true:
 * a future writer that appends at the end would silently invert the tab, and
 * a sort makes that impossible. An entry with no usable `ts` sinks to the
 * bottom, which is the honest reading of "we do not know when".
 */
export function readRecent() {
  const store = hasWindow() && storage();
  if (!store) return [];
  let raw;
  try {
    raw = store.getItem(KEY);
  } catch (e) {
    return [];
  }
  // Both the legacy bare array and the current {v, entries} are decoded here,
  // so an upgrade reads what an older build wrote instead of starting blank.
  const parsed = _decode(raw);

  const seen = new Set();
  const out = [];
  for (const entry of parsed) {
    if (!entry || typeof entry !== "object") continue;
    const id = entry.game_id || (entry.game && entry.game.game_id);
    if (!id || seen.has(id)) continue;
    seen.add(id);
    // only a real `game` counts as a cached game: trimming the entry itself
    // would turn an id-only v1 record into a "game" with nothing but an id,
    // which then renders as a blank card instead of being recognised as
    // "ordered, but we do not have it"
    out.push({ game_id: id, ts: Number(entry.ts) || 0, game: trim(entry.game) });
  }
  out.sort((a, b) => b.ts - a.ts);
  return out.slice(0, RECENT_LIMIT);
}

/** Remember that `game` was opened, newest first. Returns the new list. */
export function rememberGame(game) {
  const row = trim(game);
  if (!row) return readRecent();
  const rest = readRecent().filter((r) => r.game_id !== row.game_id);
  const next = [{ game_id: row.game_id, ts: Date.now(), game: row }, ...rest];
  const trimmed = next.slice(0, RECENT_LIMIT);
  write(trimmed);
  return trimmed;
}

function write(entries) {
  const store = hasWindow() && storage();
  if (!store) return;
  try {
    store.setItem(KEY, JSON.stringify({ v: VERSION, entries }));
  } catch (e) {
    /* quota: drop the stored copy of the games and keep only their ids, so
     * the recents survive even when the metadata does not fit */
    try {
      store.setItem(
        KEY,
        JSON.stringify({
          v: 1,
          entries: entries.map((r) => ({ game_id: r.game_id, ts: r.ts })),
        })
      );
    } catch (e2) {
      /* genuinely full: recents degrade to nothing, the lobby does not care */
    }
  }
}

export function clearRecent() {
  const store = hasWindow() && storage();
  if (!store) return;
  try {
    store.removeItem(KEY);
  } catch (e) {}
}

/** Reads a legacy bare-array store (v1) or the current {v, entries}. Both are
 * decoded in one place so the shape change never spreads to the callers, and
 * so an upgrade keeps the ordering an older build wrote. */
export function _decode(raw) {
  if (!raw) return [];
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    return []; // torn write, or a version that wrote something else
  }
  if (Array.isArray(parsed)) return parsed;
  return Array.isArray(parsed && parsed.entries) ? parsed.entries : [];
}
