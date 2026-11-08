// In-app odds drift alerts + live odds ticker (pure helpers, no I/O).
//
// Favorites are stored per browser; the server never hears about them. On
// every feed refresh the board compares the previously shown price of each
// *favorited* selection with the new one and surfaces moves as in-app notes
// (no push, no email, no spam). Same helper powers the "biggest movers"
// ticker shown to everyone, favorited or not.

import { validMarkets, betIdentity } from "./sports.mjs";

/** Price snapshot for one fixture: identity -> price. */
export function priceSnapshot(fixture) {
  const out = new Map();
  for (const market of validMarkets(fixture)) {
    market.selections.forEach((selection, i) => {
      const bet = {
        fixtureKey: fixture.key,
        marketKind: market.kind,
        line: market.line,
        selection,
      };
      out.set(betIdentity(bet), market.prices[i]);
    });
  }
  return out;
}

/** Snapshot of several fixtures (board state). */
export function snapshotPrices(fixtures) {
  const out = new Map();
  for (const fixture of Array.isArray(fixtures) ? fixtures : []) {
    for (const [id, price] of priceSnapshot(fixture)) out.set(id, price);
  }
  return out;
}

/**
 * Compare two snapshots into drift alerts, biggest absolute move first.
 * options: { threshold = 0 (any move), limit = 20, fixtures (for labels) }
 */
export function driftAlerts(previous, next, { threshold = 0, limit = 20, fixtures = [] } = {}) {
  if (!(previous instanceof Map) || !(next instanceof Map)) return [];
  const labels = new Map();
  for (const f of Array.isArray(fixtures) ? fixtures : []) {
    for (const [id] of priceSnapshot(f)) {
      labels.set(id, { home: f.home, away: f.away, competition: f.competition });
    }
  }
  const alerts = [];
  for (const [id, after] of next) {
    const before = previous.get(id);
    if (typeof before !== "number" || !Number.isFinite(before) || before <= 0) continue;
    if (typeof after !== "number" || !Number.isFinite(after) || after <= 0) continue;
    const deltaPct = ((after - before) / before) * 100;
    if (deltaPct === 0 || Math.abs(deltaPct) < threshold) continue;
    const label = labels.get(id) || {};
    alerts.push({
      id,
      home: label.home || "?",
      away: label.away || "?",
      competition: label.competition || "",
      before,
      after,
      direction: after > before ? "up" : "down",
      deltaPct: Math.round(deltaPct * 10) / 10,
    });
  }
  alerts.sort((a, b) => Math.abs(b.deltaPct) - Math.abs(a.deltaPct));
  return alerts.slice(0, limit);
}

/** Biggest movers across the whole board (the live ticker). */
export function biggestMovers(previous, next, { limit = 3, fixtures = [] } = {}) {
  return driftAlerts(previous, next, { limit, fixtures });
}

/** Stable alert identity for dismissal ("seen") tracking. */
export function alertKey(alert) {
  return `${alert.id}@${alert.after}`;
}
