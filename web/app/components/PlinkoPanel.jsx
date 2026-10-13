"use client";

import { useEffect, useRef, useState } from "react";

const STAKES = [
  [200, "R$2"],
  [500, "R$5"],
  [1000, "R$10"],
  [2500, "R$25"],
];

const SLOTS = [130, 24, 8.1, 2, 0.7, 0.2, 0.2, 0.2, 0.7, 2, 8.1, 24, 130];

/** In-house plinko original: 12 rows, the ball falls left/right into one
 * of 13 slots. The server draws the path (sha256, RTP 97,16%); the board
 * here replays the settled round step by step. */
export default function PlinkoPanel({
  game,
  lastRow,
  win,
  message,
  stake,
  busy,
  onStake,
  onSpin,
  onClose,
}) {
  const [step, setStep] = useState(0);
  const timer = useRef(null);
  const settled = lastRow && lastRow.game_id === "demo:plinko-drops";
  const path = settled ? (lastRow.symbols[0] || "") : "";
  const slot = settled ? parseInt((lastRow.symbols[1] || "slot -1").replace("slot ", ""), 10) : -1;

  useEffect(() => {
    if (timer.current) clearInterval(timer.current);
    setStep(0);
    if (!settled || !path) return;
    timer.current = setInterval(() => {
      setStep((s) => {
        if (s >= 12) {
          clearInterval(timer.current);
          return s;
        }
        return s + 1;
      });
    }, 110);
    return () => timer.current && clearInterval(timer.current);
  }, [settled ? lastRow.round_id : null]); // eslint-disable-line react-hooks/exhaustive-deps

  // fixed 15-column grid; row r shows its r+3 pegs centered.
  // after s moves the ball sits at column 7 + net(s).
  const net = (s) => {
    let c = 0;
    for (let i = 0; i < Math.min(s, path.length); i++) c += path[i] === "R" ? 1 : -1;
    return c;
  };

  return (
    <div id="gameview" style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{game.title}</h2>
        <button className="ghost" style={{ width: "auto" }} onClick={onClose}>
          ✕ Fechar Plinko
        </button>
      </div>
      <div id="cert">Plinko Original · RTP {game.rtp}% · 12 fileiras</div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", margin: "12px 0" }}>
        {Array.from({ length: 12 }, (_, r) => {
          const half = Math.floor((r + 3) / 2);
          return (
            <div key={r} style={{ display: "flex", gap: 12, height: 20, alignItems: "center" }}>
              {Array.from({ length: 15 }, (_, c) => {
                const off = c - 7;
                const showPeg = Math.abs(off) <= half;
                const isBall = settled && step > 0 && step <= 12 && r === step - 1 && off === net(step);
                if (!showPeg && !isBall) return <span key={c} style={{ width: 7, height: 7 }} />;
                return (
                  <span key={c} style={{
                    width: isBall ? 12 : 7, height: isBall ? 12 : 7, borderRadius: "50%",
                    background: isBall ? "#eab308" : "currentColor", opacity: isBall ? 1 : 0.45,
                    display: "inline-block",
                  }} />
                );
              })}
            </div>
          );
        })}
        <div style={{ display: "flex", gap: 4, marginTop: 8 }}>
          {SLOTS.map((m, i) => (
            <div key={i} style={{
              minWidth: 30, textAlign: "center", fontSize: 11, fontWeight: 700,
              padding: "4px 2px", borderRadius: 6,
              background: step >= 12 && i === slot ? "#eab308" : "rgba(127,127,127,.18)",
              color: step >= 12 && i === slot ? "#000" : "inherit",
            }}>
              {m}x
            </div>
          ))}
        </div>
        <div style={{ fontSize: 13, marginTop: 6, opacity: 0.8 }}>
          {settled && step >= 12 ? `slot ${slot} · ${SLOTS[slot]}x` : settled ? "caindo…" : "12 fileiras · bordas pagam 130x"}
        </div>
      </div>
      <div className="stakeRow">
        {STAKES.map(([value, label]) => (
          <button key={value} className={stake === value ? "on" : ""} onClick={() => onStake(value)}>
            {label}
          </button>
        ))}
      </div>
      <button id="spin" disabled={busy} onClick={onSpin}>
        Soltar a bola
      </button>
      <div id="msg" className={win ? "ok" : "err"}>
        {message}
      </div>
      <table className="paytab">
        <tbody>
          <tr><td>Bordas (0 ou 12 desvios)</td><td>130x</td></tr>
          <tr><td>Centro (5–7 desvios)</td><td>0,2x</td></tr>
          <tr><td>RTP do modelo demo</td><td>97,16%</td></tr>
        </tbody>
      </table>
    </div>
  );
}
