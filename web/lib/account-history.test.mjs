import test from "node:test";
import assert from "node:assert/strict";
import { filterHistory, historyCSV, transactionLabel, historySummary } from "./account-history.mjs";
test("history filtering preserves rows, identities and outcome amounts", () => {
  const rows = [{ round_id: "a", title: "Flamengo", tier: "pendente", stake_minor: 123 },
    { round_id: "b", title: "Santos", tier: "vitoria", payout_minor: 300 }];
  assert.deepEqual(filterHistory(rows, { query: "FLAM", status: "pending" }), [rows[0]]);
  assert.deepEqual(filterHistory(rows, { status: "settled" }), [rows[1]]);
  assert.equal(rows.length, 2);
});
test("CSV escapes quoted labels, formula text and exact minor amounts", () => {
  const csv = historyCSV([{ round_id: "=BAD()", title: 'Casa "A"; Fora', ts: "2026-11-06", stake_minor: 123, payout_minor: 456, tier: "pendente" }]);
  assert.match(csv, /'\=BAD/);
  assert.ok(csv.includes('"Casa ""A""; Fora"'));
  assert.ok(csv.includes('"1,23";"4,56"'));
});
test("history search matches accents and case without changing displayed labels", () => {
  const row = { round_id: "pix-42", title: "São Paulo × Grêmio", tier: "vitoria" };
  assert.deepEqual(filterHistory([row], { query: " SAO PAULO " }), [row]);
  assert.deepEqual(filterHistory([row], { query: "gremio" }), [row]);
  assert.deepEqual(filterHistory([row], { query: "GRÊMIO" }), [row]);
  assert.deepEqual(filterHistory([row], { query: "pix-42" }), [row]);
  assert.deepEqual(filterHistory([row], { query: "gremio", status: "pending" }), []);
  assert.equal(row.title, "São Paulo × Grêmio");
});
test("history search accepts words in any order across title and reference", () => {
  const row = { round_id: "bet-42", title: "São Paulo × Grêmio", tier: "pendente" };
  for (const query of ["gremio sao", "paulo   gremio", "42 gremio", "   "]) {
    assert.deepEqual(filterHistory([row], { query }), [row]);
  }
  assert.deepEqual(filterHistory([row], { query: "gremio santos" }), []);
});

test("wallet activity labels recognize actual posting kinds", () => {
  assert.equal(transactionLabel("bet_placed"), "Aposta");
  assert.equal(transactionLabel("bet_settled_win"), "Retorno");
  assert.equal(transactionLabel("bet_settled_loss"), "Liquidação");
  assert.equal(transactionLabel("bet_settled_push"), "Aposta anulada");
  assert.equal(transactionLabel("bonus_convert"), "Bônus convertido");
  assert.equal(transactionLabel("unknown"), "Movimentação");
});

test("pending stakes are excluded from settled net and ROI", () => {
  const result = historySummary([
    { tier: "pendente", stake_minor: 500, payout_minor: 9999 },
    { tier: "vitoria", stake_minor: 200, payout_minor: 400 },
    { tier: "derrota", stake_minor: 100, payout_minor: 0 },
  ]);
  assert.deepEqual(result, { total: 800, returned: 400, settledStake: 300,
    pendingStake: 500, pending: 1, net: 100, roi: 100 / 300 * 100 });
});
test("empty and pending-only histories have no settled ROI", () => {
  assert.equal(historySummary([]).roi, null);
  const result = historySummary([{ tier: "pendente", stake_minor: 200 }]);
  assert.equal(result.net, 0);
  assert.equal(result.roi, null);
  assert.equal(result.pendingStake, 200);
});
test("refunds and malformed amounts do not corrupt the summary", () => {
  assert.equal(historySummary([{ tier: "anulada", stake_minor: 200, payout_minor: 200 }]).net, 0);
  assert.equal(historySummary([null, { stake_minor: "200", payout_minor: Infinity }]).total, 0);
});

test("CSV neutralizes formula prefixes hidden behind whitespace and preserves Unicode", () => {
  for (const title of [" =SUM(A1)", "  +1", "\n=BAD()", "\t@BAD()", "\r-1"]) {
    const csv = historyCSV([{ round_id: "id", title, stake_minor: 100, payout_minor: 0 }]);
    assert.ok(csv.includes(`"'${title}"`));
  }
  const csv = historyCSV([{ title: "São Paulo\nGrêmio", stake_minor: 100, payout_minor: 0 }]);
  assert.ok(csv.startsWith("\uFEFF"));
  assert.ok(csv.includes('"São Paulo\nGrêmio"'));
});
