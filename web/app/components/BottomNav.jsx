"use client";
import { useState, useRef, useEffect } from "react";
import UIIcon from "./UIIcon";

export default function BottomNav({ view, authenticated, liveOnly, unlocked, betCount, onCasino, onSport, onAccount, onCash, onPortal, onFavorites, onPromos, onCreateBet }) {
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef(null);
  useEffect(() => {
    if (!moreOpen) return undefined;
    const handler = (e) => {
      if (moreRef.current && !moreRef.current.contains(e.target)) setMoreOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [moreOpen]);

  const primary = [
    { name: "Esportes", icon: "home", active: view === "sport" && !liveOnly, action: () => onSport(false) },
    { name: "Ao vivo", icon: "live", active: view === "sport" && liveOnly, action: () => onSport(true) },
    { name: authenticated ? "Cassino" : "Dados", icon: "data", active: view === (authenticated ? "casino" : "dados"), action: authenticated ? () => onCasino("Todos") : onPortal },
  ];
  const overflow = [
    { name: "Favoritos", icon: "star", action: () => { onFavorites?.(); setMoreOpen(false); } },
    ...(authenticated ? [{ name: "Criar Aposta", icon: "play", action: () => { onCreateBet?.(); setMoreOpen(false); } }, { name: "Caixa", icon: "wallet", action: () => { onCash?.(); setMoreOpen(false); } }] : []),
    ...(authenticated ? [{ name: "Promoções", icon: "info", action: () => { onPromos?.(); setMoreOpen(false); } },
    { name: "Minha conta", icon: "user", action: () => { onAccount?.(); setMoreOpen(false); } }] : []),
  ];

  return (
    <nav className="bottomnav" aria-label="Navegação móvel">
      {primary.map(item => (
        <button key={item.name} className={item.active ? "on" : ""} aria-current={item.active ? "page" : undefined} onClick={item.action}>
          <UIIcon name={item.icon} size={21} />
          {authenticated && item.name === "Esportes" && betCount > 0 ? <span className="bottomnav-badge" aria-label={`${betCount} seleções`}>{betCount}</span> : null}
          <span>{item.name}</span>
        </button>
      ))}
      <div className="bottomnav-more" ref={moreRef}>
        <button className={moreOpen ? "on" : ""} aria-expanded={moreOpen} onClick={() => setMoreOpen(v => !v)} aria-label="Mais opções">
          <UIIcon name="filter" size={21} />
          <span>Mais</span>
        </button>
        {moreOpen ? (
          <div className="bottomnav-overflow" role="menu">
            {overflow.map(item => (
              <button key={item.name} role="menuitem" onClick={item.action}>
                <UIIcon name={item.icon} size={18} />
                <span>{item.name}</span>
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </nav>
  );
}