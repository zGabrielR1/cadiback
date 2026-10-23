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
  onHelp,
}) {
  return (
    <>
      <div className="topbar">
        <span>18+ · Jogue com responsabilidade</span>
        <span>
          <b>Seu jogo. Seu ritmo.</b>
          <button className="topbar-help" onClick={onHelp}>Ajuda</button>
        </span>
      </div>

      <header className="sticky">
        <div className="hwrap">
          <button className="logo" aria-label="Candibet início" onClick={() => onSport(false)}>
            Candi<span>bet</span>
          </button>
          <nav className="main">
            <button className={view === "sport" && !liveOnly ? "on" : ""} onClick={() => onSport(false)}>Esportes</button>
            <button className={view === "sport" && liveOnly ? "on" : ""} onClick={() => onSport(true)}><span className="live-dot" /> Ao vivo</button>
            <button className={view === "casino" ? "on" : ""} onClick={() => onCasino("Todos")}>Cassino {!player ? <span className="nav-lock" aria-label="Login necessário">↗</span> : null}</button>
            {player ? <button className={view === "casino" && casinoCat === "Slots" ? "on" : ""} onClick={() => onCasino("Slots")}>Slots</button> : null}
          </nav>
          <div className="spacer" />
          <input
            id="search"
            aria-label={view === "sport" ? "Buscar times, ligas ou países" : "Buscar jogos ou provedores"}
            placeholder={view === "sport" ? "Times, ligas, países…" : "Buscar jogos, provedores…"}
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
          <button className="ghost header-promos" onClick={onPromos}>
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
          <button className="ghost header-cash" onClick={onCash}>
            Depositar
          </button>
          <button onClick={onAccount}>{player ? "Minha conta" : "Entrar"}</button>
        </div>
      </header>
    </>
  );
}
