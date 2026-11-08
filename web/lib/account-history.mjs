export function historySummary(rows) {
  const summary = { total: 0, returned: 0, settledStake: 0, pendingStake: 0, pending: 0, net: 0, roi: null };
  for (const row of Array.isArray(rows) ? rows : []) {
    if (!row || typeof row !== "object") continue;
    const stake = Number.isSafeInteger(row.stake_minor) && row.stake_minor >= 0 ? row.stake_minor : 0;
    summary.total += stake;
    if (row.tier === "pendente") {
      summary.pending++;
      summary.pendingStake += stake;
    } else {
      summary.settledStake += stake;
      summary.returned += Number.isSafeInteger(row.payout_minor) && row.payout_minor >= 0 ? row.payout_minor : 0;
    }
  }
  summary.net = summary.returned - summary.settledStake;
  summary.roi = summary.settledStake > 0 ? summary.net / summary.settledStake * 100 : null;
  return summary;
}

export function transactionLabel(kind) {
  return ({ deposit: "Depósito", withdraw: "Retirada", withdrawal_paid: "Retirada concluída",
    bet_placed: "Aposta", bet_settled_win: "Retorno", bet_settled_loss: "Liquidação",
    bet_settled_push: "Aposta anulada", bet_settled_casino: "Retorno do cassino",
    bet_settled_casino_payout: "Retorno do cassino", bonus_grant: "Bônus",
    bonus_convert: "Bônus convertido", adjustment: "Ajuste" })[kind] || "Movimentação";
}

export function filterHistory(rows, { query = "", status = "all" } = {}) {
  const normalize = value => String(value ?? "").normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase("pt-BR");
  const terms = normalize(query).trim().split(/\s+/).filter(Boolean);
  return (Array.isArray(rows) ? rows : []).filter(row => row &&
    (status === "all" || (status === "pending" ? row.tier === "pendente" : row.tier !== "pendente")) &&
    terms.every(term => [row.round_id, row.title, row.game_id].some(value => normalize(value).includes(term))));
}

export function historyCSV(rows) {
  const cell = value => {
    let text = String(value ?? "");
    if (/^[\t\r\n]|^\s*[=+\-@]/.test(text)) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  };
  const money = value => (Number.isFinite(value) ? value / 100 : 0).toFixed(2).replace(".", ",");
  return "\uFEFF" + [
    ["Data", "ID", "Descrição", "Aposta (R$)", "Retorno (R$)", "Resultado"],
    ...rows.map(row => [row.ts || "", row.round_id, row.title || row.game_id,
      money(row.stake_minor), money(row.payout_minor), row.tier]),
  ].map(row => row.map(cell).join(";")).join("\r\n");
}
