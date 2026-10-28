"use client";

import { useEffect, useState } from "react";
import { api, BRL } from "../../lib/api";
import UIIcon from "./UIIcon";

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
export default function AccountView({ profile, player, health, history, fullAccess = false, refreshError, onChanged, onLogout, onCash, onHistory }) {
  const [section, setSection] = useState("profile");
  const [sessions, setSessions] = useState(null);
  const [sessionError, setSessionError] = useState("");
  const [endingSession, setEndingSession] = useState(false);
  // On the public sports surface the history shows sports bets only; casino
  // rounds reappear once the data portal is unlocked (decision 0080).
  const rounds = (history?.rounds || []).filter((r) => fullAccess || r.type === "sports");

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

  const [excludeOpen, setExcludeOpen] = useState(false);
  const [excludeDuration, setExcludeDuration] = useState("7");
  const [excludeBusy, setExcludeBusy] = useState(false);
  const [excludeNotice, setExcludeNotice] = useState("");
  const [excludeError, setExcludeError] = useState("");
  const [liftOpen, setLiftOpen] = useState(false);

  const exclusionUntil = () => {
    if (excludeDuration === "permanent") return "2099-12-31";
    return new Date(Date.now() + Number(excludeDuration) * 86400000).toISOString().slice(0, 10);
  };

  const selfExclude = async () => {
    if (excludeBusy) return;
    setExcludeBusy(true);
    setExcludeError("");
    setExcludeNotice("");
    try {
      const until = exclusionUntil();
      await api("POST", "/api/self-exclude", { until });
      setExcludeOpen(false);
      setExcludeNotice(
        excludeDuration === "permanent"
          ? "Autoexclusão permanente ativada."
          : "Autoexclusão ativada até " + new Date(until + "T12:00:00").toLocaleDateString("pt-BR") + "."
      );
      if (onChanged) onChanged();
    } catch (e) {
      setExcludeError(e.message);
    } finally {
      setExcludeBusy(false);
    }
  };
  const liftBlock = async () => {
    setExcludeError("");
    setExcludeNotice("");
    try {
      await api("POST", "/api/self-exclude-lift");
      setExcludeNotice("Bloqueio de autoexclusão removido.");
    } catch (e) {
      setExcludeError(e.message);
    }
    if (onChanged) onChanged();
  };
  return (
    <div className="account-view">
      <header className="account-title account-identity"><div className="account-avatar" aria-hidden="true">{(profile?.name || "C").trim().split(/\s+/).slice(0,2).map(part=>part[0]).join("").toUpperCase()}</div><div><h1>{profile?.name || "Minha conta"}</h1>{profile?.username ? <p>@{profile.username}</p> : null}</div><button className="account-icon-action" onClick={onLogout} title="Sair da conta" aria-label="Sair da conta"><UIIcon name="logout" size={22}/></button></header>
      <div className="account-workspace"><nav className="account-sections" role="tablist" aria-label="Seções da conta" onKeyDown={event => { const tabs = [...event.currentTarget.querySelectorAll("button")]; const index = tabs.indexOf(document.activeElement); const next = event.key === "ArrowRight" || event.key === "ArrowDown" ? (index + 1) % tabs.length : event.key === "ArrowLeft" || event.key === "ArrowUp" ? (index + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null; if (next !== null) { event.preventDefault(); tabs[next].focus(); tabs[next].click(); } }}>{[{key:"profile",icon:"user",label:"Perfil"},{key:"sessions",icon:"monitor",label:"Dispositivos"},{key:"history",icon:"history",label:"Histórico"},{key:"limits",icon:"shield",label:"Pausas e proteção"}].map(item=><button key={item.key} type="button" role="tab" aria-selected={section===item.key} aria-controls={"account-"+item.key} aria-label={item.label} title={item.label} onClick={()=>setSection(item.key)}><UIIcon name={item.icon} size={23}/></button>)}</nav><div className="account-content">
      {profile ? (
        <section className="panel account-balance-card" id="account-overview" hidden={section !== "profile"}>
          <div className="account-balance-total"><h2>Saldo disponível</h2><strong>{BRL(profile.available_minor)}</strong></div>
          <div className="account-balance-legend">
            <div><span className="legend-dot cash" />Saldo disponível <b>{BRL(profile.available_minor)}</b></div>
            {profile.bonus_minor > 0 ? <div><span className="legend-dot bonus" />Bônus <b>{BRL(profile.bonus_minor)}</b></div> : null}
            <div className="account-balance-actions">
              <button className="betslip-submit" style={{ width: "auto", padding: "8px 14px" }} onClick={() => onCash?.("dep")} aria-label="Depositar" title="Depositar"><UIIcon name="incoming" size={22}/></button>
              <button className="ghost" style={{ width: "auto", padding: "8px 14px" }} onClick={() => onCash?.("wd")} aria-label="Sacar" title="Sacar"><UIIcon name="outgoing" size={22}/></button>
            </div>
          </div>
        </section>
      ) : null}
      <section className="panel" id="account-profile" hidden={section !== "profile"} role="tabpanel" aria-label="Perfil">
        <h2>Perfil</h2>
        {profile ? <>

          <dl className="club-account-facts">
            {profile.username ? <div><dt>Usuário</dt><dd>{profile.username}</dd></div> : null}
            <div><dt>{profile.person_type === "PJ" ? "CNPJ" : "CPF"}</dt><dd>{profile.cnpj_masked || profile.cpf_masked || "Não informado"}</dd></div>
            <div><dt>Chave Pix</dt><dd>{profile.pix_masked || "Não cadastrada"}</dd></div>
          </dl>
        </> : <p className="sub">Nenhuma conta conectada. Entre para acessar seus dados.</p>}

      </section>
      <section className="panel account-rg" id="account-limits" hidden={section !== "limits"} role="tabpanel" aria-label="Pausas e proteção"><h2>Pausas e proteção</h2>
        {excludeOpen ? (
          <div className="account-exclude" role="group" aria-label="Confirmar autoexclusão">
            <p>Escolha por quanto tempo bloquear sua conta. Durante o bloqueio você não poderá apostar nem depositar.</p>
            <label htmlFor="exclude-duration">Duração</label>
            <select id="exclude-duration" value={excludeDuration} onChange={(e) => setExcludeDuration(e.target.value)}>
              <option value="1">24 horas</option>
              <option value="7">7 dias</option>
              <option value="30">30 dias</option>
              <option value="permanent">Permanente</option>
            </select>
            <div className="account-exclude-actions">
              <button className="ghost" disabled={excludeBusy} onClick={() => setExcludeOpen(false)}>Cancelar</button>
              <button className="danger" disabled={excludeBusy} onClick={selfExclude}>{excludeBusy ? "Ativando…" : "Confirmar autoexclusão"}</button>
            </div>
          </div>
        ) : (
          <button
            className="danger"
            style={{ width: "auto", marginTop: 14 }}
            disabled={!player}
            onClick={() => { setExcludeOpen(true); setLiftOpen(false); setExcludeNotice(""); setExcludeError(""); }}
          >
            Pausar acesso
          </button>
        )}
        {liftOpen ? (
          <span className="account-exclude-actions" style={{ marginTop: 14, marginLeft: 8 }}>
            <button className="ghost" onClick={() => setLiftOpen(false)}>Cancelar</button>
            <button onClick={() => { setLiftOpen(false); liftBlock(); }}>Confirmar levantamento</button>
          </span>
        ) : (
          <button
            className="ghost"
            style={{ width: "auto", marginTop: 14, marginLeft: 8 }}
            disabled={!player}
            onClick={() => { setLiftOpen(true); setExcludeNotice(""); setExcludeError(""); }}
          >
            Reativar acesso
          </button>
        )}
        {excludeNotice ? <p className="account-notice" role="status">{excludeNotice}</p> : null}
        {excludeError ? <p className="account-notice err" role="alert">{excludeError}</p> : null}
      </section>
      <section className="panel" id="account-sessions" hidden={section !== "sessions"} role="tabpanel" aria-label="Dispositivos">
        <h2>Dispositivos</h2>
        <div style={{ fontSize: 12.5, color: "var(--mut)" }}>
          Gerencie seus acessos.
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
      <section className="panel" id="account-history" hidden={section !== "history"} role="tabpanel" aria-label="Histórico">
        <h2>Histórico</h2>
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
        {rounds.length > 0
          ? (() => {
              const total = rounds.reduce((n, r) => n + (r.stake_minor || 0), 0);
              const back = rounds.reduce((n, r) => n + (r.payout_minor || 0), 0);
              const pending = rounds.filter((r) => r.tier === "pendente").length;
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
                      <div style={{ fontSize: 12, color: "var(--mut)" }}>{k}</div>
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
              <th>Descrição</th>
              <th>Aposta</th>
              <th>Retorno</th>
              <th>Resultado</th>
            </tr>
          </thead>
          <tbody>
            {rounds.length > 0 ? (
              rounds
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
                  Nenhuma aposta realizada ainda. Escolha um mercado no boletim para começar!
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
      </div></div>
    </div>
  );
}
