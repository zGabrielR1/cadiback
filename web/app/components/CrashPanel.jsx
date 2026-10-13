"use client";

import { useEffect, useRef, useState } from "react";
import { api, BRL } from "../../lib/api";

const STAKES = [
  [200, "R$2"],
  [500, "R$5"],
  [1000, "R$10"],
  [2500, "R$25"],
];

const TARGETS = ["1.50", "2.00", "5.00", "10.00"];

const POLL_MS = 300;
const TICK_MS = 50;

/** In-house crash original, two ways to play.
 *
 * Manual (the default): the curve climbs in real time and the player
 * cashes out at any instant; the server holds the secret bust and pays
 * stake x the multiplier its clock shows at the click. Auto: name a
 * target and the settled round replays. Both draw the bust from the same
 * sha256 discipline (RTP 97%), so the two modes share one paytable. */
export default function CrashPanel({
  game,
  stake,
  busy,
  onStake,
  onClose,
  target,
  onTarget,
  lastRow,
  win,
  message,
  onSpin,
  player,
  onRefresh,
  onNeedAccount,
}) {
  const [mode, setMode] = useState("manual");

  // -- manual (live) round state
  const [phase, setPhase] = useState("idle"); // idle | flying | cashed | busted
  const [round, setRound] = useState(null); // {token, growth, base, t0, max}
  const [live, setLive] = useState(1.0);
  const [result, setResult] = useState(null); // {win, multiplier, bust, payout_minor}
  const [err, setErr] = useState("");
  const [starting, setStarting] = useState(false);

  const setStake = (value) => {
    if (phase === "flying") return; // stake is locked once the plane is up
    onStake(value);
  };

  const start = async () => {
    if (!player) {
      if (onNeedAccount) onNeedAccount();
      return;
    }
    setErr("");
    setResult(null);
    setPhase("idle");
    setStarting(true);
    try {
      const r = await api("POST", "/api/crash/start", {
        player,
        stake_minor: stake,
      });
      const base = Math.max(0, (r.server_now || 0) - (r.started_at || 0));
      setRound({
        token: r.token,
        growth: r.growth,
        max: r.max_multiplier,
        base,
        t0: performance.now(),
      });
      setLive(1.0);
      setPhase("flying");
    } catch (e) {
      setErr(e.message);
    } finally {
      setStarting(false);
    }
  };

  const cashout = async () => {
    if (!round) return;
    try {
      const r = await api("POST", "/api/crash/cashout", {
        player,
        token: round.token,
      });
      setLive(r.win ? r.multiplier : r.bust);
      setResult(r);
      setPhase(r.win ? "cashed" : "busted");
      setRound(null);
      if (onRefresh) onRefresh();
    } catch (e) {
      setErr(e.message);
    }
  };

  // climb the curve locally while flying (server clock, growth aligned at start)
  useEffect(() => {
    if (phase !== "flying" || !round) return undefined;
    const id = setInterval(() => {
      const elapsed = round.base + (performance.now() - round.t0) / 1000;
      setLive(Math.min(round.max, Math.exp(round.growth * elapsed)));
    }, TICK_MS);
    return () => clearInterval(id);
  }, [phase, round]);

  // ask the server whether the plane is still up; on a bust it settles the loss
  useEffect(() => {
    if (phase !== "flying" || !round) return undefined;
    const id = setInterval(async () => {
      try {
        const s = await api("POST", "/api/crash/status", {
          token: round.token,
        });
        if (s.status === "busted") {
          setLive(s.bust);
          setResult(s);
          setPhase("busted");
          setRound(null);
          if (onRefresh) onRefresh();
        } else if (s.status === "unknown") {
          setErr("voo encerrado no servidor");
          setPhase("idle");
          setRound(null);
        }
      } catch (e) {
        /* transient poll failure: the local curve keeps climbing */
      }
    }, POLL_MS);
    return () => clearInterval(id);
  }, [phase, round]); // eslint-disable-line react-hooks/exhaustive-deps

  // -- auto (target) round replay, unchanged from the original panel
  const [shown, setShown] = useState(1.0);
  const timer = useRef(null);
  useEffect(() => {
    if (timer.current) clearInterval(timer.current);
    if (!lastRow || lastRow.game_id !== "demo:crash-nitro") {
      setShown(1.0);
      return undefined;
    }
    const bust = parseFloat((lastRow.symbols[0] || "1x").replace("x", "")) || 1.0;
    const cash = lastRow.payout_minor > 0
      ? parseFloat((lastRow.multiplier || "1").replace(",", "."))
      : bust;
    const end = Math.min(cash, bust);
    const t0 = performance.now();
    const dur = Math.min(5000, 900 + 1400 * Math.log10(end + 1));
    timer.current = setInterval(() => {
      const p = Math.min(1, (performance.now() - t0) / dur);
      setShown(Math.max(1.0, 1 + (end - 1) * (p < 1 ? Math.pow(p, 1.6) : 1)));
      if (p >= 1) clearInterval(timer.current);
    }, 50);
    return () => timer.current && clearInterval(timer.current);
  }, [lastRow]);

  const manual = mode === "manual";
  const display = manual ? live : shown;
  const liveWin = phase === "cashed";
  const liveBusted = phase === "busted";

  const autoBust = lastRow && lastRow.game_id === "demo:crash-nitro"
    ? parseFloat((lastRow.symbols[0] || "1x").replace("x", "")) || 1.0
    : null;

  // curve points for the SVG: x = progress, y = multiplier (log scale)
  const top = Math.max(display, 1.2);
  const pts = [];
  for (let i = 0; i <= 40; i++) {
    const p = i / 40;
    const m = 1 + (display - 1) * Math.pow(p, 1.6);
    pts.push(`${(p * 300).toFixed(1)},${(150 - (Math.log(m) / Math.log(top)) * 140).toFixed(1)}`);
  }

  const hot = manual ? (liveBusted ? "#ef4444" : liveWin ? "#22c55e" : "#eab308")
    : (autoBust !== null && lastRow.payout_minor === 0 ? "#ef4444" : "#22c55e");

  const caption = manual
    ? (phase === "flying"
      ? `voando · saque agora: ${BRL(Math.round(stake * display))}`
      : phase === "cashed"
        ? `SACADO em ${Number(result.multiplier).toFixed(2)}x`
        : phase === "busted"
          ? `VOOU PARA LONGE em ${Number(result.bust).toFixed(2)}x`
          : "clique em apostar e saque a hora que quiser")
    : (autoBust !== null && lastRow.payout_minor === 0
      ? `VOOU PARA LONGE em ${autoBust.toFixed(2)}x`
      : win ? `SACADO em ${target}x` : `alvo ${target}x`);

  const primary = manual
    ? (phase === "flying"
      ? {
        label: `SACAR ${display.toFixed(2)}x · ${BRL(Math.round(stake * display))}`,
        on: cashout,
        style: { background: "#16a34a", color: "#fff" },
      }
      : { label: starting ? "decolando…" : "Apostar e voar", on: start })
    : { label: "Apostar e voar", on: onSpin };

  return (
    <div id="gameview" style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{game.title}</h2>
        <button className="ghost" style={{ width: "auto" }} onClick={onClose}>
          ✕ Fechar Crash
        </button>
      </div>
      <div id="cert">Crash Original · RTP {game.rtp}% · edge 3% · saque até 1000x</div>

      <div className="stakeRow" style={{ marginTop: 12, justifyContent: "center" }}>
        <button className={manual ? "on" : ""} onClick={() => setMode("manual")}>
          Manual
        </button>
        <button className={manual ? "" : "on"} onClick={() => setMode("auto")}>
          Automático
        </button>
      </div>

      <div style={{ textAlign: "center", margin: "14px 0 4px" }}>
        <div style={{
          fontSize: 44, fontWeight: 800,
          color: hot,
        }}>
          {display.toFixed(2)}x
        </div>
        <div style={{ fontSize: 13, opacity: 0.75 }}>{caption}</div>
      </div>

      <svg viewBox="0 0 300 160" style={{ width: "100%", maxWidth: 460, display: "block", margin: "0 auto" }}>
        <line x1="0" y1="150" x2="300" y2="150" stroke="currentColor" strokeOpacity="0.25" />
        <polyline points={pts.join(" ")} fill="none" stroke={hot} strokeWidth="3" strokeLinejoin="round" />
        <circle cx={pts.length ? pts[pts.length - 1].split(",")[0] : 0} cy={pts.length ? pts[pts.length - 1].split(",")[1] : 150} r="5" fill={hot} />
      </svg>

      {!manual ? (
        <div className="stakeRow" style={{ marginTop: 10 }}>
          {TARGETS.map((t) => (
            <button key={t} className={target === t ? "on" : ""} onClick={() => onTarget(t)}>
              {t.replace(".", ",")}x
            </button>
          ))}
          <input
            aria-label="Cash-out alvo"
            value={target}
            onChange={(e) => onTarget(e.target.value)}
            style={{ width: 76, textAlign: "center" }}
          />
        </div>
      ) : null}

      <div className="stakeRow">
        {STAKES.map(([value, label]) => (
          <button
            key={value}
            className={stake === value ? "on" : ""}
            disabled={manual && phase === "flying"}
            onClick={() => setStake(value)}
          >
            {label}
          </button>
        ))}
      </div>

      <button
        id="spin"
        style={primary.style}
        disabled={manual ? starting : busy}
        onClick={primary.on}
      >
        {primary.label}
      </button>

      <div id="msg" className={manual ? (liveWin ? "ok" : "err") : (win ? "ok" : "err")}>
        {manual
          ? (err
            ? err
            : liveWin
              ? "Prêmio " + BRL(result.payout_minor) + " · saque " + Number(result.multiplier).toFixed(2) + "x"
              : liveBusted
                ? "Sem prêmio · voou para longe em " + Number(result.bust).toFixed(2) + "x"
                : "")
          : message}
      </div>

      <table className="paytab">
        <tbody>
          <tr><td>Manual: saque a qualquer instante</td><td>aposta x multiplicador</td></tr>
          <tr><td>Automático: saque no alvo escolhido</td><td>alvo x aposta</td></tr>
          <tr><td>Bust (3% instantâneo em 1,00x)</td><td>perde</td></tr>
          <tr><td>RTP do modelo demo</td><td>97,00%</td></tr>
        </tbody>
      </table>
    </div>
  );
}
