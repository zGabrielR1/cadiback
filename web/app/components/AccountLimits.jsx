"use client";

import { useEffect, useRef, useState } from "react";
import { api, BRL } from "../../lib/api";
import { limitDraft, limitPayload } from "../../lib/account-limits.mjs";

export default function AccountLimits({ responsible, onChanged }) {
  const [draft, setDraft] = useState(() => limitDraft(responsible?.limits));
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(null);
  const mounted = useRef(false);
  const submitting = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const limits = saved || responsible?.limits;
  useEffect(() => {
    if (!dirty) setDraft(limitDraft(limits));
  }, [limits, dirty]);
  useEffect(() => { setSaved(null); }, [responsible?.limits]);

  const reset = () => {
    setDraft(limitDraft(limits));
    setDirty(false);
    setError("");
    setNotice("");
  };
  const save = async event => {
    event.preventDefault();
    if (submitting.current || !responsible?.limits) return;
    setError(""); setNotice("");
    let payload;
    try { payload = limitPayload(draft); } catch (e) { setError(e.message); return; }
    submitting.current = true; setBusy(true);
    try {
      const result = await api("POST", "/api/player/limits", payload);
      if (!mounted.current) return;
      if (!result?.limits) throw new Error("Não foi possível confirmar os limites salvos. Atualize a conta antes de tentar novamente.");
      setSaved(result.limits);
      setDraft(limitDraft(result.limits));
      setDirty(false);
      setNotice("Limites salvos.");
      try { await onChanged?.(); } catch {
        if (mounted.current) setError("Limites salvos, mas não foi possível atualizar o resumo da conta.");
      }
    } catch (e) {
      if (mounted.current) setError(e.message);
    } finally {
      submitting.current = false;
      if (mounted.current) setBusy(false);
    }
  };
  const fields = [
    ["deposit_daily_minor", "Limite diário de depósito (R$)", "decimal"],
    ["bet_daily_minor", "Limite diário de apostas (R$)", "decimal"],
    ["session_minutes", "Tempo máximo de sessão (minutos)", "numeric"],
  ];
  const today = responsible?.today;
  const net = today?.net_minor;
  return <form className="account-limits" onSubmit={save} aria-busy={busy}>
    <h3>Seus limites</h3>
    {today ? <p className="sub">Hoje (UTC): depositado {BRL(today.deposited_minor)} · apostado {BRL(today.staked_minor)} · saldo líquido {net == null ? "—" : (net < 0 ? "−" : net > 0 ? "+" : "") + BRL(Math.abs(net))}.</p> : <p className="sub">Resumo diário indisponível.</p>}
    <p className="sub" id="account-limits-help">Deixe um campo vazio para remover esse limite. Os limites diários reiniciam à meia-noite UTC; o tempo máximo vale por sessão.</p>
    <fieldset disabled={busy || !responsible?.limits} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
      {fields.map(([key, label, inputMode]) => <label key={key}>{label}<input inputMode={inputMode} value={draft[key]} aria-describedby="account-limits-help" onChange={event => { setDraft(previous => ({ ...previous, [key]: event.target.value })); setDirty(true); setNotice(""); setError(""); }} placeholder="Sem limite" /></label>)}
      <div className="account-exclude-actions">
        <button type="submit" className="ghost" disabled={!dirty}>{busy ? "Salvando…" : "Salvar limites"}</button>
        <button type="button" className="ghost" disabled={!dirty} onClick={reset}>Descartar alterações</button>
      </div>
    </fieldset>
    {!responsible?.limits ? <p className="sub">Carregue os dados da conta para editar seus limites.</p> : null}
    {dirty ? <p className="sub" role="status">Alterações ainda não salvas.</p> : null}
    {notice ? <p className="account-notice" role="status">{notice}</p> : null}
    {error ? <p className="account-notice err" role="alert">{error}</p> : null}
  </form>;
}
