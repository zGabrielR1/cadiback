from pathlib import Path
p=Path('web/app/components/SportsHome.jsx')
s=p.read_text(encoding='utf-8')
s=s.replace('import { useEffect, useMemo, useState } from "react";', 'import { useEffect, useMemo, useState } from "react";\nimport SpotlightCard from "./reactbits/SpotlightCard";\nimport { filterFixtures, betIdentity, validMarkets } from "../../lib/sports.mjs";')
a=s.index('  return (f.markets || []).filter(',s.index('function pricedMarkets'))
b=s.index('\n}',a)
s=s[:a]+'  return validMarkets(f);'+s[b:]
s=s.replace('function EventRow({ f, onSelectBet, selectedBets, nowMs })', 'function EventRow({ f, onSelectBet, selectedBets, nowMs, favorite, onFavorite })')
s=s.replace('const isPicked = (sel) =>\n    selectedBets && selectedBets.some((x) => x.fixtureKey === f.key && x.selection === sel);','const isPicked = (m, sel) => selectedBets?.some((x) => betIdentity(x) === betIdentity({ fixtureKey: f.key, marketKind: m.kind, line: m.line, selection: sel }));')
s=s.replace('isPicked(sel)', 'isPicked(m, sel)')
s=s.replace('title={"Apostar em "', 'disabled={final}\n          aria-pressed={!!isPicked(m, sel)}\n          title={"Apostar em "')
s=s.replace('<div className="sx-odds" key={m.key}>','<div className="sx-market-block" key={m.key || m.kind + String(m.line)}><span className="sx-market-label">{KIND_LABEL[m.kind] || m.kind}{m.line != null ? " · " + m.line : ""} · {m.pricing === "market" ? "Provedor" : "Modelo"}</span><div className="sx-odds">')
s=s.replace('      ))}\n    </div>\n  );\n\n  return (','      ))}\n    </div></div>\n  );\n\n  return (',1)
s=s.replace('<div className="sx-state">','<div className="sx-state">\n        <button className="sx-save" aria-label={(favorite ? "Remover favorito: " : "Favoritar: ") + f.home + " × " + f.away} aria-pressed={favorite} onClick={() => onFavorite(f.key)}>{favorite ? "★" : "☆"}</button>',1)
s=s.replace('{extras.length > 0 ? (','{extras.length > 0 || f.stats ? (',1)
s=s.replace('<button className="sx-more" onClick=', '<button className="sx-more" aria-expanded={open} onClick=',1)
s=s.replace('export default function SportsHome({ sports, liveOnly, onSelectBet, selectedBets, onLive })', 'export default function SportsHome({ sports, liveOnly, onSelectBet, selectedBets, onLive, query = "" })')
s=s.replace('  const [sport, setSport] = useState(null);','''  const [sport, setSport] = useState(null);
  const [date, setDate] = useState("all");
  const [league, setLeague] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [favorites, setFavorites] = useState([]);
  useEffect(() => {
    try { const saved = JSON.parse(localStorage.getItem("candi-sport-favorites") || "[]"); if (Array.isArray(saved)) setFavorites(saved.filter(x => typeof x === "string")); } catch {}
  }, []);
  const toggleFavorite = (key) => setFavorites(previous => {
    const next = previous.includes(key) ? previous.filter(x => x !== key) : [...previous, key];
    try { localStorage.setItem("candi-sport-favorites", JSON.stringify(next)); } catch {}
    return next;
  });''')
a=s.index('  const shown = useMemo('); b=s.index('\n  const groups',a)
s=s[:a]+'''  const leagues = [...new Set(fixtures.filter(f => !activeSport || (f.sport || "soccer") === activeSport).map(f => f.competition).filter(Boolean))].sort();
  const shown = useMemo(() => filterFixtures(fixtures, { liveOnly, sport: activeSport, query, date, league, favoritesOnly, favorites, nowMs }), [fixtures, liveOnly, activeSport, query, date, league, favoritesOnly, favorites, nowMs]);
  const featured = shown.find(f => !isFinal(f));
  const resetFilters = () => { setDate("all"); setLeague(""); setFavoritesOnly(false); };
''' +s[b:]
s=s.replace('<div className="sporthead">','''<SpotlightCard className="sx-hero" spotlightColor="#7bf5b4" intensity={0.12}>
        <div className="sx-hero-copy"><span className="sx-eyebrow">CANDIBET / SPORTSBOOK</span>
        <h1>O jogo começa<br /><em>na sua escolha.</em></h1>
        <p>Explore os esportes. Acompanhe cada placar. Encontre seu próximo jogo.</p>
        <div className="sx-metrics"><span><b>{fixtures.length}</b> partidas</span><span><b>{liveCount}</b> ao vivo</span><span><b>{sportsShown.length}</b> esportes</span></div></div>
        <div className="sx-feature"><span className="sx-eyebrow">{featured ? (isLive(featured) ? "EM CAMPO AGORA" : "NA AGENDA") : "SEU PRÓXIMO JOGO"}</span>
          {featured ? <><p>{featured.competition}</p><div className="sx-feature-teams"><b>{featured.home}</b><span>{isLive(featured) ? `${featured.home_score ?? "–"} : ${featured.away_score ?? "–"}` : "VS"}</span><b>{featured.away}</b></div><small>{isLive(featured) ? "Ao vivo · " + liveLabel(featured, nowMs) : kickLabel(featured.kickoff)}</small></> : <p>As partidas disponíveis aparecerão aqui.</p>}
        </div>
      </SpotlightCard>
      <div className="sporthead">''',1)
s=s.replace('onClick={() => setSport(s)}','aria-pressed={s === activeSport}\n                  onClick={() => { setSport(s); setLeague(""); }}')
s=s.replace('<div className="sx-controls">','''<div className="sx-toolbar">
            <label>Quando<select value={date} onChange={e => setDate(e.target.value)}><option value="all">Todas as datas</option><option value="today">Hoje</option><option value="tomorrow">Amanhã</option><option value="upcoming">Próximas partidas</option><option value="results">Resultados</option></select></label>
            <label>Competição<select value={league} onChange={e => setLeague(e.target.value)}><option value="">Todas as competições</option>{leagues.map(l => <option key={l}>{l}</option>)}</select></label>
            <button className={"sx-filter" + (favoritesOnly ? " on" : "")} aria-pressed={favoritesOnly} onClick={() => setFavoritesOnly(v => !v)}>☆ Favoritos ({favorites.length})</button>
            <button className="sx-filter" onClick={resetFilters}>Limpar filtros</button>
          </div>
          <div className="sx-controls">''',1)
s=s.replace('className={"sx-filter" + (liveOnly ? " on" : "")}','aria-pressed={!!liveOnly}\n              className={"sx-filter" + (liveOnly ? " on" : "")}',1)
s=s.replace('Nenhuma partida encontrada para este esporte.', 'Nenhuma partida corresponde aos filtros. Experimente outra data, competição ou busca.')
s=s.replace('<button className="sx-league-head" onClick=', '<button className="sx-league-head" aria-expanded={!isClosed} onClick=')
s=s.replace('selectedBets={selectedBets} nowMs={nowMs}', 'selectedBets={selectedBets} nowMs={nowMs} favorite={favorites.includes(f.key)} onFavorite={toggleFavorite}')
s=s.replace('      ) : null}\n    </>\n  );\n}', '      ) : <div className="sx-loading" role="status">Carregando calendário e mercados…</div>}\n      <details className="sx-guide"><summary>Entenda os mercados e as cotações</summary><p><b>1 · X · 2:</b> vitória da casa, empate ou vitória do visitante. <b>Total:</b> mais ou menos que a linha indicada. <b>Dupla chance:</b> dois resultados na mesma seleção. <b>Empate anula:</b> devolução em caso de empate.</p><p>As cotações identificadas como Modelo são simuladas; Provedor indica preços publicados pela fonte. O retorno potencial inclui o valor apostado. Partidas encerradas exibem resultados e não aceitam seleções.</p></details>\n    </>\n  );\n}',1)
p.write_text(s,encoding='utf-8')
p=Path('web/app/components/CasinoHome.jsx');s=p.read_text(encoding='utf-8').replace('import { api, BRL }','import SpotlightCard from "./reactbits/SpotlightCard";\nimport { api, BRL }');s=s.replace('      <div\n        className="hero carousel"','      <SpotlightCard\n        spotlightColor="#7bf5b4" intensity={0.13}\n        className="hero carousel"',1);s=s.replace('      </div>\n\n      <div className="chips"','      </SpotlightCard>\n\n      <div className="chips"',1);p.write_text(s,encoding='utf-8')
p=Path('web/app/page.jsx');s=p.read_text(encoding='utf-8').replace('import SportsHome from "./components/SportsHome";','import SportsHome from "./components/SportsHome";\nimport { betIdentity } from "../lib/sports.mjs";');s=s.replace('x.fixtureKey === b.fixtureKey && x.selection === b.selection','betIdentity(x) === betIdentity(b)');s=s.replace('            sports={sports}','            query={query}\n            sports={sports}');p.write_text(s,encoding='utf-8')
p=Path('web/app/components/Header.jsx');s=p.read_text(encoding='utf-8').replace('<div className="logo" onClick={() => onCasino("Todos")} style={{ cursor: "pointer" }}>','<button className="logo" aria-label="Candibet início" onClick={() => onCasino("Todos")}>').replace('Candi<span>bet</span>\n          </div>','Candi<span>bet</span>\n          </button>');s=s.replace('placeholder="Buscar jogos, provedores…"','aria-label={view === "sport" ? "Buscar times, ligas ou países" : "Buscar jogos ou provedores"}\n            placeholder={view === "sport" ? "Times, ligas, países…" : "Buscar jogos, provedores…"}');p.write_text(s,encoding='utf-8')
p=Path('web/app/components/BetslipTray.jsx');s=p.read_text(encoding='utf-8').replace('import { BRL }','import { betIdentity } from "../../lib/sports.mjs";\nimport { BRL }').replace('key={b.fixtureKey + b.selection}','key={betIdentity(b)}');p.write_text(s,encoding='utf-8')
