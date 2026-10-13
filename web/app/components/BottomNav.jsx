"use client";

/** Mobile bottom navigation (F1 extract from page.jsx). */
export default function BottomNav({ view, liveOnly, onCasino, onSport, onAccount, onCash }) {
  return (
    <nav className="bottomnav">
      <button
        className={view === "casino" ? "on" : ""}
        onClick={() => onCasino("Todos")}
      >
        Cassino
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
      <button className={view === "account" ? "on" : ""} onClick={onAccount}>
        Minha Conta
      </button>
      <button onClick={onCash}>Caixa</button>
    </nav>
  );
}
