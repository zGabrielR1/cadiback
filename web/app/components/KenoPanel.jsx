"use client";

import { BRL } from "../../lib/api";

const STAKES = [
  [200, "R$2"],
  [500, "R$5"],
  [1000, "R$10"],
  [2500, "R$25"],
];

const POOL = 80;
const DRAWN = 20;
const MAX_SPOTS = 10;
const KEEP = 0.97; // house keep, same 3% edge as the rest of the originals
const SCALE = 10000; // the ladder is snapped to four decimals (see demo/arcade.py)

/** P(exactly `hits` of `spots` picked numbers are drawn), exactly.
 *
 * Hypergeometric, in doubles instead of Fractions — the display only needs
 * the shape of the ladder, and the number that has to be right (the payout)
 * is computed by the server. Mirrors `keno_hit_probability`. */
function hitProbability(spots, hits) {
  if (hits < 0 || hits > spots) return 0;
  const missed = DRAWN - hits;
  const unseen = POOL - spots;
  if (missed < 0 || missed > unseen) return 0;
  const choose = (n, k) => {
    if (k < 0 || k > n) return 0;
    let r = 1;
    for (let i = 0; i < k; i++) r = (r * (n - i)) / (i + 1);
    return r;
  };
  return (choose(spots, hits) * choose(unseen, missed)) / choose(POOL, DRAWN);
}

const snap = (v) => Math.round(v * SCALE) / SCALE;

/** The payout ladder for a spot count: each extra hit doubles, then the
 * whole ladder is scaled so its expected return is exactly 97%.
 *
 * This mirrors `arcade.keno_paytable` — same weights, same eight settling
 * passes, same snap. The server computes what is actually paid; this exists
 * so the table on screen is the table that pays. */
export function paytable(spots) {
  const tiers = [];
  for (let k = 1; k <= spots; k++) tiers.push(k);
  let ladder = {};
  for (const k of tiers) {
    ladder[k] = snap(KEEP * Math.pow(2, k - 1));
  }
  for (let pass = 0; pass < 8; pass++) {
    let total = 0;
    for (const k of tiers) total += hitProbability(spots, k) * ladder[k];
    if (!total) return {};
    for (const k of tiers) {
      ladder[k] = Math.max(0.0001, snap((ladder[k] / total) * KEEP));
    }
  }
  return ladder;
}

/** What this exact pick is worth if it lands now, and the best it could pay. */
function outcome(spots, picks) {
  const table = paytable(spots);
  let top = 0;
  for (let h = 1; h <= spots; h++) {
    const mult = table[h] || 0;
    if (mult > top) top = mult;
  }
  return { table, top };
}

export default function KenoPanel({
  game,
  spots,
  onSpots,
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
  const settled = lastRow && lastRow.game_id === "demo:keno";
  const drawn = settled ? (lastRow.symbols[0] || "").split(",").filter(Boolean).map(Number) : [];
  const hitNumbers = settled ? (lastRow.symbols[1] || "").split(",").filter(Boolean).map(Number) : [];
  const hits = settled ? hitNumbers.length : null;
  const paid = settled && lastRow.multiplier !== "0" && hits > 0;
  const partial = paid && Number(lastRow.multiplier) < 1;

  const { table, top } = outcome(spots, picks);
  const potential = Math.round(stake * top);

  const toggle = (n) => {
    if (picks.includes(n)) {
      onPicks(picks.filter((p) => p !== n));
    } else if (picks.length < spots) {
      onPicks([...picks, n].sort((a, b) => a - b));
    }
  };

  // quick picks: a random legal set, so a player can try a spot count without
  // hunting for numbers by hand. Random, never seeded — this is the player's
  // choice, not a draw.
  const quickPick = () => {
    const deck = Array.from({ length: POOL }, (_, i) => i + 1);
    for (let i = deck.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [deck[i], deck[j]] = [deck[j], deck[i]];
    }
    onPicks(deck.slice(0, spots).sort((a, b) => a - b));
  };

  const cellState = (n) => {
    const isPick = picks.includes(n);
    const isHit = hitNumbers.includes(n);
    const isDrawn = drawn.includes(n);
    if (!settled) return isPick ? "kenoCell kenoPick" : "kenoCell";
    if (isHit) return "kenoCell kenoHit";
    if (isPick) return "kenoCell kenoMiss";
    if (isDrawn) return "kenoCell kenoDrawn";
    return "kenoCell kenoIdle";
  };

  return (
    <div id="gameview" style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{game.title}</h2>
        <button className="ghost" style={{ width: "auto" }} onClick={onClose}>
          ✕ Fechar Keno
        </button>
      </div>
      <div id="cert">
        Keno Original · RTP {game.rtp}% · edge 3% · 20 de 80 números
      </div>

      {settled ? (
        <div style={{ textAlign: "center", margin: "12px 0 2px" }}>
          <div style={{
            fontSize: 40, fontWeight: 800,
            color: paid ? (partial ? "#f59e0b" : "#22c55e") : "#ef4444",
          }}>
            {hits} / {spots}
          </div>
          <div style={{ fontSize: 13, opacity: 0.8 }}>
            {paid
              ? `${partial ? "retorno parcial" : "prêmio"} ${Number(lastRow.multiplier).toFixed(2)}x · ${BRL(lastRow.payout_minor)}`
              : "sem prêmio nesta rodada"}
          </div>
        </div>
      ) : (
        <div style={{ textAlign: "center", margin: "12px 0 2px" }}>
          <div style={{ fontSize: 40, fontWeight: 800 }}>
            {picks.length}<span style={{ fontSize: 20, opacity: 0.6 }}>/{spots}</span>
          </div>
          <div style={{ fontSize: 13, opacity: 0.8 }}>números marcados</div>
        </div>
      )}

      <div className="stakeRow" style={{ marginTop: 8, flexWrap: "wrap" }}>
        {Array.from({ length: MAX_SPOTS }, (_, i) => i + 1).map((s) => (
          <button key={s} className={spots === s ? "on" : ""}
            onClick={() => { onSpots(s); if (picks.length > s) onPicks(picks.slice(0, s)); }}>
            {s}
          </button>
        ))}
      </div>

      <div style={{
        display: "grid", gridTemplateColumns: "repeat(10, 1fr)", gap: 4,
        maxWidth: 520, margin: "10px auto",
      }}>
        {Array.from({ length: POOL }, (_, i) => i + 1).map((n) => (
          <button
            key={n}
            className={cellState(n)}
            disabled={busy || (!picks.includes(n) && picks.length >= spots)}
            onClick={() => toggle(n)}
            aria-pressed={picks.includes(n)}
          >
            {n}
          </button>
        ))}
      </div>

      <div style={{ textAlign: "center" }}>
        <button className="ghost" style={{ width: "auto" }} onClick={quickPick} disabled={busy}>
          Sortear {spots} números
        </button>
      </div>

      <div className="stakeRow">
        {STAKES.map(([value, label]) => (
          <button key={value} className={stake === value ? "on" : ""} onClick={() => onStake(value)}>
            {label}
          </button>
        ))}
      </div>
      <button id="spin" disabled={busy || picks.length !== spots} onClick={onSpin}>
        Sortear 20 números
      </button>
      <div id="msg" className={win ? "ok" : "err"}>
        {message}
      </div>

      <table className="paytab">
        <thead>
          <tr>
            <th>acertos</th>
            {Object.keys(table).map((k) => <th key={k}>{k}</th>)}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>paga</td>
            {Object.keys(table).map((k) => (
              <td key={k}>{Number(table[k]).toFixed(2)}x</td>
            ))}
          </tr>
          <tr>
            <td>chance</td>
            {Object.keys(table).map((k) => (
              <td key={k}>{(hitProbability(spots, Number(k)) * 100).toFixed(2)}%</td>
            ))}
          </tr>
        </tbody>
      </table>
      <div style={{ textAlign: "center", fontSize: 12, opacity: 0.75, marginTop: 6 }}>
        prêmio máximo com {spots} número(s): {top.toFixed(2)}x · {BRL(potential)} · RTP do
        modelo 97,00%
      </div>
    </div>
  );
}
