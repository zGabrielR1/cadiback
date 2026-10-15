"use client";

import { useEffect, useState } from "react";
import { api, BRL } from "../../lib/api";

/** Painel administrativo — hidden behind a real login (default admin/admin
 * until the owner changes it). The dashboard reads GET /api/admin, which
 * derives every figure from the round ledger, the double-entry books and
 * the players file; credential management talks to /api/auth/* and
 * /api/admin/users*. Nothing here is fabricated. */

const pct = (v) =>
  v === null || v === undefined ? "—" : v.toFixed(2).replace(".", ",") + "%";

const signedBRL = (minor) =>
  (minor > 0 ? "+" : minor < 0 ? "-" : "") + BRL(Math.abs(minor || 0));

const brlPct = (v, target = 95.9) => {
  if (v == null) return { text: "—", cls: "" };
  const n = Math.max(0, Math.min(100, v));
  const cls = n >= target ? "" : (n >= target - 1 ? "mid" : "bad");
  return {
    text: n.toFixed(2).replace(".", ",") + "%",
    width: n + "%",
    cls,
  };
};

const barPct = (v) => Math.min(100, Math.max(0, v || 0));

const isAuthError = (message) =>
  /sessão|sessao|autentica|inválida|invalida/i.test(message || "");

function Kpi({ label, value, sub, tone }) {
  return (
    <div className="kpi">
      <div className="k-label">{label}</div>
      <div className={"k-value" + (tone ? " " + tone : "")}>{value}</div>
      {sub ? <div className="k-sub">{sub}</div> : null}
    </div>
  );
}

function Field({ id, label, ...props }) {
  return (
    <>
      <label htmlFor={id}>{label}</label>
      <input id={id} {...props} />
    </>
  );
}

export default function AdminPanel({ session, onSession }) {
  const [data, setData] = useState(null);
  const [users, setUsers] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // per-player drill-down (admin)
  const [playerDetail, setPlayerDetail] = useState(null);
  const [playerBusy, setPlayerBusy] = useState(false);
  const [playerLoader, setPlayerLoader] = useState(false);

  const openPlayer = (pid) => {
    setPlayerDetail(null);
    setPlayerLoader(true);
    let alive = true;
    api("GET", "/api/admin/player?id=" + encodeURIComponent(pid))
      .then((d) => { if (alive) setPlayerDetail(d); })
      .catch((e) => { if (!isAuthError(e.message)) { if (alive) setError(e.message); } else onSession(null); })
      .finally(() => { alive && setPlayerLoader(false); });
  };

  const closePlayer = () => { setPlayerDetail(null); setPlayerLoader(false); };

  // login
  const [loginUser, setLoginUser] = useState("");
  const [loginPass, setLoginPass] = useState("");
  const [loginError, setLoginError] = useState("");

  // own password
  const [pwCurrent, setPwCurrent] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwConfirm, setPwConfirm] = useState("");
  const [pwMsg, setPwMsg] = useState("");
  const [pwError, setPwError] = useState("");

  // user credentials (admin)
  const [newUser, setNewUser] = useState("");
  const [newPass, setNewPass] = useState("");
  const [newRole, setNewRole] = useState("viewer");
  const [resetUser, setResetUser] = useState("");
  const [resetPass, setResetPass] = useState("");
  const [userMsg, setUserMsg] = useState("");
  const [userError, setUserError] = useState("");

  // operator settings + test accounts (admin)
  const [settings, setSettings] = useState(null);
  const [settingsMsg, setSettingsMsg] = useState("");
  const [settingsError, setSettingsError] = useState("");
  const [testAccounts, setTestAccounts] = useState(null);
  const [tName, setTName] = useState("");
  const [tEmail, setTEmail] = useState("");
  const [tCpf, setTCpf] = useState("");
  const [tPix, setTPix] = useState("");
  const [tPass, setTPass] = useState("");
  const [resetTest, setResetTest] = useState("");
  const [resetTestPass, setResetTestPass] = useState("");
  const [testMsg, setTestMsg] = useState("");
  const [testError, setTestError] = useState("");

  const refreshTestAccounts = async () => {
    try {
      const list = await api("GET", "/api/admin/test-accounts");
      setTestAccounts(list.test_accounts);
      setTestError("");
    } catch (e) {
      setTestError(e.message);
    }
  };

  const refreshUsers = async () => {
    try {
      const list = await api("GET", "/api/admin/users");
      setUsers(list.users);
      setUserError("");
    } catch (e) {
      setUserError(e.message);
    }
  };

  useEffect(() => {
    if (!session) {
      setData(null);
      setUsers(null);
      setSettings(null);
      setTestAccounts(null);
      return undefined;
    }
    let alive = true;
    const load = async () => {
      try {
        await api("GET", "/api/auth/me"); // validates the stored token
        const dash = await api("GET", "/api/admin");
        if (!alive) return;
        setData(dash);
        setError("");
        if (session.role === "admin") {
          try {
            const list = await api("GET", "/api/admin/users");
            if (alive) setUsers(list.users);
          } catch (e) {
            if (alive) setUserError(e.message);
          }
          try {
            const cfg = await api("GET", "/api/admin/settings");
            if (alive) setSettings(cfg.settings);
          } catch (e) {
            if (alive) setSettingsError(e.message);
          }
          try {
            const accs = await api("GET", "/api/admin/test-accounts");
            if (alive) setTestAccounts(accs.test_accounts);
          } catch (e) {
            if (alive) setTestError(e.message);
          }
        }
      } catch (e) {
        if (!alive) return;
        if (isAuthError(e.message)) onSession(null); // expired/revoked
        else setError(e.message);
      }
    };
    load();
    const id = setInterval(load, 30000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [session, onSession]);

  const doLogin = async () => {
    setBusy(true);
    setLoginError("");
    try {
      const s = await api("POST", "/api/auth/login", {
        username: loginUser.trim(),
        password: loginPass,
      });
      onSession(s);
      setLoginUser("");
      setLoginPass("");
    } catch (e) {
      setLoginError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doLogout = async () => {
    try {
      await api("POST", "/api/auth/logout");
    } catch (e) {
      /* a dead token still ends the local session */
    }
    onSession(null);
  };

  const doChangePassword = async () => {
    setPwMsg("");
    setPwError("");
    if (pwNew !== pwConfirm) {
      setPwError("a confirmação não confere");
      return;
    }
    if ((pwNew || "").length < 4) {
      setPwError("a senha precisa de ao menos 4 caracteres");
      return;
    }
    setBusy(true);
    try {
      const s = await api("POST", "/api/auth/password", {
        current: pwCurrent,
        new: pwNew,
      });
      onSession(s); // the server reissued the token
      setPwCurrent("");
      setPwNew("");
      setPwConfirm("");
      setPwMsg("Senha alterada. As sessões anteriores foram encerradas.");
    } catch (e) {
      setPwError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doCreateUser = async () => {
    setUserMsg("");
    setUserError("");
    setBusy(true);
    try {
      await api("POST", "/api/admin/users", {
        username: newUser.trim(),
        password: newPass,
        role: newRole,
      });
      setUserMsg(`Usuário ${newUser.trim()} criado (${newRole}).`);
      setNewUser("");
      setNewPass("");
      await refreshUsers();
    } catch (e) {
      setUserError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doResetPassword = async () => {
    setUserMsg("");
    setUserError("");
    if (!resetUser) {
      setUserError("escolha um usuário para redefinir");
      return;
    }
    setBusy(true);
    try {
      await api("POST", "/api/admin/users/reset", {
        username: resetUser,
        new: resetPass,
      });
      setUserMsg(`Senha de ${resetUser} redefinida; sessões dela encerradas.`);
      setResetUser("");
      setResetPass("");
      await refreshUsers();
    } catch (e) {
      setUserError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doDeleteUser = async (username) => {
    setUserMsg("");
    setUserError("");
    if (!window.confirm(`Remover o usuário ${username}?`)) return;
    setBusy(true);
    try {
      await api("POST", "/api/admin/users/delete", { username });
      setUserMsg(`Usuário ${username} removido.`);
      await refreshUsers();
    } catch (e) {
      setUserError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const saveSetting = async (key, value) => {
    setSettingsMsg("");
    setSettingsError("");
    setBusy(true);
    try {
      const out = await api("POST", "/api/admin/settings", { [key]: value });
      setSettings(out.settings);
      setSettingsMsg("Configuração salva.");
    } catch (e) {
      setSettingsError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doCreateTestAccount = async () => {
    setTestMsg("");
    setTestError("");
    setBusy(true);
    try {
      await api("POST", "/api/admin/test-accounts", {
        name: tName.trim(),
        email: tEmail.trim(),
        cpf: tCpf.trim(),
        password: tPass,
        pix_key: tPix.trim(),
      });
      setTestMsg(`Conta de teste ${tEmail.trim()} criada.`);
      setTName("");
      setTEmail("");
      setTCpf("");
      setTPix("");
      setTPass("");
      await refreshTestAccounts();
    } catch (e) {
      setTestError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doResetTestPassword = async () => {
    setTestMsg("");
    setTestError("");
    if (!resetTest) {
      setTestError("escolha uma conta de teste");
      return;
    }
    setBusy(true);
    try {
      await api("POST", "/api/admin/test-accounts/reset", {
        player_id: resetTest,
        password: resetTestPass,
      });
      setTestMsg("Senha da conta de teste redefinida.");
      setResetTest("");
      setResetTestPass("");
      await refreshTestAccounts();
    } catch (e) {
      setTestError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doDeleteTestAccount = async (playerId, email) => {
    setTestMsg("");
    setTestError("");
    if (!window.confirm(`Remover a conta de teste ${email}?`)) return;
    setBusy(true);
    try {
      await api("POST", "/api/admin/test-accounts/delete", {
        player_id: playerId,
      });
      setTestMsg(`Conta de teste ${email} removida.`);
      await refreshTestAccounts();
    } catch (e) {
      setTestError(e.message);
    } finally {
      setBusy(false);
    }
  };

  /* ---- not logged in: the login door ---- */
  if (!session) {
    return (
      <section className="panel">
        <h2>Área do Operador</h2>
        <p className="sub">
          Acesso restrito ao painel administrativo da demonstração.
        </p>
        <Field
          id="adm-user"
          label="Usuário"
          value={loginUser}
          autoComplete="username"
          onChange={(e) => setLoginUser(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") doLogin();
          }}
        />
        <Field
          id="adm-pass"
          label="Senha"
          type="password"
          value={loginPass}
          autoComplete="current-password"
          onChange={(e) => setLoginPass(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") doLogin();
          }}
        />
        <button
          disabled={busy}
          style={{ marginTop: 14 }}
          onClick={doLogin}
        >
          Entrar no Painel
        </button>
        {loginError ? (
          <p className="err" style={{ fontSize: 13, marginTop: 10 }}>
            {loginError}
          </p>
        ) : null}
      </section>
    );
  }

  /* ---- session, dashboard still loading ---- */
  if (!data) {
    return (
      <section className="panel">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            gap: 8,
          }}
        >
          <h2>Painel Administrativo</h2>
          <button className="ghost" onClick={doLogout}>
            Sair ({session.username})
          </button>
        </div>
        <p className="sub">
          {error ? "falha ao carregar: " + error : "Carregando indicadores…"}
        </p>
      </section>
    );
  }

  const t = data.totals;
  const r = data.returns;
  const max = Math.max(1, ...data.day_series.map((d) => d.stake_minor));

  return (
    <>
      <section className="panel">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            flexWrap: "wrap",
            gap: 8,
          }}
        >
          <h2>Painel Administrativo</h2>
          <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="badge b-ok">
              {session.username} · {session.role} · {data.health}
            </span>
            <button className="ghost" onClick={doLogout}>
              Sair
            </button>
          </span>
        </div>
        <p className="sub">{data.note}</p>
        {error ? (
          <p className="err" style={{ fontSize: 12.5 }}>
            falha ao atualizar: {error}
          </p>
        ) : null}
        <div className="kpi-grid" style={{ marginTop: 14 }}>
          <Kpi
            label="Jogadores"
            value={t.players}
            sub={`${t.rounds} rodadas no total · ${t.rounds_today} hoje`}
          />
          <Kpi
            label="GGR (livros)"
            value={signedBRL(t.ggr_minor)}
            sub={`Caixa do operador: ${BRL(t.operator_cash_minor)}`}
            tone={t.ggr_minor >= 0 ? "k-pos" : "k-neg"}
          />
          <Kpi
            label="Passivo de jogadores"
            value={BRL(t.player_liability_minor)}
            sub={`Bônus em aberto: ${BRL(t.bonus_liability_minor)}`}
          />
          <Kpi
            label="Depósitos"
            value={BRL(t.deposits_minor)}
            sub={`Saques pedidos: ${BRL(t.withdrawals_minor)} · pagos: ${BRL(
              t.withdrawals_paid_minor
            )}`}
          />
          <Kpi
            label="Saques pendentes"
            value={BRL(t.withdrawals_pending_minor)}
            sub={`Apostas esportivas aguardando: ${data.pending_sports}`}
          />
          <Kpi
            label="Jackpot"
            value={BRL(data.jackpot.pool_minor)}
            sub={`1% do volume de hoje (${BRL(
              data.jackpot.volume_today_minor
            )}) alimenta o pote`}
          />
        </div>
      </section>

      <section className="panel">
        <h2>Retorno ao jogador (RTP)</h2>
        <p className="sub">
          RTP realizado = prêmios ÷ apostas das rodadas in-house liquidadas
          (exclui pendentes e esportes, comparáveis ao modelo teórico).
        </p>
        <div className="rtp-row">
          <span>Realizado — geral</span>
          <div className="rtp-track">
            <div className="rtp-fill" style={{ width: barPct(r.rtp_percent) + "%" }} />
          </div>
          <b>{pct(r.rtp_percent)}</b>
        </div>
        <div className="rtp-row">
          <span>Realizado — hoje</span>
          <div className="rtp-track">
            <div className="rtp-fill today" style={{ width: barPct(r.rtp_today_percent) + "%" }} />
          </div>
          <b>{pct(r.rtp_today_percent)}</b>
        </div>
        <div className="rtp-row">
          <span>Modelo teórico (demo)</span>
          <div className="rtp-track">
            <div className="rtp-fill model" style={{ width: barPct(r.model_rtp_percent) + "%" }} />
          </div>
          <b>{pct(r.model_rtp_percent)}</b>
        </div>
        <p className="sub" style={{ marginTop: 12 }}>
          Turnover: {BRL(r.turnover_minor)} acumulado · {BRL(r.turnover_today_minor)} hoje
        </p>
      </section>

      <div className="admin-cols" style={{ marginTop: 16 }}>
        <section className="panel" style={{ marginTop: 0 }}>
          <h2>Volume por dia (7 dias)</h2>
          <p className="sub">Apostas liquidadas por dia (UTC), do livro de rodadas.</p>
          <div className="bars">
            {data.day_series.map((d) => (
              <div
                className="bar-col"
                key={d.day}
                title={`${d.day}: ${BRL(d.stake_minor)} em apostas · ${BRL(
                  d.payout_minor
                )} devolvidos · ${d.rounds} rodadas`}
              >
                <div className="bar-track">
                  {d.stake_minor > 0 ? (
                    <div
                      className="bar"
                      style={{
                        height: Math.max(5, Math.round((d.stake_minor / max) * 100)) + "%",
                      }}
                    />
                  ) : null}
                </div>
                <span className="bar-day">
                  {d.day.slice(8)}/{d.day.slice(5, 7)}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel" style={{ marginTop: 0 }}>
          <h2>Top ganhadores</h2>
          <p className="sub">Líquido acumulado (prêmios − apostas) por jogador.</p>
          {data.top_winners.length === 0 ? (
            <p style={{ color: "var(--mut)", fontSize: 13 }}>Nenhuma rodada registrada ainda.</p>
          ) : (
            <table className="hist">
              <thead>
                <tr>
                  <th>Jogador</th>
                  <th>Rodadas</th>
                  <th>Vitórias</th>
                  <th>Líquido</th>
                </tr>
              </thead>
              <tbody>
                {data.top_winners.map((w) => (
                  <tr key={w.pid}>
                    <td>
                      <button
                        className="ghost-sm"
                        onClick={() => openPlayer(w.pid)}
                      >
                        {w.label}
                      </button>
                    </td>
                    <td>{w.rounds}</td>
                    <td>{w.wins}</td>
                    <td className={w.net_minor >= 0 ? "k-pos" : "k-neg"}>
                      {signedBRL(w.net_minor)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <div className="admin-cols" style={{ marginTop: 16 }}>
        <section className="panel" style={{ marginTop: 0 }}>
          <h2>Maiores prêmios</h2>
          <p className="sub">Maior pagamento individual registrado.</p>
          {data.biggest_wins.length === 0 ? (
            <p style={{ color: "var(--mut)", fontSize: 13 }}>Sem prêmios registrados.</p>
          ) : (
            <table className="hist">
              <thead>
                <tr>
                  <th>Jogador</th>
                  <th>Jogo</th>
                  <th>Dia</th>
                  <th>Prêmio</th>
                </tr>
              </thead>
              <tbody>
                {data.biggest_wins.map((w, i) => (
                  <tr key={w.label + w.day + i}>
                    <td>
                      <button
                        className="ghost-sm"
                        onClick={() => openPlayer(w.label)}
                      >
                        {w.label}
                      </button>
                    </td>
                    <td>{w.game_id}</td>
                    <td>{w.day}</td>
                    <td style={{ color: "var(--gold)", fontWeight: 700 }}>
                      {BRL(w.payout_minor)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="panel" style={{ marginTop: 0 }}>
          <h2>Risco e pendências</h2>
          <div className="kpi-grid">
            <Kpi
              label="Jogadores sinalizados"
              value={data.risk.flagged_players}
              sub="monitor de risco: velocidade, picos, perseguição de perda, RTP"
            />
            <Kpi
              label="Apostas pendentes"
              value={data.pending_sports}
              sub="esportivas aguardando liquidação"
            />
          </div>
          <p className="sub" style={{ marginTop: 12 }}>
            Painel somente leitura do ambiente de demonstração — nenhum dado é
            inventado; cada número vem do livro de rodadas, dos livros duplos e
            do cadastro de jogadores.
          </p>
        </section>
      </div>

      {/* secret admin heading + per-player drill-down */}
      <div className="admin-sec-head">
        <h2>Painel operador — conta do jogador</h2>
        <p className="sub" style={{ margin: 0 }}>
          Selecione um jogador na seção Top ganhadores para ver o extrato,
          saldo, turnover e RTP do perfil. Cada número deriva do cadastro e do
          livro de rodadas; nada é inventado.
        </p>
      </div>
      {playerDetail ? (
        <section className="admin-player">
          <h3>{playerDetail.player.name || playerDetail.player.player_id}</h3>
          <div className="ap-meta">
            <div>CPF: {playerDetail.player.cpf_masked || "—"}</div>
            <div>PIX: {playerDetail.player.pix_masked || "—"} ({playerDetail.player.pix_kind || "—"})</div>
            <div>ID do cadastro: {playerDetail.player.player_id}</div>
            <div>Cadastro atualizado: {playerDetail.player.updated_at ? playerDetail.player.updated_at.slice(0, 10) : "—"}</div>
          </div>
          <div className="ap-balance">
            <div>
              <div className="lbl">Saldo disponível</div>
              <div className="val">{BRL(playerDetail.balance.available_minor)}</div>
            </div>
            <div>
              <div className="lbl">Bônus em aberto</div>
              <div className="val">{BRL(playerDetail.balance.bonus_minor)}</div>
            </div>
            <div>
              <div className="lbl">Total depositado</div>
              <div className="val">{BRL(playerDetail.balance.deposits_minor)}</div>
            </div>
            <div>
              <div className="lbl">1ª aposta</div>
              <div className="val">{BRL(playerDetail.balance.first_deposit_minor)}</div>
            </div>
          </div>
          <div className="ap-rtp">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <span style={{ color: "var(--mut)", fontSize: 12.5, textTransform: "uppercase", letterSpacing: ".06em" }}>RTP realizado</span>
              <span style={{ color: "var(--ink)", fontWeight: 700 }}>{brlPct(playerDetail.activity.settled_rtp_percent).text}</span>
            </div>
            <div className="ap-rtp-row">
              <span>Geral (liquidado)</span>
              <div className="ap-rtp-track">
                <div className={"ap-rtp-fill " + brlPct(playerDetail.activity.settled_rtp_percent).cls}
                  style={{ width: brlPct(playerDetail.activity.settled_rtp_percent).width }} />
              </div>
              <b>{brlPct(playerDetail.activity.settled_rtp_percent).text}</b>
            </div>
            <div className="ap-rtp-row">
              <span>Hoje (liquidado)</span>
              <div className="ap-rtp-track">
                <div className={"ap-rtp-fill " + brlPct(playerDetail.activity.settled_rtp_today_percent).cls}
                  style={{ width: brlPct(playerDetail.activity.settled_rtp_today_percent).width }} />
              </div>
              <b>{brlPct(playerDetail.activity.settled_rtp_today_percent).text}</b>
            </div>
            <div className="ap-rtp-row" style={{ marginTop: 6 }}>
              <span style={{ color: "var(--mut)" }}>
                Turnover liquidado: {BRL(playerDetail.activity.settled_stake_minor)} ·
                prêmios: {BRL(playerDetail.activity.settled_payout_minor)}
              </span>
            </div>
          </div>
          <div className="ap-latest">              {playerDetail.latest.length === 0 ? (
              <p className="ap-none">Nenhuma rodada encontrada para este cadastro.</p>
              ) : (
                <table className="ap-latest">
                  <thead>
                    <tr>
                      <th>Ronda</th>
                      <th>Jogo</th>
                      <th>Aposta</th>
                      <th>Prêmio</th>
                      <th>Status</th>
                      <th>Data</th>
                    </tr>
                  </thead>
                  <tbody>
                    {playerDetail.latest.map((r) => (
                      <tr key={r.round_id}>
                        <td style={{ fontFamily: "monospace", fontSize: 11.5, color: "var(--mut)" }}>{r.round_id}</td>
                        <td>{r.title || r.game_id || "—"}</td>
                        <td style={{ textAlign: "right", fontWeight: 700 }}>{BRL(r.stake_minor)}</td>
                        <td className={r.payout_minor > 0 ? "amt-win" : r.payout_minor < 0 ? "amt-loss" : ""}>
                          {BRL(r.payout_minor)}
                        </td>
                        <td>
                          {r.tier || r.type || "—"}
                          {r.type === "sports" && r.tier === "pendente"
                            ? " (pendente)"
                            : ""}
                        </td>
                        <td style={{ color: "var(--mut)" }}>
                          {r.ts ? r.ts.slice(0, 10) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
          </div>
          {playerDetail.flagged ? (
            <p className="ap-flag" style={{ margin: "12px 0 0", fontSize: 13 }}>
              Sinalizado em monitoramento: {playerDetail.flags.join(", ") || "…"}.
              Os detalhes completos ficam em /api/history?id=….
            </p>
          ) : null}
          <div style={{ marginTop: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <button className="ghost-sm" disabled={playerBusy} onClick={() => openPlayer(playerDetail.player.player_id)}>
              {playerBusy ? "Atualizando…" : "Atualizar extrato"}
            </button>
            <button className="ghost-sm" onClick={closePlayer}>
              Fechar
            </button>
          </div>
        </section>
      ) : null}

      {/* own password */}
      <section className="panel" style={{ marginTop: 16 }}>
        <h2>Minha senha</h2>
        <p className="sub">
          Trocar a senha encerra todas as suas sessões abertas e emite um novo
          token para esta tela.
        </p>
        <div className="admin-cols">
          <div>
            <Field
              id="pw-current"
              label="Senha atual"
              type="password"
              value={pwCurrent}
              autoComplete="current-password"
              onChange={(e) => setPwCurrent(e.target.value)}
            />
            <Field
              id="pw-new"
              label="Nova senha"
              type="password"
              value={pwNew}
              autoComplete="new-password"
              onChange={(e) => setPwNew(e.target.value)}
            />
          </div>
          <div>
            <Field
              id="pw-confirm"
              label="Confirmar nova senha"
              type="password"
              value={pwConfirm}
              autoComplete="new-password"
              onChange={(e) => setPwConfirm(e.target.value)}
            />
            <button
              disabled={busy}
              style={{ marginTop: 6 }}
              onClick={doChangePassword}
            >
              Alterar senha
            </button>
          </div>
        </div>
        {pwMsg ? (
          <p className="ok" style={{ fontSize: 13, marginTop: 10 }}>
            {pwMsg}
          </p>
        ) : null}
        {pwError ? (
          <p className="err" style={{ fontSize: 13, marginTop: 10 }}>
            {pwError}
          </p>
        ) : null}
      </section>

      {/* credential management — admins only */}
      {session.role === "admin" ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>Usuários do painel</h2>
          <p className="sub">
            Crie controles, redefina senhas (as sessões do usuário são
            encerradas) e remova controles. Senhas nunca são exibidas.
          </p>

          <table className="hist">
            <thead>
              <tr>
                <th>Usuário</th>
                <th>Papel</th>
                <th>Criado</th>
                <th>Atualizada</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(users || []).map((u) => (
                <tr key={u.username}>
                  <td>{u.username}</td>
                  <td>
                    <span className="badge">
                      {u.role === "admin" ? "admin" : "viewer"}
                    </span>
                  </td>
                  <td>{u.created_at.slice(0, 10)}</td>
                  <td>{u.updated_at.slice(0, 10)}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button
                      className="ghost"
                      style={{ width: "auto", padding: "4px 10px", fontSize: 12, marginRight: 6 }}
                      onClick={() => {
                        setResetUser(u.username);
                        setResetPass("");
                        setUserError("");
                        setUserMsg("");
                      }}
                    >
                      Redefinir
                    </button>
                    <button
                      className="danger"
                      style={{ width: "auto", padding: "4px 10px", fontSize: 12 }}
                      disabled={u.username === session.username}
                      onClick={() => doDeleteUser(u.username)}
                    >
                      Remover
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="admin-cols" style={{ marginTop: 14 }}>
            <div>
              <b style={{ fontSize: 13 }}>Criar usuário</b>
              <Field
                id="nu-name"
                label="Usuário"
                value={newUser}
                onChange={(e) => setNewUser(e.target.value)}
              />
              <Field
                id="nu-pass"
                label="Senha"
                type="password"
                value={newPass}
                onChange={(e) => setNewPass(e.target.value)}
              />
              <label htmlFor="nu-role">Papel</label>
              <select
                id="nu-role"
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
              >
                <option value="viewer">viewer (só assiste)</option>
                <option value="admin">admin (acesso total)</option>
              </select>
              <button
                disabled={busy}
                style={{ marginTop: 12 }}
                onClick={doCreateUser}
              >
                Criar usuário
              </button>
            </div>
            <div>
              <b style={{ fontSize: 13 }}>
                Redefinir senha{resetUser ? ` de ${resetUser}` : ""}
              </b>
              <Field
                id="ru-user"
                label="Usuário"
                value={resetUser}
                onChange={(e) => setResetUser(e.target.value)}
              />
              <Field
                id="ru-pass"
                label="Nova senha"
                type="password"
                value={resetPass}
                onChange={(e) => setResetPass(e.target.value)}
              />
              <button
                disabled={busy}
                style={{ marginTop: 12 }}
                onClick={doResetPassword}
              >
                Redefinir senha
              </button>
            </div>
          </div>

          {userMsg ? (
            <p className="ok" style={{ fontSize: 13, marginTop: 10 }}>
              {userMsg}
            </p>
          ) : null}
          {userError ? (
            <p className="err" style={{ fontSize: 13, marginTop: 10 }}>
              {userError}
            </p>
          ) : null}
        </section>
      ) : null}

      {/* operator settings — admins only */}
      {session.role === "admin" ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>Configurações do cadastro</h2>
          <p className="sub">
            Regras do cadastro de jogadores. O saque cai na chave Pix, então
            os dados bancários são opcionais por padrão.
          </p>
          <label
            style={{ display: "flex", gap: 8, alignItems: "flex-start" }}
          >
            <input
              type="checkbox"
              checked={!!(settings && settings.require_bank_at_signup)}
              disabled={busy || !settings}
              onChange={(e) =>
                saveSetting("require_bank_at_signup", e.target.checked)
              }
              style={{ width: "auto", marginTop: 3 }}
            />
            <span>
              Exigir banco / agência / conta no cadastro
              <br />
              <span className="sub" style={{ fontSize: 12 }}>
                Desligado: o jogador entra só com nome, email, CPF, senha e
                chave Pix, e pode completar os dados depois.
              </span>
            </span>
          </label>
          <label
            style={{
              display: "flex",
              gap: 8,
              alignItems: "flex-start",
              marginTop: 12,
            }}
          >
            <input
              type="checkbox"
              checked={!!(settings && settings.test_accounts_enabled)}
              disabled={busy || !settings}
              onChange={(e) =>
                saveSetting("test_accounts_enabled", e.target.checked)
              }
              style={{ width: "auto", marginTop: 3 }}
            />
            <span>
              Habilitar contas de teste
              <br />
              <span className="sub" style={{ fontSize: 12 }}>
                Desligado: contas de teste não entram, mesmo com a senha
                certa.
              </span>
            </span>
          </label>
          {settingsMsg ? (
            <p className="ok" style={{ fontSize: 13, marginTop: 10 }}>
              {settingsMsg}
            </p>
          ) : null}
          {settingsError ? (
            <p className="err" style={{ fontSize: 13, marginTop: 10 }}>
              {settingsError}
            </p>
          ) : null}
        </section>
      ) : null}

      {/* test accounts — admins only */}
      {session.role === "admin" ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>Contas de teste</h2>
          <p className="sub">
            Contas invisíveis no site, para testes. Entram pelo login normal
            (email + senha). No site, com a janela de conta aberta,
            Ctrl+Shift+T preenche a identidade de teste embutida.
          </p>

          <table className="hist">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Email</th>
                <th>CPF</th>
                <th>Pix</th>
                <th>Criada</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(testAccounts || []).map((a) => (
                <tr key={a.player_id}>
                  <td>{a.name}</td>
                  <td>{a.email}</td>
                  <td>{a.cpf_masked}</td>
                  <td>{a.pix_masked}</td>
                  <td>{(a.created_at || "").slice(0, 10)}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button
                      className="ghost"
                      style={{
                        width: "auto",
                        padding: "4px 10px",
                        fontSize: 12,
                        marginRight: 6,
                      }}
                      onClick={() => {
                        setResetTest(a.player_id);
                        setResetTestPass("");
                        setTestError("");
                        setTestMsg("");
                      }}
                    >
                      Redefinir
                    </button>
                    <button
                      className="danger"
                      style={{ width: "auto", padding: "4px 10px", fontSize: 12 }}
                      onClick={() => doDeleteTestAccount(a.player_id, a.email)}
                    >
                      Remover
                    </button>
                  </td>
                </tr>
              ))}
              {(testAccounts || []).length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ color: "var(--mut)" }}>
                    Nenhuma conta de teste.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>

          <div className="admin-cols" style={{ marginTop: 14 }}>
            <div>
              <b style={{ fontSize: 13 }}>Criar conta de teste</b>
              <Field
                id="ta-name"
                label="Nome completo"
                value={tName}
                onChange={(e) => setTName(e.target.value)}
              />
              <Field
                id="ta-email"
                label="Email"
                value={tEmail}
                onChange={(e) => setTEmail(e.target.value)}
              />
              <Field
                id="ta-cpf"
                label="CPF"
                value={tCpf}
                onChange={(e) => setTCpf(e.target.value)}
              />
              <Field
                id="ta-pix"
                label="Chave Pix"
                value={tPix}
                onChange={(e) => setTPix(e.target.value)}
              />
              <Field
                id="ta-pass"
                label="Senha"
                type="password"
                value={tPass}
                onChange={(e) => setTPass(e.target.value)}
              />
              <button
                disabled={busy}
                style={{ marginTop: 12 }}
                onClick={doCreateTestAccount}
              >
                Criar conta de teste
              </button>
            </div>
            <div>
              <b style={{ fontSize: 13 }}>Redefinir senha</b>
              <label htmlFor="ta-reset">Conta</label>
              <select
                id="ta-reset"
                value={resetTest}
                onChange={(e) => setResetTest(e.target.value)}
              >
                <option value="">— escolha —</option>
                {(testAccounts || []).map((a) => (
                  <option key={a.player_id} value={a.player_id}>
                    {a.email}
                  </option>
                ))}
              </select>
              <Field
                id="ta-reset-pass"
                label="Nova senha"
                type="password"
                value={resetTestPass}
                onChange={(e) => setResetTestPass(e.target.value)}
              />
              <button
                disabled={busy}
                style={{ marginTop: 12 }}
                onClick={doResetTestPassword}
              >
                Redefinir senha
              </button>
            </div>
          </div>

          {testMsg ? (
            <p className="ok" style={{ fontSize: 13, marginTop: 10 }}>
              {testMsg}
            </p>
          ) : null}
          {testError ? (
            <p className="err" style={{ fontSize: 13, marginTop: 10 }}>
              {testError}
            </p>
          ) : null}
        </section>
      ) : null}
    </>
  );
}
