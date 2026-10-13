"use client";

import { BRL } from "../../lib/api";

const STAKES = [
  [200, "R$2"],
  [500, "R$5"],
  [1000, "R$10"],
  [2500, "R$25"],
];

const GRID = 10000; // the roll grid: 0.00 .. 99.99, one sha256 draw
const KEEP = 0.97; // house keep, same 3% edge as the arcade trio

/** The selection's win chance over the 0.01 roll grid, mirroring the
 * engine: under wins on rolls below the target, over wins above it. */
function winChance(over, target) {
  const h = Math.round((Number(target) || 0) * 100);
  const wins = over ? GRID - h - 1 : h;
  return Math.max(0, wins) / GRID;
}

/** In-house dice original: one draw trims to a 0.01 roll, and the player
 * picks under/over a target. A win pays 0.97 / P(win), which can land
 * below the stake on a high-probability bet — that is dice, not a bug. */
export default function DicePanel({
  game,
  target,
  onTarget,
  over,
  onOver,
  lastRow,
  win,
  message,
  stake,
  busy,
  onStake,
  onSpin,
  onClose,
}) {
  const settled = lastRow && lastRow.game_id === "demo:dados";
  const roll = settled ? parseFloat(lastRow.symbols[0]) : null;
  const won = settled && lastRow.multiplier !== "0";

  const p = winChance(over, target);
  const mult = p > 0 ? KEEP / p : 0;
  const potential = Math.round(stake * mult);

  const dir = over ? "acima de" : "abaixo de";

  return (
    <div id="gameview" style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{game.title}</h2>
        <button className="ghost" style={{ width: "auto" }} onClick={onClose}>
          ✕ Fechar Dados
        </button>
      </div>
      <div id="cert">Dados Original · RTP {game.rtp}% · edge 3% · rolagem 0,00–99,99</div>

      <div style={{ textAlign: "center", margin: "14px 0 4px" }}>
        <div style={{
          fontSize: 44, fontWeight: 800,
          color: settled ? (won ? "#22c55e" : "#ef4444") : "inherit",
        }}>
          {settled ? Number(roll).toFixed(2) : Number(target || 0).toFixed(2)}
        </div>
        <div style={{ fontSize: 13, opacity: 0.75 }}>
          {settled
            ? `rolou ${Number(roll).toFixed(2)} · ${dir} ${Number(target).toFixed(2)}`
            : `${dir} ${Number(target || 0).toFixed(2)}`}
        </div>
      </div>

      <div className="stakeRow" style={{ marginTop: 10 }}>
        <button className={over ? "" : "on"} onClick={() => onOver(false)}>
          Abaixo de
        </button>
        <button className={over ? "on" : ""} onClick={() => onOver(true)}>
          Acima de
        </button>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 10 }}>
        <input
          type="range"
          min="1"
          max="99"
          step="1"
          aria-label="Alvo"
          value={Math.min(99, Math.max(1, Math.round(Number(target) || 50)))}
          onChange={(e) => onTarget(e.target.value)}
          style={{ flex: 1 }}
        />
        <input
          inputMode="decimal"
          aria-label="Alvo (número)"
          value={target}
          onChange={(e) => onTarget(e.target.value)}
          style={{ width: 76, textAlign: "center" }}
        />
      </div>

      <div style={{ textAlign: "center", fontSize: 13, opacity: 0.85, marginTop: 6 }}>
        chance {(p * 100).toFixed(2)}% · pagamento {mult.toFixed(2)}x · ganho {BRL(potential)}
      </div>

      <div className="stakeRow">
        {STAKES.map(([value, label]) => (
          <button key={value} className={stake === value ? "on" : ""} onClick={() => onStake(value)}>
            {label}
          </button>
        ))}
      </div>
      <button id="spin" disabled={busy} onClick={onSpin}>
        Rolar dados
      </button>
      <div id="msg" className={win ? "ok" : "err"}>
        {message}
      </div>
      <table className="paytab">
        <tbody>
          <tr><td>Rolagem abaixo/acima do alvo</td><td>0,97 ÷ chance</td></tr>
          <tr><td>Alvo com 50% de chance</td><td>1,94x</td></tr>
          <tr><td>Alvo extremo (1% ou 99%)</td><td>~0,98x – 97x</td></tr>
          <tr><td>RTP do modelo demo</td><td>97,00%</td></tr>
        </tbody>
      </table>
    </div>
  );
}
