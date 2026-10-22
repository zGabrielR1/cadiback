/** Exact centavos, accepting comma or dot decimals, never partial parseFloat. */
export function amountMinor(value) {
  const raw = String(value ?? "").trim();
  if (!/^\d+(?:[.,]\d{1,2})?$/.test(raw)) return null;
  const [whole, fraction = ""] = raw.replace(",", ".").split(".");
  const amount = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return Number.isSafeInteger(amount) && amount > 0 ? amount : null;
}

export function depositAllowed(value, quote) {
  const amount = amountMinor(value);
  return Number.isSafeInteger(quote?.min_minor) && quote.min_minor > 0 &&
    amount !== null && amount >= quote.min_minor;
}

export function clampDeposit(value, quote) {
  if (!Number.isSafeInteger(quote?.min_minor)) return value;
  return (Math.max(quote.min_minor, amountMinor(value) || 0) / 100).toFixed(2);
}

export function matchingDepositLimit(quote, method, coin) {
  if (quote?.method !== method) return null;
  if (method === "crypto" && quote.provider !== "demo" && quote.pay_currency !== coin) return null;
  return quote;
}
