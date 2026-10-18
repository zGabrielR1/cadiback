"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const STAKES = [[200, "R$2"], [500, "R$5"], [1000, "R$10"], [2500, "R$25"]];

// Mirrors demo/arcade.py WHEEL_LADDER: (multiplier, count) over 100 equal
// sectors that sum to exactly 97, i.e. a 97% RTP by construction.
const LADDER = [
  [0, 54], [0.5, 12], [1, 6], [1.5, 12], [2, 10], [3, 4], [10, 1], [25, 1],
];

const NS = 100;
const DEG = 360 / NS;

const SECTORS = LADDER.flatMap(([mult, count]) =>
  Array.from({ length: count }, () => mult));

const COLOR = {
  0: "#1e2530",
  0.5: "#2f3a49",
  1: "#2563eb",
  1.5: "#16a34a",
  2: "#eab308",
  3: "#f97316",
  10: "#ec4899",
  25: "#a855f7",
};

const cx = 170;
const cy = 170;
const r = 156;

function wedge(startDeg, endDeg) {
  const a0 = ((startDeg - 90) * Math.PI) / 180;
  const a1 = ((endDeg - 90) * Math.PI) / 180;
  const x0 = cx + r * Math.cos(a0);
  const y0 = cy + r * Math.sin(a0);
  const x1 = cx + r * Math.cos(a1);
  const y1 = cy + r * Math.sin(a1);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${cx} ${cy} L ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)} Z`;
}

function sectorOf(landed) {
  // the row carries ["setor N", "Mx"]; N is 1-based.
  const label = landed && landed.symbols && landed.symbols[0];
  const n = parseInt(String(label || "").replace(/\D+/g, ""), 10);
  if (Number.isFinite(n) && n >= 1 && n <= NS) return n - 1;
  if (landed && typeof landed.unit === "number") {
    return Math.min(NS - 1, Math.floor(landed.unit * NS));
  }
  return null;
}

export default function WheelPanel({ game, lastRow, win, message, stake, busy, onStake, onSpin, onClose }) {
  const landed = lastRow && lastRow.game_id === game.game_id ? lastRow : null;
  const sector = landed ? sectorOf(landed) : null;
  const [spinCount, setSpinCount] = useState(0);
  const [rotation, setRotation] = useState(0);
  const lastRound = useRef(null);

  useEffect(() => {
    if (!landed || landed.round_id === lastRound.current) return;
    lastRound.current = landed.round_id;
    const s = sectorOf(landed) ?? 0;
    setSpinCount((n) => {
      const turns = 5 * (n + 1);
      // bring sector s (its centre) under the pointer at the top
      setRotation(turns * 360 - (s + 0.5) * DEG);
      return n + 1;
    });
  }, [landed]);

  const wedges = useMemo(
    () => SECTORS.map((mult, i) => (
      <path key={i} d={wedge(i * DEG, (i + 1) * DEG)}
        fill={COLOR[mult] ?? "#334155"} stroke="#0b0e13" strokeWidth="0.4" />
    )),
    []);

  const mult = landed ? Number(landed.multiplier) : null;
  const highlight = landed && win ? "#22c55e" : "#ef4444";

  return (
    <div id="gameview" style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{game.title}</h2>
        <button className="ghost" style={{ width: "auto" }} onClick={onClose}>Fechar roda</button>
      </div>
      <div id="cert">Roda Original · RTP {game.rtp}% · 100 setores</div>

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center", margin: "16px 0" }}>
        <div style={{ position: "relative", width: 340, height: 340 }}>
          <svg width="340" height="340" viewBox="0 0 340 340"
            style={{
              transform: `rotate(${rotation}deg)`,
              transition: "transform 2.6s cubic-bezier(.17,.67,.2,1)",
            }}>
            <circle cx={cx} cy={cy} r={r + 6} fill="#0b0e13" />
            {wedges}
            <circle cx={cx} cy={cy} r={26} fill="#0b0e13" stroke="#334155" strokeWidth="2" />
          </svg>
          <div style={{
            position: "absolute", top: -2, left: "50%", transform: "translateX(-50%)",
            width: 0, height: 0, borderLeft: "10px solid transparent",
            borderRight: "10px solid transparent", borderTop: "18px solid #e2e8f0",
            filter: "drop-shadow(0 1px 2px rgba(0,0,0,.6))",
          }} />
        </div>

        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={{ fontSize: 46, fontWeight: 800, color: landed ? highlight : "var(--mut)" }}>
            {landed ? Number(mult).toFixed(2) + "x" : "—"}
          </div>
          <div style={{ fontSize: 13, opacity: 0.85, minHeight: 18 }}>
            {landed ? (landed.symbols[0] + " · " + landed.tier) : "gire a roda"}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
            {LADDER.map(([m, c]) => (
              <span key={m} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12 }}>
                <i style={{ width: 11, height: 11, borderRadius: 3, background: COLOR[m], display: "inline-block" }} />
                {m === 0 ? "perde" : `${m}x`}
                <span style={{ color: "var(--mut)" }}>{c}</span>
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="stakeRow">
        {STAKES.map(([v, label]) => (
          <button key={v} className={stake === v ? "on" : ""} onClick={() => onStake(v)}>
            {label}
          </button>
        ))}
      </div>
      <button id="spin" disabled={busy} onClick={onSpin}>Girar a roda</button>
      <div id="msg" className={win ? "ok" : "err"}>{message}</div>
    </div>
  );
}
