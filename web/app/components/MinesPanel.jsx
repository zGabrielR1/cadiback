"use client";

const STAKES = [
  [200, "R$2"],
  [500, "R$5"],
  [1000, "R$10"],
  [2500, "R$25"],
];

const MINE_CHOICES = [1, 3, 5, 10, 15];

/** In-house mines original: a 5x5 field hides `mines` bombs (sha256 draw,
 * RTP 97%). Pick safe houses; one bomb loses everything, a clean sheet
 * pays the survival odds minus the edge. */
export default function MinesPanel({
  game,
  mines,
  onMines,
  picks,
  onPicks,
  lastRow,
  win,
  message,
  stake,
  busy,
  onStake,
  onSpin,
  onClose,
}) {
  const settled = lastRow && lastRow.game_id === "demo:minas";
  const revealed = {};
  if (settled) {
    for (const s of lastRow.symbols) {
      if (s.startsWith("minas:")) for (const c of s.slice(6).split(",")) revealed[parseInt(c, 10)] = "mina";
      if (s.startsWith("picks:")) for (const c of s.slice(6).split(",")) {
        const n = parseInt(c, 10);
        if (!revealed[n]) revealed[n] = "limpa";
      }
    }
  }

  const toggle = (n) => {
    if (settled && Object.keys(revealed).length) return;
    onPicks(picks.includes(n) ? picks.filter((p) => p !== n) : [...picks, n].slice(0, 25 - mines));
  };

  return (
    <div id="gameview" style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{game.title}</h2>
        <button className="ghost" style={{ width: "auto" }} onClick={onClose}>
          ✕ Fechar Minas
        </button>
      </div>
      <div id="cert">Minas Original · RTP {game.rtp}% · campo 5x5</div>
      <div className="stakeRow" style={{ marginTop: 10 }}>
        <span style={{ alignSelf: "center", fontSize: 13, opacity: 0.8 }}>Minas:</span>
        {MINE_CHOICES.map((m) => (
          <button key={m} className={mines === m ? "on" : ""} onClick={() => { onMines(m); onPicks([]); }}>
            {m}
          </button>
        ))}
      </div>
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8,
        maxWidth: 340, margin: "12px auto",
      }}>
        {Array.from({ length: 25 }, (_, i) => {
          const n = i + 1;
          const state = revealed[n];
          const picked = picks.includes(n);
          return (
            <button
              key={n}
              onClick={() => toggle(n)}
              style={{
                aspectRatio: "1", fontSize: 20, borderRadius: 10,
                background: state === "mina" ? "#5a1010" : state === "limpa" ? "#14532d" : picked ? "var(--acc-soft, #1e293b)" : undefined,
                border: picked && !state ? "2px solid var(--acc, #22c55e)" : undefined,
                cursor: "pointer",
              }}
            >
              {state === "mina" ? "💣" : state === "limpa" ? "💎" : picked ? "·" : ""}
            </button>
          );
        })}
      </div>
      <div style={{ textAlign: "center", fontSize: 13, opacity: 0.8 }}>
        {settled
          ? (win ? `limpo! ${lastRow.multiplier}x` : lastRow.tier)
          : `${picks.length} casa(s) · ${25 - mines} seguras no campo`}
      </div>
      <div className="stakeRow">
        {STAKES.map(([value, label]) => (
          <button key={value} className={stake === value ? "on" : ""} onClick={() => onStake(value)}>
            {label}
          </button>
        ))}
      </div>
      <button id="spin" disabled={busy || picks.length === 0} onClick={onSpin}>
        Revelar ({picks.length || "—"})
      </button>
      <div id="msg" className={win ? "ok" : "err"}>
        {message}
      </div>
      <table className="paytab">
        <tbody>
          <tr><td>Ficha limpa (3 minas, 3 casas)</td><td>~1,45x</td></tr>
          <tr><td>Qualquer mina revelada</td><td>perde</td></tr>
          <tr><td>RTP do modelo demo</td><td>97,00%</td></tr>
        </tbody>
      </table>
    </div>
  );
}
