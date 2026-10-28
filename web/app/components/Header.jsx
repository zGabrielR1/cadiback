"use client";

import { useEffect, useRef, useState } from "react";
import { BRL } from "../../lib/api";
import UIIcon from "./UIIcon";
import { usePanelResize } from "../../lib/usePanelResize";

export default function Header({ view, casinoCat, unlocked, liveOnly, query, profile, player, admin, theme, design, favoritesOnly, onFavorites, onCasino, onSport, onQuery, onPromos, onAdmin, onTheme, onCash, onAccount, onHelp, onPortal, onCreateBet }) {
  const [mobileSearch, setMobileSearch] = useState(false);
  const [searchExpanded, setSearchExpanded] = useState(false);
  const header = useRef(null);
  useEffect(() => {
    const node = header.current;
    if (!node) return;
    const update = () => document.body.style.setProperty("--header-height", node.getBoundingClientRect().height + "px");
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => { observer.disconnect(); document.body.style.removeProperty("--header-height"); };
  }, []);
  const searchResize = usePanelResize("casa-search-size", 245, 300, 1, 180);
  return <>
    <div className="topbar"><span>{player ? "18+ · Jogue com responsabilidade" : "Cotações esportivas e análise de partidas"}</span><span><b>Acompanhe cada mercado.</b><button className="topbar-help" onClick={onPortal}>Dados</button><button className="topbar-help" onClick={onHelp}>Ajuda</button></span></div>
    <header ref={header} className="sticky variant-header">
      <div className="hwrap">
        <a className="logo" aria-label="Candibet início" href="/">candi<span>bet</span></a>
        <nav className="main" aria-label="Navegação principal">
          <button className={view === "sport" && !liveOnly && !favoritesOnly ? "on" : ""} aria-current={view === "sport" && !liveOnly && !favoritesOnly ? "page" : undefined} onClick={() => onSport(false)}>Esportes</button>
          <button className={view === "sport" && liveOnly ? "on" : ""} onClick={() => onSport(true)}><span className="live-dot" />Ao vivo</button>
          <button className={view === "sport" && favoritesOnly ? "on" : ""} onClick={onFavorites}>Favoritos</button>
          {(design === "blue" || design === "auteur") ? <><button className="nav-aux" onClick={onPortal}>Dados</button><button className="nav-aux" onClick={onHelp}>Ajuda</button></> : null}
          {player ? <button className="nav-builder" onClick={onCreateBet}>Criar Aposta</button> : null}
          {player ? <button className={view === "casino" ? "on" : ""} onClick={() => onCasino(casinoCat || "Todos")}>Cassino</button> : null}
        </nav>
        <button className="header-search-toggle" aria-label="Buscar" aria-expanded={mobileSearch} onClick={() => { setMobileSearch((v) => !v); if (!mobileSearch) requestAnimationFrame(() => document.getElementById("mobile-search")?.focus()); }}><UIIcon name="search" size={18} /></button>
        <div className="spacer" />
        <label className={"header-search" + (searchExpanded ? " search-expanded" : "")} style={{"--search-width": searchResize.size.width + "px"}}><UIIcon name="search" size={17} /><input id="search" onFocus={() => setSearchExpanded(true)} aria-label={view === "casino" ? "Buscar jogos ou provedores" : "Buscar times, ligas ou países"} placeholder={view === "casino" ? "Jogos, provedores…" : "Times, ligas, países…"} value={query} onChange={e => onQuery(e.target.value)} />{query ? <button className="search-clear" aria-label="Limpar busca" onClick={() => { onQuery(""); requestAnimationFrame(() => document.getElementById("search")?.focus()); }}><UIIcon name="close" size={15} /></button> : null}<button type="button" className="search-expand" aria-label={searchExpanded ? "Recolher busca" : "Ampliar busca"} aria-expanded={searchExpanded} onClick={() => setSearchExpanded(value => !value)}><UIIcon name="expand" size={16}/></button><button type="button" className="search-resize" aria-label="Redimensionar busca" title="Arraste ou use as setas para ajustar a largura" {...searchResize.handle} onPointerDown={event => { setSearchExpanded(false); searchResize.handle.onPointerDown(event); }}><UIIcon name="grip" size={14}/></button></label>
        {profile ? <span className="bal">{BRL(profile.available_minor)}{profile.bonus_minor > 0 ? " + " + BRL(profile.bonus_minor) + " bônus" : ""}</span> : null}
        <button className="ghost header-theme" aria-label={theme === "light" ? "Ativar tema escuro" : "Ativar tema claro"} title={theme === "light" ? "Tema escuro" : "Tema claro"} onClick={onTheme}><UIIcon name={theme === "light" ? "moon" : "sun"} size={18} /></button>
        {player ? <button className="ghost header-cash" onClick={onCash}>Depositar</button> : null}
        {player || admin ? <details className="header-more"><summary>Mais</summary><div>{player ? <button onClick={onPromos}>Promoções</button> : null}{admin ? <button onClick={onAdmin}>Painel</button> : null}<button onClick={onPortal}>Dados</button><button onClick={onHelp}>Ajuda</button></div></details> : null}
        <button className={"header-account" + (player ? " is-member" : "")} title={player ? "Minha conta" : "Entrar"} aria-label={player ? "Minha conta" : "Entrar"} onClick={onAccount}><UIIcon name="user" size={18} />{!player ? <span>Entrar</span> : null}</button>
      </div>
      {mobileSearch ? <div className="header-mobile-search"><label className="header-search"><UIIcon name="search" size={17} /><input id="mobile-search" aria-label={view === "casino" ? "Buscar jogos ou provedores" : "Buscar times, ligas ou países"} placeholder={view === "casino" ? "Jogos, provedores…" : "Times, ligas, países…"} value={query} onChange={e => onQuery(e.target.value)} />{query ? <button className="search-clear" aria-label="Limpar busca" onClick={() => { onQuery(""); requestAnimationFrame(() => document.getElementById("mobile-search")?.focus()); }}><UIIcon name="close" size={15} /></button> : null}</label></div> : null}
    </header>
  </>;
}