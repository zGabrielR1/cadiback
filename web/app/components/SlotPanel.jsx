"use client";

const STAKES = [
  [200, "R$2"],
  [500, "R$5"],
  [1000, "R$10"],
  [2500, "R$25"],
];

// Fallback only — the catalog row carries each game's real
// paytable (decision 0021), so every original shows its own
// tiers instead of one shared paytable.
const PAYTABLE = [
  ["Trinca 7 (jackpot)", "100x"],
  ["Trinca DIAMOND", "15x"],
  ["Trinca BAR", "5x"],
  ["Trinca LEMON", "2x"],
  ["Trinca CHERRY", "1,2x"],
  ["RTP do modelo demo", "95,90% ilustrativo"],
];

function paytableRows(game) {
  if (game && Array.isArray(game.paytable) && game.paytable.length) {
    return game.paytable.map((t) => [
      `${t.symbols.join(" · ")} (${t.name})`,
      `${parseFloat(t.multiplier).toFixed(2).replace(".", ",")}x`,
    ]);
  }
  return PAYTABLE;
}

/** In-house original slot panel (F1 extract from page.jsx): reels, stake
 * row, spin button, message and paytable. The page owns spin/stake. */
export default function SlotPanel({
  game,
  reels,
  win,
  message,
  stake,
  busy,
  onStake,
  onSpin,
  onClose,
}) {
  if (!game) return null;
  const rows = paytableRows(game);
  return (
    <div id="gameview" style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{game.title}</h2>
        <button className="ghost" style={{ width: "auto" }} onClick={onClose}>
          ✕ Fechar Slot
        </button>
      </div>
      <div id="cert">Slot Original · RTP {game.rtp}%</div>
      <div className="reels">
        {reels.map((symbol, i) => (
          <div className={"reel" + (win && i < 3 ? " win" : "")} key={i}>
            {symbol}
          </div>
        ))}
      </div>
      <div className="stakeRow">
        {STAKES.map(([value, label]) => (
          <button
            key={value}
            className={stake === value ? "on" : ""}
            onClick={() => onStake(value)}
          >
            {label}
          </button>
        ))}
      </div>
      <button id="spin" disabled={busy} onClick={onSpin}>
        Girar
      </button>
      <div id="msg" className={win ? "ok" : "err"}>
        {message}
      </div>
      <table className="paytab">
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
