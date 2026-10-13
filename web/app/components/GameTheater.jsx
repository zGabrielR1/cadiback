"use client";

import { useEffect, useRef, useState } from "react";
import { BRL, api } from "../../lib/api";

/** Spribe operator bridge (decision 0031): the game posts its round
 * lifecycle to the parent window (`ifc.make.bet` / `ifc.win.info` /
 * `ifc.end.round`) and obeys `{cmd: 'ifc.set.balance'}` back. The theater
 * mirrors each round to our wallet through `POST /api/wallet/round`
 * (idempotent per round, so replays settle once) and pushes our real
 * saldo into the game — whose own client refuses the bet when it cannot
 * cover the stake (the R$0 gate). A cancelled bet is dropped before any
 * mirror; a bust (round ends with no win) settles as payout 0. */
function useSpribeBridge(game, profile, walletToken, onWallet, iframeRef) {
  const open = useRef({});
  const ignored = useRef({});
  const seq = useRef(0);
  const note = useRef(null);
  const [, setNoteTick] = useState(0);
  // The message listener is registered once per game/token; the profile it
  // gates on is mirrored through a ref so every bet sees the live saldo.
  const profileRef = useRef(profile);
  profileRef.current = profile;

  const spendable = () => {
    const p = profileRef.current || {};
    return (Number(p.available_minor) || 0) + (Number(p.bonus_minor) || 0);
  };

  const say = (text) => {
    note.current = text;
    setNoteTick((n) => n + 1);
    setTimeout(() => {
      if (note.current === text) {
        note.current = null;
        setNoteTick((n) => n + 1);
      }
    }, 5000);
  };

  const pushBalance = () => {
    try {
      const frame = iframeRef.current;
      const p = profileRef.current;
      if (!frame || !frame.contentWindow || !p) return;
      // available_minor (+ bonus_minor) are the live fields; either may be
      // absent on a fresh object, so default to 0 — never NaN (the game
      // would refuse every bet on a null balance).
      const major = ((Number(p.available_minor) || 0) +
                     (Number(p.bonus_minor) || 0)) / 100;
      frame.contentWindow.postMessage(
        { cmd: "ifc.set.balance", data: { value: major } },
        window.location.origin
      );
    } catch (e) {}
  };

  useEffect(() => {
    open.current = {};
  }, [game && game.game_id]);

  useEffect(() => {
    pushBalance();
  }, [profile && profile.available_minor, profile && profile.bonus_minor]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!game || !game.game_id || game.game_id.indexOf("spribe:") !== 0 || !walletToken) return;
    const report = (betId, payoutMinor) => {
      const o = open.current[betId];
      if (!o) return;
      delete open.current[betId];
      api("POST", "/api/wallet/round", {
        token: walletToken,
        round_id: o.rid,
        stake_minor: o.stake,
        payout_minor: payoutMinor,
      }).then(() => {
        if (onWallet) onWallet();
      }).catch(() => {});
    };
    const onMessage = (ev) => {
      try {
        if (ev.origin !== window.location.origin) return;
        const msg = ev.data;
        if (!msg || typeof msg.type !== "string" || msg.type.indexOf("ifc.") !== 0) return;
        const d = msg.data || {};
        if (msg.type === "ifc.make.bet") {
          seq.current += 1;
          const stake = Math.max(0, Math.round(Number(d.amount || 0) * 100));
          // The demo client ships with balance validation OFF, so the game
          // itself never refuses — the gate lives here: a bet our saldo
          // cannot cover runs on trial credits only and is never mirrored.
          if (spendable() < stake) {
            ignored.current[d.id] = true;
            say("Saldo insuficiente — esta rodada corre em créditos de demonstração.");
          } else {
            open.current[d.id] = {
              stake,
              rid: `spribe-${d.id}-${seq.current}-${Date.now()}`,
            };
          }
          pushBalance();
        } else if (msg.type === "ifc.make.bet.complete") {
          if (Number(d.code) !== 200) {
            delete open.current[d.id];
            delete ignored.current[d.id];
          }
        } else if (msg.type === "ifc.win.info") {
          if (ignored.current[d.id]) return;
          report(d.id, Math.max(0, Math.round(Number(d.amount || 0) * 100)));
        } else if (msg.type === "ifc.cancel.bet") {
          delete open.current[d.id];
          delete ignored.current[d.id];
        } else if (msg.type === "ifc.end.round") {
          // A bust settles the still-open bets as payout 0 — but a cashout
          // tapped at the last instant reports its win just after the round
          // ends, so wait briefly: a win.info that lands first settles the
          // bet and this finds nothing left to do.
          const pending = Object.keys(open.current);
          ignored.current = {};
          setTimeout(() => {
            pending.forEach((betId) => report(betId, 0));
          }, 2000);
        } else if (msg.type === "ifc.init") {
          pushBalance();
        }
      } catch (e) {}
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [game && game.game_id, walletToken]); // eslint-disable-line react-hooks/exhaustive-deps

  return note.current;
}

/** Embedded official-game theater player (F1 extract from page.jsx):
 * fullscreen, reload, balance chip, new-tab escape hatch and the
 * quick-switch strip over every provider-hosted demo. */
export default function GameTheater({
  game,
  allGames,
  profile,
  walletToken,
  onWallet,
  isFullscreen,
  iframeKey,
  onBack,
  onReload,
  onToggleFullscreen,
  onSelect,
}) {
  const iframeRef = useRef(null);
  const spribeNote = useSpribeBridge(game, profile, walletToken, onWallet, iframeRef);
  if (!game) return null;
  return (
    <div
      className="game-modal"
      onClick={(e) => {
        if (e.target === e.currentTarget) onBack();
      }}
    >
      <div className={"game-theater" + (isFullscreen ? " fullscreen" : "")}>
        <div className="game-header">
          <div className="game-info">
            <button
              className="ghost"
              style={{ width: "auto", margin: 0, padding: "6px 12px" }}
              onClick={onBack}
            >
              ← Voltar ao Cassino
            </button>
            <h3 className="game-title">{game.title}</h3>
            <span className="game-provider-tag">
              {(game.provider || "").replace(/_/g, " ")}
            </span>
            <span
              className="badge b-ok"
              style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              ● AO VIVO DEMO
            </span>
          </div>
          <div className="game-actions">
            {profile ? (
              <span className="bal" style={{ fontSize: 13, padding: "5px 12px" }}>
                Saldo: {BRL(profile.available_minor)}
              </span>
            ) : null}
            <button
              className="ghost"
              title="Recarregar Jogo"
              onClick={onReload}
            >
              ↻ Recarregar
            </button>
            <button
              className="ghost"
              title="Tela Cheia"
              onClick={onToggleFullscreen}
            >
              {isFullscreen ? "🗗 Restaurar" : "⛶ Tela Cheia"}
            </button>
            <a
              href={game.launch_url || game.demo_url}
              target="_blank"
              rel="noopener noreferrer"
              className="ghost"
              style={{
                padding: "7px 12px",
                borderRadius: 8,
                border: "1px solid var(--line)",
                color: "var(--ink)",
                textDecoration: "none",
                fontSize: 12.5,
                fontWeight: 700,
              }}
              title="Abrir em Nova Aba"
            >
              ↗ Nova Aba
            </a>
            <button
              className="danger"
              style={{ padding: "6px 12px", width: "auto" }}
              onClick={onBack}
            >
              ✕ Fechar
            </button>
          </div>
        </div>
        <div className="game-frame-container">
          {spribeNote ? (
            <div style={{
              padding: "8px 14px", fontSize: 13, fontWeight: 600,
              background: "#5a1010", color: "#fff", textAlign: "center",
            }}>
              {spribeNote}
            </div>
          ) : null}
          <iframe
            key={iframeKey}
            ref={iframeRef}
            src={game.launch_url || game.demo_url}
            className="game-iframe"
            allow="autoplay; fullscreen; screen-wake-lock; encrypted-media"
            title={game.title}
          />
        </div>
        <div className="game-quick-strip">
          <span className="game-quick-label">Trocar de Jogo:</span>
          {allGames.map((g) => (
            <button
              key={g.game_id}
              className={
                "game-quick-chip" +
                (game.game_id === g.game_id ? " active" : "")
              }
              onClick={() => onSelect(g)}
            >
              {g.title}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
