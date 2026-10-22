"use client";

import { useEffect, useState } from "react";
import { api, BRL } from "../../lib/api";

/** A registry instant (ISO, UTC) in the reader's own timezone. */
function when(iso) {
  if (!iso) return "—";
  const stamp = new Date(iso);
  return Number.isNaN(stamp.getTime())
    ? "—"
    : stamp.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

/** A browser/OS label from the user agent. The raw string is not shown: it is
 * 200 characters of noise, and the point of the list is "is that me?". */
function deviceName(userAgent) {
  const text = String(userAgent || "");
  if (!text) return "Dispositivo desconhecido";
  const browser = /Edg\//.test(text)
    ? "Edge"
    : /OPR\//.test(text)
      ? "Opera"
      : /Firefox\//.test(text)
        ? "Firefox"
        : /Chrome\//.test(text)
          ? "Chrome"
          : /Safari\//.test(text)
            ? "Safari"
            : "Navegador";
  const system = /Android/.test(text)
    ? "Android"
    : /iPhone|iPad|iPod/.test(text)
      ? "iOS"
      : /Windows/.test(text)
        ? "Windows"
        : /Mac OS X|Macintosh/.test(text)
          ? "macOS"
          : /Linux/.test(text)
            ? "Linux"
            : "dispositivo";
  return browser + " · " + system;
}

/** Account view: profile, self-exclusion controls, active sessions, stats
 * strip and round history (F1 extract from page.jsx). Exclusion and session
 * calls live here and report back through onChanged (the page refresh);
 * history rendering is untouched. */
export default function AccountView({ profile, player, health, history, refreshError, onChanged, onLogout }) {
  const [sessions, setSessions] = useState(null);
  const [sessionError, setSessionError] = useState("");
  const [endingSession, setEndingSession] = useState(false);

  const loadSessions = () => {
    api("GET", "/api/player/sessions")
      .then((data) => {
        setSessions(data.sessions || []);
        setSessionError("");
      })
      .catch((e) => {
        setSessions([]);
        setSessionError(e.message);
      });
  };

  useEffect(() => {
    if (player) loadSessions();
    else setSessions(null);
    // a login on another tab changes the list; reload with the player
  }, [player]);

  const endSession = async (sessionId) => {
    if (endingSession) return;
    setEndingSession(true);
    setSessionError("");
    try {
      const result = await api("POST", "/api/player/sessions/revoke", {
        session_id: sessionId,
      });
      // revoking the row this tab is using is a logout for this tab too
      if (result.current) onLogout();
      else loadSessions();
    } catch (e) {
      setSessionError(e.message);
    } finally {
      setEndingSession(false);
    }
  };

  const endOtherSessions = async () => {
    if (endingSession) return;
    setEndingSession(true);
    setSessionError("");
    try {
      await api("POST", "/api/player/sessions/revoke-others");
      loadSessions();
    } catch (e) {
      setSessionError(e.message);
    } finally {
      setEndingSession(false);
    }
  };

  const selfExclude = async () => {
    try {
      await api("POST", "/api/self-exclude", {
        until: "2027-01-01",
      });
      window.alert("Autoexclusão ativada no ambiente de demonstração.");
    } catch (e) {
      window.alert(e.message);
    }
  };
  const liftBlock = async () => {
    try {
      await api("POST", "/api/self-exclude-lift");
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
              {profile.cnpj_masked || profile.cpf_masked ? (
                <div className="sub">{profile.person_type === "PJ" ? "PJ · CNPJ " : "PF · CPF "}
                  {profile.cnpj_masked || profile.cpf_masked}</div>
              ) : null}
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
        <h2>Sessões ativas</h2>
        <div style={{ fontSize: 12.5, color: "var(--mut)" }}>
          Cada login abre uma sessão. Encerrar uma aqui derruba aquela sessão no próximo pedido;
          a senha e o saldo não mudam.
        </div>
        {sessionError ? (
          <div className="err" role="alert" style={{ fontSize: 12.5 }}>
            Sessões: {sessionError}
          </div>
        ) : null}
        {sessions === null ? (
          <div className="sub" style={{ marginTop: 8 }}>
            Carregando...
          </div>
        ) : sessions.length === 0 ? (
          <div className="sub" style={{ marginTop: 8 }}>
            Nenhuma sessão ativa.
          </div>
        ) : (
          <table className="hist" style={{ marginTop: 8 }}>
            <thead>
              <tr>
                <th>Dispositivo</th>
                <th>Início</th>
                <th>Último uso</th>
                <th>Expira</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td>
                    {deviceName(s.user_agent)}
                    {s.current ? (
                      <>
                        {" "}
                        <span className="badge b-ok">este dispositivo</span>
                      </>
                    ) : null}
                    <div style={{ fontSize: 11, color: "var(--mut)" }}>
                      {s.ip || "IP desconhecido"}
                    </div>
                  </td>
                  <td>{when(s.created_at)}</td>
                  <td>{when(s.last_seen_at)}</td>
                  <td>{when(s.expires_at)}</td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      className="ghost"
                      style={{ width: "auto", fontSize: 11.5, padding: "4px 8px" }}
                      onClick={() => endSession(s.id)}
                      disabled={endingSession}
                    >
                      {s.current ? "Sair" : "Encerrar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <button
          className="ghost"
          style={{ width: "auto", marginTop: 12 }}
          disabled={endingSession || !sessions || sessions.length < 2}
          onClick={endOtherSessions}
        >
          Encerrar as outras sessões
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
