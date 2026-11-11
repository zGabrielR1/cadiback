export const LIMIT_FIELDS = ["deposit_daily_minor", "bet_daily_minor", "session_minutes"];

export function limitDraft(limits = {}) {
  return Object.fromEntries(LIMIT_FIELDS.map(key => {
    const value = limits[key];
    return [key, value == null ? "" : key === "session_minutes" ? String(value) : (value / 100).toFixed(2).replace(".", ",")];
  }));
}

export function limitPayload(draft) {
  return Object.fromEntries(LIMIT_FIELDS.map(key => {
    const value = String(draft[key] ?? "").trim();
    if (!value) return [key, null];
    const minutes = key === "session_minutes";
    if (!(minutes ? /^\d+$/ : /^\d+(?:[.,]\d{1,2})?$/).test(value)) {
      throw new Error(minutes ? "Informe o tempo em minutos inteiros." : "Informe um valor em reais com até duas casas decimais, como 50,00.");
    }
    const [whole, fraction = ""] = value.replace(",", ".").split(".");
    const amount = minutes ? Number(whole) : Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
    if (!Number.isSafeInteger(amount) || amount <= 0) throw new Error("Os limites devem ser maiores que zero. Deixe vazio para remover um limite.");
    return [key, amount];
  }));
}
