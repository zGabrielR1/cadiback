"use client";

import { betIdentity } from "../../lib/sports.mjs";
import { BRL } from "../../lib/api";

/** Floating sports betslip tray (F1 extract from page.jsx). Leg
 * add/remove stays here as presentation; pricing + placement stay in
 * the page handler so the wallet check lives in one place. */
export default function BetslipTray({
  bets,
  profile,
  betAmount,
  onBetAmount,
  busy,
  onRemove,
  onClear,
  onPlace,
}) {
  if (bets.length === 0) return null;
  const totalOdds = bets.reduce((acc, b) => acc * b.price, 1);
  return (
    <div className="betslip-tray">
      <div className="betslip-head">
        <span>Boletim de Apostas</span>
        {profile ? (
          <span style={{ color: "var(--acc)", fontSize: 12, fontWeight: 700 }}>
            Saldo: {BRL(profile.available_minor)}
          </span>
        ) : null}
        <button
          style={{
            background: "none",
            border: "none",
            color: "var(--mut)",
            cursor: "pointer",
            padding: "2px 6px",
            fontSize: 14,
          }}
          onClick={onClear}
        >
          ✕
        </button>
      </div>
      <div className="betslip-body">
        {bets.map((b) => (
          <div className="betslip-match" key={betIdentity(b)} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>
              {b.competition} · {b.home} × {b.away} — <b>{b.selection}</b> @{" "}
              <span style={{ color: "var(--acc)" }}>{b.price.toFixed(2)}</span>
            </span>
            <button
              style={{ background: "none", border: "none", color: "var(--mut)", cursor: "pointer", fontSize: 12 }}
              onClick={() => onRemove(b)}
            >
              remover
            </button>
          </div>
        ))}
        {bets.length > 1 ? (
          <div className="betslip-pick">
            <span>Express — {bets.length} seleções</span>
            <span style={{ color: "var(--acc)" }}>
              {totalOdds.toFixed(2)}
            </span>
          </div>
        ) : null}
        <label style={{ fontSize: 11.5, margin: "4px 0" }}>Valor da Aposta (R$)</label>
        <div className="betslip-stake-row">
          <input
            inputMode="decimal"
            value={betAmount}
            onChange={(e) => onBetAmount(e.target.value)}
            style={{ padding: "8px 10px", fontSize: 14 }}
          />
        </div>
        <div className="betslip-quick-chips">
          {["5", "10", "25", "50", "100"].map((val) => (
            <button key={val} onClick={() => onBetAmount(val)}>
              +R${val}
            </button>
          ))}
        </div>
        <div className="betslip-payout">
          <span>Retorno Potencial:</span>
          <b>
            {BRL(
              Math.round(
                (parseFloat(betAmount.replace(",", ".")) || 0) *
                  totalOdds * 100
              )
            )}
          </b>
        </div>
        <button
          disabled={busy}
          style={{ width: "100%", padding: "12px", boxShadow: "var(--glow)" }}
          onClick={onPlace}
        >
          Confirmar Aposta Demo
        </button>
      </div>
    </div>
  );
}
