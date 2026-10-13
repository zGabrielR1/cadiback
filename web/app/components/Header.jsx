"use client";

import { BRL } from "../../lib/api";

/** Site topbar + sticky header (F1 extract from page.jsx). All navigation
 * stays in the shell; the page passes the current view state and the
 * go/query/cashier/account callbacks as props. */
export default function Header({
  view,
  casinoCat,
  liveOnly,
  query,
  profile,
  player,
  admin,
  theme,
  onCasino,
  onSport,
  onQuery,
  onPromos,
  onAdmin,
  onTheme,
  onCash,
  onAccount,
}) {
  return (
    <>
      <div className="topbar">
        <span>18+ · Jogue com responsabilidade</span>
        <span>
          Candibet · <b>Réplica 1:1 de Alta Fidelidade</b>
        </span>
      </div>

      <header className="sticky">
        <div className="hwrap">
          <div className="logo" onClick={() => onCasino("Todos")} style={{ cursor: "pointer" }}>
            Candi<span>bet</span>
          </div>
          <nav className="main">
            <button
              className={view === "casino" && casinoCat === "Todos" ? "on" : ""}
              onClick={() => onCasino("Todos")}
            >
              Cassino
            </button>
            <button
              className={view === "casino" && casinoCat === "Slots" ? "on" : ""}
              onClick={() => onCasino("Slots")}
            >
              Slots
            </button>
            <button
              className={view === "casino" && casinoCat === "Crash" ? "on" : ""}
              onClick={() => onCasino("Crash")}
            >
              Crash
            </button>
            <button
              className={view === "sport" && !liveOnly ? "on" : ""}
              onClick={() => onSport(false)}
            >
              Esportes
            </button>
            <button
              className={view === "sport" && liveOnly ? "on" : ""}
              onClick={() => onSport(true)}
            >
              Ao Vivo
            </button>
          </nav>
          <div className="spacer" />
          <input
            id="search"
            placeholder="Buscar jogos, provedores…"
            value={query}
            onChange={(e) => onQuery(e.target.value)}
          />
          {profile ? (
            <span className="bal">
              {BRL(profile.available_minor)}
              {profile.bonus_minor > 0
                ? " + " + BRL(profile.bonus_minor) + " bônus"
                : ""}
            </span>
          ) : null}
          <button className="ghost" onClick={onPromos}>
            Promoções
          </button>
          {admin ? (
            <button className="ghost" onClick={onAdmin}>
              Painel
            </button>
          ) : null}
          <button className="ghost" onClick={onTheme}>
            {theme === "light" ? "Escuro" : "Claro"}
          </button>
          <button className="ghost" onClick={onCash}>
            Caixa
          </button>
          <button onClick={onAccount}>{player ? "Minha conta" : "Entrar"}</button>
        </div>
      </header>
    </>
  );
}
