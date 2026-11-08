import { test } from "node:test";
import assert from "node:assert/strict";
import { alertKey, biggestMovers, driftAlerts, priceSnapshot, snapshotPrices } from "./odds-drift.mjs";

const fx = (key, prices) => ({
  key, home: "A", away: "B", competition: "Liga",
  markets: [{ kind: "1x2", selections: ["1", "X", "2"], prices }],
});

test("snapshot keys every valid selection", () => {
  const snap = priceSnapshot(fx("k1", [2.1, 3.2, 3.5]));
  assert.equal(snap.size, 3);
  assert.deepEqual([...snap.values()], [2.1, 3.2, 3.5]);
});

test("drift only reports changed picks, biggest move first", () => {
  const prev = snapshotPrices([fx("k1", [2.0, 3.0, 3.0])]);
  const next = snapshotPrices([fx("k1", [2.2, 2.9, 3.0])]);
  const alerts = driftAlerts(prev, next, { fixtures: [fx("k1", [2.2, 2.9, 3.0])] });
  assert.equal(alerts.length, 2);
  assert.equal(alerts[0].direction, "up");
  assert.equal(alerts[0].before, 2.0);
  assert.equal(alerts[0].after, 2.2);
  assert.equal(alerts[0].deltaPct, 10);
  assert.equal(alerts[1].direction, "down");
});

test("threshold filters small moves and unknown picks are ignored", () => {
  const prev = snapshotPrices([fx("k1", [2.0, 3.0, 3.0])]);
  const next = snapshotPrices([fx("k1", [2.02, 3.0, 3.0]), fx("k2", [9.0, 9.0, 9.0])]);
  assert.equal(driftAlerts(prev, next, { threshold: 2 }).length, 0);
  assert.equal(biggestMovers(prev, next).length, 1);
});

test("alert keys are stable and snapshot tolerates junk", () => {
  const a = { id: "x", after: 2.5 };
  assert.equal(alertKey(a), "x@2.5");
  assert.equal(snapshotPrices(null).size, 0);
  assert.equal(snapshotPrices([null, { key: "z" }]).size, 0);
  assert.deepEqual(driftAlerts(null, null), []);
});
