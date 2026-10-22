import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { amountMinor, clampDeposit, depositAllowed, matchingDepositLimit } from "./money.mjs";

const source = await readFile(new URL("./validation.js", import.meta.url), "utf8");
const { validateCPF, validateCNPJ, formatCPF, formatCNPJ } = await import(
  "data:text/javascript;base64," + Buffer.from(source).toString("base64"));

test("CPF mask and check digits reject repeated, wrong and mixed values", () => {
  assert.equal(formatCPF("52998224725"), "529.982.247-25");
  assert.equal(formatCPF(formatCPF("52998224725")), "529.982.247-25");
  assert.equal(validateCPF("529.982.247-25"), "");
  for (const value of ["111.111.111-11", "529.982.247-26", "x52998224725"])
    assert.ok(validateCPF(value));
});

test("CNPJ mask and checks cover numeric and 2026 alphanumeric documents", () => {
  assert.equal(formatCNPJ("11222333000181"), "11.222.333/0001-81");
  assert.equal(formatCNPJ("00000000e08g12"), "00.000.000/E08G-12");
  for (const value of ["11.222.333/0001-81", "00.000.000/E08G-12"])
    assert.equal(validateCNPJ(value), "");
  for (const value of ["11.222.333/0001-80", "00.000.000/0000-00", "00.000.000/E08G-13"])
    assert.ok(validateCNPJ(value));
});

test("cashier uses exact cents, blocks subminimum amounts and clamps on blur", () => {
  const pix = { min_minor: 500 };
  const crypto = { min_minor: 9934 };
  assert.equal(amountMinor("5,01"), 501);
  assert.equal(amountMinor("0.29"), 29);
  for (const value of ["5garbage", "5.001", "-5", "NaN", "1e3", "", "0"])
    assert.equal(amountMinor(value), null);
  assert.equal(depositAllowed("4.99", pix), false);
  assert.equal(depositAllowed("5.00", pix), true);
  assert.equal(depositAllowed("99.33", crypto), false);
  assert.equal(depositAllowed("99.34", crypto), true);
  assert.equal(depositAllowed("1000", null), false);
  assert.equal(clampDeposit("4.99", pix), "5.00");
  assert.equal(clampDeposit("", crypto), "99.34");
  assert.equal(matchingDepositLimit({ method: "pix", min_minor: 500 }, "crypto", "btc"), null);
  assert.equal(matchingDepositLimit({ method: "crypto", pay_currency: "btc" }, "crypto", "eth"), null);
});
