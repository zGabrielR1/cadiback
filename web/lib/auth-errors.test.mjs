import test from "node:test";
import assert from "node:assert/strict";
import { socialErrorMessage } from "./auth-errors.mjs";
test("provider errors give a recovery action without reflecting raw details", () => {
  assert.match(socialErrorMessage("state_mismatch"), /expirou/);
  assert.match(socialErrorMessage("access_denied"), /não foi autorizado/);
  assert.doesNotMatch(socialErrorMessage("secret diagnostic detail"), /secret/);
  assert.match(socialErrorMessage(), /Tente novamente/);
});
