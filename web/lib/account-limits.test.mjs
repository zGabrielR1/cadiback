import test from "node:test";
import assert from "node:assert/strict";
import { limitDraft, limitPayload } from "./account-limits.mjs";

test("editing one saved limit preserves the other caps", () => {
  const draft = limitDraft({ deposit_daily_minor: 12025, bet_daily_minor: 9900, session_minutes: 45 });
  draft.deposit_daily_minor = "150,50";
  assert.deepEqual(limitPayload(draft), { deposit_daily_minor: 15050, bet_daily_minor: 9900, session_minutes: 45 });
});

test("decimal conversion uses cents and accepts Portuguese or dot decimals", () => {
  assert.equal(limitPayload({ deposit_daily_minor: "0,29" }).deposit_daily_minor, 29);
  assert.equal(limitPayload({ bet_daily_minor: " 12.3 " }).bet_daily_minor, 1230);
  assert.deepEqual(limitPayload(limitDraft()), { deposit_daily_minor: null, bet_daily_minor: null, session_minutes: null });
});

test("rejects ambiguous amounts, fractional minutes and unsafe values", () => {
  for (const value of ["-1", "0", "1.234", "1e3", "1.000,25", "Infinity", "9007199254740992"]) {
    assert.throws(() => limitPayload({ deposit_daily_minor: value }), undefined, value);
  }
  for (const value of ["1,5", "1.5", "0", "-2", "9007199254740992"]) {
    assert.throws(() => limitPayload({ session_minutes: value }), undefined, value);
  }
});
