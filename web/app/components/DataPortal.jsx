"use client";

import { useState } from "react";

/** Neutral intermediate surface between the public sports site and the full
 * terminal (decision 0080). It reads as an operator data/integrity page; the
 * access code unlocks the rest of the session. */
export default function DataPortal({
  unlocked,
  authenticated,
  onUnlock,
  onEnter,
  onLock,
  onBack,
}) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");

  const submit = (event) => {
    event.preventDefault();
    setError("");
    if (!code.trim()) {
      setError("Informe o código de acesso.");
      return;
    }
    if (!onUnlock(code)) {
      setError("Código não reconhecido.");
      return;
    }
    setCode("");
  };

  return (
    <section className="data-portal" aria-labelledby="data-portal-title">
      <div className="data-portal-main">
        <h1 id="data-portal-title">Cotações, feed e integridade.</h1>
        <p className="data-portal-lead">
          Área de consulta da operação. Reúne a origem do feed esportivo, a
          cobertura de mercados e o registro de liquidações do ambiente.
        </p>
        <dl className="data-portal-facts">
          <div>
            <dt>Feed</dt>
            <dd>Leitura pública de partidas</dd>
          </div>
          <div>
            <dt>Cotação</dt>
            <dd>Modelo da casa sobre o feed</dd>
          </div>
          <div>
            <dt>Cobertura</dt>
            <dd>Futebol, tênis, basquete, hóquei e outros</dd>
          </div>
          <div>
            <dt>Reprecificação</dt>
            <dd>A cada 30 segundos, por mercado</dd>
          </div>
        </dl>
      </div>

      <div className="data-portal-panel">
        {unlocked ? (
          <>
            <h2>Acesso liberado</h2>
            <p>
              A área completa está disponível nesta sessão do navegador.
              {authenticated
                ? " Abra o terminal para continuar."
                : " Entre na sua conta para continuar."}
            </p>
            <button type="button" onClick={onEnter}>
              {authenticated ? "Abrir terminal" : "Entrar para continuar"}
            </button>
            <button type="button" className="ghost data-portal-back" onClick={onLock}>
              Encerrar acesso
            </button>
          </>
        ) : (
          <form onSubmit={submit}>
            <h2>Acesso restrito</h2>
            <p>Informe o código operacional para abrir a área completa.</p>
            <label htmlFor="data-access-code">Código de acesso</label>
            <input
              id="data-access-code"
              name="code"
              type="password"
              autoComplete="off"
              autoFocus
              value={code}
              onChange={(event) => {
                setCode(event.target.value);
                setError("");
              }}
              placeholder="Código"
            />
            {error ? (
              <p className="data-portal-error" role="alert">
                {error}
              </p>
            ) : null}
            <button type="submit">Acessar</button>
          </form>
        )}
        <button type="button" className="ghost data-portal-back" onClick={onBack}>
          Voltar às cotações
        </button>
      </div>
    </section>
  );
}
