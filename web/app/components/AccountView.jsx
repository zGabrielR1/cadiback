"use client";

import { api, BRL } from "../../lib/api";

/** Account view: profile, self-exclusion controls, stats strip and round
 * history (F1 extract from page.jsx). Exclusion calls live here and report
 * back through onChanged (the page refresh); history rendering is
 * untouched. */
export default function AccountView({ profile, player, health, history, refreshError, onChanged, onLogout }) {
  const selfExclude = async () => {
    try {
      await api("POST", "/api/self-exclude", {
        player,
        until: "2027-01-01",
      });
      window.alert("Autoexclusão ativada no ambiente de demonstração.");
    } catch (e) {
      window.alert(e.message);
    }
  };
  const liftBlock = async () => {
    try {
      await api("POST", "/api/self-exclude-lift", { player });
      window.alert("Bloqueio de autoexclusão removido.");
    } catch (e) {
      window.alert(e.message);
    }
    if (onChanged) onChanged();
  };
  return (
    <>
      <section className="panel">
        <h2>Minha Conta</h2>
        <div style={{ fontSize: 13.5 }}>
          {profile ? (
            <>
              <b>{profile.name}</b> · {profile.player_id}
              <br />
              {profile.username ? (
                <>
                  Usuário: <b>{profile.username}</b> ·{" "}
                </>
              ) : null}
              Chave Pix: {profile.pix_masked} · Saldo Disponível:{" "}
              <b>{BRL(profile.available_minor)}</b>
            </>
          ) : (
            "Nenhuma conta conectada. Clique em Entrar para iniciar sua sessão demo."
          )}
        </div>
        <button
          className="danger"
          style={{ width: "auto", marginTop: 14 }}
          disabled={!player}
          onClick={selfExclude}
        >
          Autoexcluir-me (Jogo Responsável)
        </button>
        <button
          className="ghost"
          style={{ width: "auto", marginTop: 14, marginLeft: 8 }}
          disabled={!player}
          onClick={liftBlock}
        >
          Levantar Bloqueio
        </button>
        <button
          className="ghost"
          style={{ width: "auto", marginTop: 14, marginLeft: 8 }}
          disabled={!player}
          onClick={onLogout}
        >
          Sair da conta
        </button>
      </section>
      <section className="panel">
        <h2>Histórico de Rodadas</h2>
        <div style={{ fontSize: 12.5, color: "var(--mut)" }}>Status do sistema: {health || "online"}</div>
        {history && history.risk && history.risk.flagged ? (
          <div className="err" style={{ fontSize: 12.5 }}>
            Monitor de risco: {history.risk.flags.join(", ")}
          </div>
        ) : null}
        {refreshError ? (
          <div className="err" style={{ fontSize: 12.5 }}>
            falha ao atualizar: {refreshError}
          </div>
        ) : null}
        {history && history.rounds && history.rounds.length > 0
          ? (() => {
              const total = history.rounds.reduce((n, r) => n + (r.stake_minor || 0), 0);
              const back = history.rounds.reduce((n, r) => n + (r.payout_minor || 0), 0);
              const pending = history.rounds.filter((r) => r.tier === "pendente").length;
              const roi = total > 0 ? ((back - total) / total) * 100 : 0;
              const cards = [
                ["Apostado", BRL(total)],
                ["Retornado", BRL(back)],
                ["Líquido", (back - total >= 0 ? "+" : "-") + BRL(Math.abs(back - total))],
                ["ROI", (roi >= 0 ? "+" : "") + roi.toFixed(1) + "%"],
                ["Em aberto", String(pending)],
              ];
              return (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                  {cards.map(([k, v]) => (
                    <div
                      key={k}
                      style={{
                        padding: "8px 12px",
                        border: "1px solid var(--line)",
                        borderRadius: 10,
                        background: "var(--chip)",
                        minWidth: 86,
                      }}
                    >
                      <div style={{ fontSize: 10.5, color: "var(--mut)", textTransform: "uppercase", letterSpacing: ".04em" }}>{k}</div>
                      <b style={{ fontSize: 14 }}>{v}</b>
                    </div>
                  ))}
                </div>
              );
            })()
          : null}
        <table className="hist">
          <thead>
            <tr>
              <th>ID</th>
              <th>Jogo</th>
              <th>Aposta</th>
              <th>Retorno</th>
              <th>Resultado</th>
            </tr>
          </thead>
          <tbody>
            {history && history.rounds && history.rounds.length > 0 ? (
              history.rounds
                .slice()
                .reverse()
                .map((r) => (
                  <tr key={r.round_id}>
                    <td>{r.round_id.slice(0, 8)}</td>
                    <td>{r.title || r.game_id}</td>
                    <td>{BRL(r.stake_minor)}</td>
                    <td>{BRL(r.payout_minor)}</td>
                    <td>
                      {r.type === "sports" ? (
                        r.tier === "pendente" ? (
                          <span className="badge">PENDENTE @ {r.multiplier}</span>
                        ) : r.tier === "vitoria" ? (
                          <span className="badge b-ok">VITÓRIA @ {r.multiplier}</span>
                        ) : r.tier === "anulada" ? (
                          <span className="badge">ANULADA · estorno @ 1.00</span>
                        ) : (
                          <span className="badge b-err">DERROTA @ {r.multiplier}</span>
                        )
                      ) : (
                        <>
                          {r.tier} {r.multiplier}x
                        </>
                      )}
                      {r.type === "sports" && r.note ? (
                        <div style={{ fontSize: 11, color: "var(--mut)", marginTop: 4 }}>
                          {r.note}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))
            ) : (
              <tr>
                <td colSpan={5} style={{ color: "var(--mut)", textAlign: "center", padding: "16px" }}>
                  Nenhuma rodada realizada ainda. Escolha um jogo no cassino para começar!
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </>
  );
}
