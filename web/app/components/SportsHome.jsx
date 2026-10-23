"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { filterFixtures, betIdentity, validMarkets } from "../../lib/sports.mjs";
import BetBuilder from "./BetBuilder";
import OddsButton from "./OddsButton";

const SPORT_ORDER = [
  "soccer", "basketball", "tennis", "hockey", "volleyball", "futsal",
  "handball", "esports", "baseball", "football", "rugby", "cricket",
];

const SPORT_META = {
  soccer: { label: "Futebol" },
  basketball: { label: "Basquete" },
  tennis: { label: "Tênis" },
  hockey: { label: "Hóquei" },
  volleyball: { label: "Vôlei" },
  futsal: { label: "Futsal" },
  handball: { label: "Handebol" },
  esports: { label: "e-Sports" },
  baseball: { label: "Beisebol" },
  football: { label: "F. Americano" },
  rugby: { label: "Rúgbi" },
  cricket: { label: "Críquete" },
};

// Inline SVG sport marks. Deliberately drawn (not emoji) so the tab strip is
// one visual language at every size and renders identically on every platform.
const SPORT_PATHS = {
  soccer: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.2l3 2.2-1.1 3.5h-3.8L9 9.4z" />
      <path d="M12 3.2v4M4.4 9.6l4.6-.2M19.6 9.6l-4.6-.2M7 19.6l2.6-4.5M17 19.6l-2.6-4.5" />
    </>
  ),
  basketball: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3v18M6 5.2c3 3 3 10.6 0 13.6M18 5.2c-3 3-3 10.6 0 13.6" />
    </>
  ),
  tennis: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M6.2 5.8C9.6 9.2 9.6 14.8 6.2 18.2M17.8 5.8C14.4 9.2 14.4 14.8 17.8 18.2" />
    </>
  ),
  hockey: (
    <>
      <path d="M5 4v8.5a4.5 4.5 0 0 0 4.5 4.5H18" />
      <circle cx="17.5" cy="18" r="2.2" />
    </>
  ),
  volleyball: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3c3.5 4.5 3.5 13.5 0 18M3.4 9.4c4.8.4 12.4 4 15.2 8M20.6 9.4c-4.8.4-12.4 4-15.2 8" />
    </>
  ),
  futsal: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.2l3 2.2-1.1 3.5h-3.8L9 9.4z" />
      <path d="M8.5 4.6l3.5 2.6M15.5 4.6L12 7.2" />
    </>
  ),
  handball: (
    <>
      <circle cx="12" cy="8.4" r="5.4" />
      <path d="M12 3v10.8M7 6.4l4 3M17 6.4l-4 3M6 20.5c2-3.4 10-3.4 12 0" />
    </>
  ),
  esports: (
    <>
      <path d="M4 8.5h16a2 2 0 0 1 2 2.2l-.6 4.4a2.4 2.4 0 0 1-4.2 1.3L15.4 15H8.6l-1.8 1.4A2.4 2.4 0 0 1 2.6 15.1L2 10.7a2 2 0 0 1 2-2.2z" />
      <path d="M7 11.5v3M5.5 13h3M16.6 12.4h.01M18.4 14.2h.01" />
    </>
  ),
  baseball: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M8 4.4c2.4 2.6 2.4 12.6 0 15.2M16 4.4c-2.4 2.6-2.4 12.6 0 15.2" />
    </>
  ),
  football: (
    <>
      <path d="M12 4c4.4 0 8 3.4 8 8s-3.6 8-8 8-8-3.4-8-8 3.6-8 8-8z" />
      <path d="M12 6.6v10.8M8.2 9.6l7.6 4.8M15.8 9.6l-7.6 4.8" />
    </>
  ),
  rugby: (
    <>
      <path d="M12 4.2c3.4 1 6 4.6 6 7.8s-2.6 6.8-6 7.8c-3.4-1-6-4.6-6-7.8s2.6-6.8 6-7.8z" />
      <path d="M10.4 9.6h3.2M10 12h4M10.4 14.4h3.2" />
    </>
  ),
  cricket: (
    <>
      <path d="M6 20l8-14" />
      <path d="M11.5 4.5l3 1.8" />
      <circle cx="17.5" cy="7.5" r="2.2" />
    </>
  ),
};

function SportIcon({ sport, size = 22 }) {
  const inner = SPORT_PATHS[sport] || (
    <circle cx="12" cy="12" r="8.5" />
  );
  return (
    <svg className="sx-icon" width={size} height={size} viewBox="0 0 24 24"
         fill="none" stroke="currentColor" strokeWidth="1.7"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {inner}
    </svg>
  );
}

const PRIMARY_KINDS = new Set(["1x2", "moneyline"]);
const TOTAL_KIND = "total";

const KIND_LABEL = {
  "1x2": "Casa · Empate · Fora",
  moneyline: "Vencedor",
  total: "Total",
  "total-h1": "Total 1º tempo",
  "total-h2": "Total 2º tempo",
  dc: "Dupla chance",
  btts: "Ambas marcam",
  dnb: "Empate anula",
  ah: "Handicap",
  cards: "Cartões amarelos",
  corners: "Escanteios",
  fouls: "Faltas",
  "scorer-h": "Marcador a qualquer momento · Casa",
  "scorer-a": "Marcador a qualquer momento · Fora",
};

// The stats panel rows, in the order a real match screen prints them. Each is
// a stat key from the match-stats feed; a key the feed omits is not shown.
const STAT_ROWS = [
  ["possession", "Posse de bola", "%"],
  ["shots", "Finalizações", ""],
  ["shots_on_target", "No gol", ""],
  ["corners", "Escanteios", ""],
  ["yellow_cards", "Cartões amarelos", ""],
  ["fouls", "Faltas", ""],
];

// the sports whose live clock is minutes — a set/innings sport shows the live
// dot without a misleading number. Same caps the backend derives.
const LIVE_CAP = {
  soccer: 90, futsal: 40, handball: 60, basketball: 48, hockey: 60,
  rugby: 80, football: 60,
};

/** The live clock for one row: prefer the source's own minute, otherwise
 *  advance it locally from the kickoff — minute by minute between polls, with
 *  no extra request to the feed (the score still refreshes every poll). */
function liveLabel(f, nowMs) {
  const raw = String(f.progress || "").trim();
  if (/^(\d+'\d*|\d+\+\d+'|\d+min|HT)$/.test(raw)) return raw;
  const cap = LIVE_CAP[f.sport];
  if (!cap || !f.kickoff) return "";
  const ko = new Date(f.kickoff).getTime();
  if (Number.isNaN(ko)) return "";
  const m = Math.max(0, (nowMs - ko) / 60000);
  if (m >= cap) return cap + "+'";
  if (m < 1) return "1'";
  return Math.floor(m) + "'";
}

function meta(sport) {
  return SPORT_META[sport] || { label: sport || "Outros" };
}

function isLive(f) {
  return /IN_PROGRESS|LIVE/i.test(f.status || "");
}

function isFinal(f) {
  return /FINAL|AET|\bFT\b/i.test(f.status || "");
}

/** A local-time clock that starts empty, so the server and the first client
 *  render agree. It follows Brasília time, the storefront's public clock. */
function LocalClock() {
  const [label, setLabel] = useState("");
  useEffect(() => {
    const tickClock = () => {
      try {
        setLabel(new Date().toLocaleTimeString("pt-BR", {
          hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo",
        }));
      } catch (e) {
        setLabel(new Date().toLocaleTimeString("pt-BR", {
          hour: "2-digit", minute: "2-digit",
        }));
      }
    };
    tickClock();
    const id = setInterval(tickClock, 30000);
    return () => clearInterval(id);
  }, []);
  return (
    <span className="ed-clock" aria-label={label ? "Hora de Brasília: " + label : "Hora de Brasília"}>
      {label || "--:--"} <span aria-hidden="true">BRT</span>
    </span>
  );
}

/** The hero ticket and the board rows share one identity rule. */
function betFor(fixture, market, selection, price) {
  return {
    fixtureKey: fixture.key,
    home: fixture.home,
    away: fixture.away,
    competition: fixture.competition,
    marketKind: market.kind,
    selection,
    price,
    line: market.line == null ? null : market.line,
  };
}

function sameDay(value, ref) {
  if (!value) return false;
  const d = new Date(value);
  return !Number.isNaN(d.getTime()) &&
    d.getFullYear() === ref.getFullYear() &&
    d.getMonth() === ref.getMonth() &&
    d.getDate() === ref.getDate();
}

function kickLabel(iso) {
  if (!iso) return "";
  const text = String(iso);
  if (text.length === 10) return text.slice(8, 10) + "/" + text.slice(5, 7);
  const d = new Date(text);
  if (Number.isNaN(d.getTime())) return text;
  const hhmm = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  if (sameDay(text, new Date())) return hhmm;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }) + " " + hhmm;
}

function tick(kind, i, selections) {
  if (kind === "1x2") return ["1", "X", "2"][i] || selections[i];
  if (kind === "moneyline") return i === 0 ? "1" : "2";
  if (kind === "total") return ["Mais", "Menos"][i] || selections[i];
  if (kind === "dnb" || kind === "ah") return i === 0 ? "1" : "2";
  return selections[i];
}

function pricedMarkets(f) {
  return validMarkets(f);
}

/** The match-stats panel: a two-sided bar per stat the feed carried. Purely
 *  descriptive — it shows what happened, and the count markets settle off the
 *  same numbers. Renders nothing when the source shipped no stats. */
function Stats({ stats }) {
  if (!stats || typeof stats !== "object") return null;
  const rows = STAT_ROWS.filter(([key]) => Array.isArray(stats[key]));
  if (rows.length === 0) return null;
  return (
    <div className="sx-stats">
      {rows.map(([key, label, unit]) => {
        const home = Number(stats[key][0] || 0);
        const away = Number(stats[key][1] || 0);
        const total = home + away || 1;
        const hp = Math.round((home / total) * 100);
        return (
          <div className="sx-stat" key={key}>
            <span className="sx-stat-h">{home}{unit}</span>
            <span className="sx-stat-label">
              {label}
              <i className="sx-stat-bar"><b style={{ width: hp + "%" }} /></i>
            </span>
            <span className="sx-stat-a">{away}{unit}</span>
          </div>
        );
      })}
    </div>
  );
}

/** One fixture row, Sofascore-shaped: state on the left, teams stacked with
 *  the score right-aligned, and the main market's odds in a fixed column.
 *  Extra markets (the total) expand under a "mais mercados" toggle. */
function EventRow({ f, onSelectBet, selectedBets, nowMs, favorite, onFavorite, onBuild, marketView }) {
  const [open, setOpen] = useState(false);
  const markets = pricedMarkets(f);
  const primary = marketView === 'result' ? markets.find(m => PRIMARY_KINDS.has(m.kind)) || markets[0] : markets.find(m=>m.kind===marketView);
  const extras = markets.filter((m) => m !== primary);
  const TeamTag = (f.sport || 'soccer') === 'soccer' ? 'button' : 'div';
  const live = isLive(f);
  const final = isFinal(f);
  const home = f.home_score;
  const away = f.away_score;
  const showScore = live || final;
  const state = live ? liveLabel(f, nowMs) || "AO VIVO" : null;

  const pick = (m, sel, price) => () =>
    onSelectBet &&
    onSelectBet({
      fixtureKey: f.key,
      home: f.home,
      away: f.away,
      competition: f.competition,
      marketKind: m.kind,
      selection: sel,
      price,
      line: m.line == null ? null : m.line,
    });
  const isPicked = (m, sel) => selectedBets?.some((x) => betIdentity(x) === betIdentity({ fixtureKey: f.key, marketKind: m.kind, line: m.line, selection: sel }));

  const renderOdds = (m) => (
    <div className="sx-market-block" key={m.key || m.kind + String(m.line)}><span className="sx-market-label">{KIND_LABEL[m.kind] || m.kind}{m.line != null ? " · " + m.line : ""} · {m.pricing === "market" ? "Provedor" : "Modelo"}</span><div className="sx-odds">
      {m.pricing === "market" ? (
        <span
          className="sx-prov"
          title="Cotação publicada pelo provedor (não é do nosso modelo)"
        >
          mercado
        </span>
      ) : null}
      {m.selections.map((sel, i) => (
        <OddsButton
          key={sel}
          price={m.prices[i]}
          className={"sx-odd" + (isPicked(m, sel) ? " on" : "")}
          disabled={final}
          aria-pressed={!!isPicked(m, sel)}
          title={"Apostar em " + sel + " @ " + m.prices[i].toFixed(2)}
          onClick={pick(m, sel, m.prices[i])}
        >
          <span className="sx-odd-tick">{tick(m.kind, i, m.selections)}</span>
          <span className="sx-odd-price">{m.prices[i].toFixed(2)}</span>
        </OddsButton>
      ))}
    </div></div>
  );

  return (
    <div className={"sx-row" + (live ? " live" : "")}>
      <div className="sx-state">
        <button className="sx-save" aria-label={(favorite ? "Remover favorito: " : "Favoritar: ") + f.home + " × " + f.away} aria-pressed={favorite} onClick={() => onFavorite(f.key)}>{favorite ? "★" : "☆"}</button>
        {live ? (
          <span className="sx-live">
            <i />
            {state}
          </span>
        ) : final ? (
          <span className="sx-final">ENC</span>
        ) : (
          <span className="sx-time">{kickLabel(f.kickoff)}</span>
        )}
      </div>

      <TeamTag className="sx-teams" onClick={TeamTag==='button'?()=>onBuild(f.key):undefined} aria-label={TeamTag==='button'?`Ver partida: ${f.home} × ${f.away}`:undefined}>
        <div className={"sx-team" + (showScore && home != null && (away == null || home > away) ? " lead" : "")}>
          <span className="sx-name">{f.home}</span>
          {showScore ? <span className="sx-score">{home ?? "–"}</span> : null}
        </div>
        <div className={"sx-team" + (showScore && away != null && (home == null || away > home) ? " lead" : "")}>
          <span className="sx-name">{f.away}</span>
          {showScore ? <span className="sx-score">{away ?? "–"}</span> : null}
        </div>
      </TeamTag>

      <div className="sx-markets">
        {primary ? renderOdds(primary) : <span className="sx-nomarket">mercados em atualização</span>}
        <div className="sx-market-actions">
        {(f.sport || 'soccer') === 'soccer' ? <button className="sx-build" onClick={() => onBuild(f.key)}>Criar Aposta <span aria-hidden="true">↗</span></button> : null}
        {extras.length > 0 || f.stats ? (
          <button className="sx-more" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            {open ? "Recolher ▲" : extras.length ? "+" + extras.length + " mercados ▼" : "Estatísticas ▼"}
          </button>
        ) : null}
        </div>
      </div>

      {open ? (
        <div className="sx-extra">
          <Stats stats={f.stats} />
          {extras.map((m) => (
            <div className="sx-extra-row" key={m.key}>
              <span className="sx-extra-kind">
                {KIND_LABEL[m.kind] || m.kind}
                {m.line != null ? " " + m.line : ""}
              </span>
              {renderOdds(m)}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function SportsHome({ sports, liveOnly, onSelectBet, onUseSingleBet, selectedBets, onLive, query = "", loading = false, error = "", updatedAt = null, onRetry, authenticated = false, onCasino, onExplore }) {
  const [builderOpen, setBuilderOpen] = useState(false);
  const [builderKey, setBuilderKey] = useState('');
  const listScroll = useRef(0);
  const openBuilder = key => { listScroll.current=window.scrollY; onExplore?.(); setBuilderKey(key || ''); setBuilderOpen(true); window.setTimeout(() => document.getElementById('sports-workspace')?.scrollIntoView({ block: 'start' }), 0); };
  const closeBuilder = () => { setBuilderOpen(false); window.setTimeout(()=>window.scrollTo({top:listScroll.current,behavior:'instant'}),0); };
  const [filterOpen, setFilterOpen] = useState(false);
  const [marketView, setMarketView] = useState('result');
  const [sport, setSport] = useState(null);
  const [railCollapsed, setRailCollapsed] = useState(false);
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
  });
  const [closed, setClosed] = useState({});
  const [nowMs, setNowMs] = useState(() => Date.now());

  // the live minute advances between polls: it is derived from the kickoff on
  // the client, so a game running at 67' stays 67' → 68' → 69' without asking
  // the feed for a new payload every few seconds
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 10000);
    return () => clearInterval(id);
  }, []);

  const fixtures = useMemo(() => {
    const rows = sports ? sports.fixtures || [] : [];
    return [...rows].sort((a, b) => {
      const rank = (f) => (isLive(f) ? 0 : isFinal(f) ? 2 : 1);
      const d = rank(a) - rank(b);
      if (d !== 0) return d;
      return String(a.kickoff || "").localeCompare(String(b.kickoff || ""));
    });
  }, [sports]);

  const liveCount = fixtures.filter(isLive).length;

  const sportsShown = useMemo(() => {
    const pool = liveOnly ? fixtures.filter(isLive) : fixtures;
    const seen = [...new Set(pool.map((f) => f.sport || "soccer"))];
    return seen.sort((a, b) => {
      const ia = SPORT_ORDER.indexOf(a);
      const ib = SPORT_ORDER.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
    });
  }, [fixtures, liveOnly]);

  const activeSport =
    sport && sportsShown.includes(sport)
      ? sport
      : sportsShown.find((s) => fixtures.some((f) => (f.sport || "soccer") === s && isLive(f))) ||
        sportsShown[0] ||
        null;

  const leagues = [...new Set(fixtures.filter(f => !activeSport || (f.sport || "soccer") === activeSport).map(f => f.competition).filter(Boolean))].sort();
  const shown = useMemo(() => filterFixtures(fixtures, { liveOnly, sport: activeSport, query, date, league, favoritesOnly, favorites, nowMs }), [fixtures, liveOnly, activeSport, query, date, league, favoritesOnly, favorites, nowMs]);
  const featured = shown.find(f=>!isFinal(f)&&favorites.includes(f.key)) || [...shown.filter(f=>!isFinal(f))].sort((a,b)=>Object.keys(b.stats||{}).length-Object.keys(a.stats||{}).length)[0];
  const resetFilters = () => { setDate("all"); setLeague(""); setFavoritesOnly(false); };

  const showHighlight = !liveOnly && !query && !builderOpen;
  const featuredLive = featured ? isLive(featured) : false;
  const heroMarkets = featured ? pricedMarkets(featured) : [];
  const heroMarket = heroMarkets.find((m) => PRIMARY_KINDS.has(m.kind)) || heroMarkets[0] || null;
  const heroPicked = (selection) =>
    !!heroMarket && !!selectedBets?.some((bet) =>
      betIdentity(bet) === betIdentity(betFor(featured, heroMarket, selection, 0))
    );
  const jumpToBoard = (mode) => {
    if (mode === "today") setDate("today");
    if (mode === "live" && onLive) onLive(true);
    window.setTimeout(() => {
      document.getElementById("sports-board")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 30);
  };

  const groups = useMemo(() => {
    const countries = new Map();
    for (const f of shown) {
      const country = f.country || "Internacional";
      if (!countries.has(country)) countries.set(country, new Map());
      const leagues = countries.get(country);
      const league = f.competition || "Outros";
      if (!leagues.has(league)) leagues.set(league, []);
      leagues.get(league).push(f);
    }
    return [...countries.entries()].map(([country, leagues]) => ({
      country,
      leagues: [...leagues.entries()].map(([league, rows]) => ({
        league,
        rows,
        live: rows.filter(isLive).length,
      })),
    }));
  }, [shown]);

  const toggle = (country, league) =>
    setClosed((prev) => {
      const key = country + "|" + league;
      return { ...prev, [key]: !prev[key] };
    });

  return (
    <>
      <nav id="sports-workspace" className="sports-workspace-nav" aria-label="Menu de apostas esportivas" onClick={onExplore}>
        <button aria-pressed={!builderOpen} onClick={() => setBuilderOpen(false)}>Partidas e mercados</button>
        <button aria-pressed={builderOpen} onClick={() => openBuilder()}>Criar Aposta</button>
        <span>Estatísticas e seleções da partida</span>
      </nav>
      {builderOpen ? <BetBuilder key={builderKey} fixtures={fixtures} initialKey={builderKey} query={query} source={sports?.source} loading={loading} error={error} updatedAt={updatedAt} onRetry={onRetry} onUseSingleBet={onUseSingleBet} onBack={closeBuilder} /> : <>
      {showHighlight && featured ? <button className="mobile-feature" onClick={()=> (featured.sport||'soccer')==='soccer'?openBuilder(featured.key):jumpToBoard()}><span>{isLive(featured)?'Ao vivo':'Em destaque'} · {featured.competition}</span><strong>{featured.home} × {featured.away}</strong><b>{isLive(featured)?`${featured.home_score??'—'} : ${featured.away_score??'—'}`:'↗'}</b></button> : null}
      {showHighlight ? (
        <section className="book-highlight" aria-label="Destaque esportivo">
          <svg className="book-field" viewBox="0 0 640 320" fill="none" aria-hidden="true"><rect x="20" y="20" width="600" height="280" rx="2"/><path d="M320 20v280M20 100h80v120H20m600-120h-80v120h80M20 132h30v56H20m600-56h-30v56h30"/><circle cx="320" cy="160" r="52"/><circle cx="320" cy="160" r="3"/></svg>
          <div className="book-highlight-copy">
            <span className="ed-kicker"><i className="live-dot" /> CENTRAL DE APOSTAS</span>
            <h1>O jogo não para.</h1>
            <p>Placares ao vivo. Mercados em um toque.</p>
            <div className="book-stats"><span><b>{liveCount}</b> ao vivo</span><span><b>{fixtures.length}</b> partidas</span><LocalClock /></div>
            <div className="book-actions">
              <button onClick={() => jumpToBoard("live")}>Ao vivo agora</button>
              <button className="ghost" onClick={() => jumpToBoard("today")}>Jogos de hoje</button>
            </div>
          </div>
              <div className="ed-ticket">
                <div className="ed-ticket-head">
                  <span>{featured ? (featuredLive ? "AO VIVO AGORA" : "NA AGENDA") : "A RODADA"}</span>
                  <span className="ed-ticket-no">01</span>
                </div>
                {featured ? (
                  <>
                    <span className="ed-ticket-comp">
                      {[featured.competition, featured.country].filter(Boolean).join(" · ")}
                    </span>
                    <div className="ed-ticket-teams">
                      <div className="ed-ticket-team">
                        <b>{featured.home}</b>
                        {featuredLive ? <strong>{featured.home_score ?? "–"}</strong> : null}
                      </div>
                      <span className="ed-ticket-vs" aria-hidden="true">{featuredLive ? ":" : "VS"}</span>
                      <div className="ed-ticket-team">
                        <b>{featured.away}</b>
                        {featuredLive ? <strong>{featured.away_score ?? "–"}</strong> : null}
                      </div>
                    </div>
                    <div className="ed-ticket-status">
                      {featuredLive ? (
                        <><i className="ed-live-dot" aria-hidden="true" /> {liveLabel(featured, nowMs) || "AO VIVO"}</>
                      ) : kickLabel(featured.kickoff)}
                    </div>
                    {heroMarket ? (
                      <div className="ed-ticket-market">
                        <span className="ed-ticket-label">
                          {KIND_LABEL[heroMarket.kind] || heroMarket.kind}
                          {heroMarket.line != null ? " · " + heroMarket.line : ""}
                          {" · "}{heroMarket.pricing === "market" ? "Provedor" : "Modelo"}
                        </span>
                        <div className="ed-ticket-odds">
                          {heroMarket.selections.map((selection, index) => (
                            <OddsButton
                              key={featured.key + ':' + heroMarket.kind + ':' + String(heroMarket.line) + ':' + selection}
                              price={heroMarket.prices[index]}
                              type="button"
                              className={"ed-ticket-odd" + (heroPicked(selection) ? " on" : "")}
                              aria-pressed={heroPicked(selection)}
                              title={"Adicionar ao boletim: " + selection + " @ " + heroMarket.prices[index].toFixed(2)}
                              onClick={() => onSelectBet?.(betFor(featured, heroMarket, selection, heroMarket.prices[index]))}
                            >
                              <span>{tick(heroMarket.kind, index, heroMarket.selections)}</span>
                              <b>{heroMarket.prices[index].toFixed(2)}</b>
                            </OddsButton>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="ed-ticket-empty">Mercados abrem perto do apito.</div>
                    )}
                    <button type="button" className="ed-ticket-link" onClick={() => jumpToBoard()}>
                      Ver todos os mercados <span aria-hidden="true">↗</span>
                    </button>
                  </>
                ) : (
                  <div className="ed-ticket-empty">
                    As partidas ao vivo aparecem aqui assim que a rodada começa.
                  </div>
                )}
              </div>
        </section>
      ) : null}

      <div className={'sports-board-layout' + (railCollapsed ? ' rail-collapsed' : '')} onClick={onExplore}>
        <aside className="sport-rail" aria-label="Navegação de esportes">
          <div className="sport-rail-head"><span>Explorar</span><button aria-label={railCollapsed ? 'Expandir navegação esportiva' : 'Recolher navegação esportiva'} aria-expanded={!railCollapsed} onClick={() => setRailCollapsed(value => !value)}>{railCollapsed ? '›' : '‹'}</button></div>
          <button className="sport-rail-item" aria-pressed={!!liveOnly} title="Eventos ao vivo" onClick={() => onLive?.(!liveOnly)}><span className="live-dot" /><span className="rail-label">Ao vivo</span><span className="rail-count">{liveCount}</span></button>
          <button className="sport-rail-item" aria-pressed={favoritesOnly} title="Favoritos" onClick={() => setFavoritesOnly(value => !value)}><span aria-hidden="true">☆</span><span className="rail-label">Favoritos</span><span className="rail-count">{favorites.length}</span></button>
          <div className="rail-section-label">Esportes</div>
          {sportsShown.map(item => <button key={item} className="sport-rail-item" aria-pressed={activeSport === item} aria-label={meta(item).label} title={meta(item).label} onClick={() => { setSport(item); setLeague(''); }}><SportIcon sport={item} size={18} /><span className="rail-label">{meta(item).label}</span><span className="rail-count">{fixtures.filter(f => (f.sport || 'soccer') === item && (!liveOnly || isLive(f))).length}</span></button>)}
          <div className="rail-detail">
            <div className="rail-section-label">Competições</div>
            {leagues.slice(0, 6).map(item => <button className="rail-league" key={item} aria-pressed={league === item} onClick={() => setLeague(league === item ? '' : item)}>{item}</button>)}
            <details><summary>Países e ligas</summary>{[...new Set(fixtures.filter(f => !activeSport || (f.sport || 'soccer') === activeSport).map(f => f.country || 'Internacional'))].sort().map(country => <details className="rail-country" key={country}><summary>{country}</summary>{[...new Set(fixtures.filter(f => (f.country || 'Internacional') === country && (!activeSport || (f.sport || 'soccer') === activeSport)).map(f => f.competition).filter(Boolean))].map(item => <button className="rail-league" key={item} aria-pressed={league === item} onClick={() => setLeague(item)}>{item}</button>)}</details>)}</details>
          </div>
        </aside>
      <div id="sports-board" className="ed-board">
        {error ? (
          <section className="sx-feed-error" role="status">
            <div><strong>{sports ? "Atualização indisponível" : "Não conseguimos carregar as partidas"}</strong><p>{error}{sports ? " As últimas partidas carregadas continuam visíveis." : ""}</p></div>
            <button className="ghost" disabled={loading} onClick={onRetry}>{loading ? "Atualizando…" : "Tentar novamente"}</button>
          </section>
        ) : null}
        <div className="sporthead">
          <div>
            <span className="ed-kicker">
              {query ? "RESULTADOS DA BUSCA" : liveOnly ? "EM ANDAMENTO" : "PRÉ-JOGO E AO VIVO"}
            </span>
            <h1>{liveOnly ? "Apostas ao Vivo" : "Apostas Esportivas"}</h1>
            <p className="sub">
              {liveOnly
                ? "Partidas em andamento agora, com placar e cotações em tempo real."
                : "Escolha o esporte, encontre a partida e selecione sua cotação."}
            </p>
          </div>
          <div className="sportfeed">
            {sports ? (
              <>
                <span className="badge b-ok">{liveCount} ao vivo</span>
                <span style={{ color: "var(--mut)", fontSize: 11.5 }}>
                  {loading ? "Atualizando… · " : ""}fonte: {sports.source}
                  {updatedAt ? " · Atualizado às " + new Date(updatedAt).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : ""}
                </span>
              </>
            ) : (
              <span style={{ color: "var(--mut)", fontSize: 12 }}>carregando partidas…</span>
            )}
          </div>
        </div>

        {sports ? (
          <>
            <div className="sx-sports">
              {(liveOnly ? fixtures.filter(isLive) : fixtures).length === 0 ? (
                <span style={{ color: "var(--mut)", fontSize: 12.5 }}>nenhuma partida ao vivo</span>
              ) : null}
              {sportsShown.map((s) => {
                const info = meta(s);
                const count = (liveOnly ? fixtures.filter(isLive) : fixtures).filter(
                  (f) => (f.sport || "soccer") === s
                ).length;
                const live = fixtures.filter((f) => (f.sport || "soccer") === s && isLive(f)).length;
                return (
                  <button
                    key={s}
                    className={"sx-tab" + (s === activeSport ? " on" : "")}
                    aria-pressed={s === activeSport}
                    onClick={() => { setSport(s); setLeague(""); }}
                  >
                    <SportIcon sport={s} size={26} />
                    <span className="sx-tab-text">{info.label}</span>
                    <span className="sx-tab-count">{count}</span>
                    {live ? <span className="sx-tab-live">{live}</span> : null}
                  </button>
                );
              })}
            </div>

            <div className={'sx-toolbar' + (filterOpen?' filters-open':'')}>
              <button className="mobile-filter-trigger" aria-expanded={filterOpen} onClick={()=>setFilterOpen(value=>!value)}>Filtros{date!=='all'||league||favoritesOnly?' · ativos':''}</button>
              <label className="sx-market-view">Mercado<select value={marketView} onChange={e=>setMarketView(e.target.value)}><option value="result">Resultado</option><option value="total">Total</option><option value="btts">Ambas marcam</option><option value="corners">Escanteios</option><option value="cards">Cartões</option></select></label>
              <button className="mobile-live-filter" aria-pressed={!!liveOnly} onClick={()=>onLive?.(!liveOnly)}>Ao vivo</button>
              <label>Quando<select value={date} onChange={e => setDate(e.target.value)}><option value="all">Todas as datas</option><option value="today">Hoje</option><option value="tomorrow">Amanhã</option><option value="upcoming">Próximas partidas</option><option value="results">Resultados</option></select></label>
              <label>Competição<select value={league} onChange={e => setLeague(e.target.value)}><option value="">Todas as competições</option>{leagues.map(l => <option key={l}>{l}</option>)}</select></label>
              <button className={"sx-filter" + (favoritesOnly ? " on" : "")} aria-pressed={favoritesOnly} onClick={() => setFavoritesOnly(v => !v)}>☆ Favoritos ({favorites.length})</button>
              <button className="sx-filter" onClick={resetFilters}>Limpar filtros</button>
            </div>
            <div className="sx-controls">
              <button
                aria-pressed={!!liveOnly}
                className={"sx-filter" + (liveOnly ? " on" : "")}
                onClick={() => onLive && onLive(!liveOnly)}
              >
                {liveOnly ? "somente ao vivo" : "mostrar só ao vivo"}
              </button>
              <span className="sx-controls-note">
                {shown.length} partidas · {groups.length} países
              </span>
            </div>

            {shown.length === 0 ? (
              <section className="panel">
                <p className="sub">
                  {liveOnly
                    ? "Nenhuma partida ao vivo neste esporte agora."
                    : "Nenhuma partida corresponde aos filtros. Experimente outra data, competição ou busca."}
                </p>
              </section>
            ) : (
              <div className="sx-groups">
                {groups.map((group) => (
                  <div className="sx-country" key={group.country}>
                    <div className="sx-country-head">
                      <span className="sx-flag" aria-hidden="true">{group.country.slice(0, 1)}</span>
                      <b>{group.country}</b>
                      <span className="sx-country-count">
                        {group.leagues.reduce((n, l) => n + l.rows.length, 0)}
                      </span>
                    </div>
                    {group.leagues.map((lg) => {
                      const key = group.country + "|" + lg.league;
                      const isClosed = closed[key];
                      return (
                        <div className="sx-league" key={key}>
                          <button className="sx-league-head" aria-expanded={!isClosed} onClick={() => toggle(group.country, lg.league)}>
                            <span className={"sx-caret" + (isClosed ? " closed" : "")}>▾</span>
                            <span className="sx-league-name">{lg.league}</span>
                            {lg.live ? <span className="sx-league-live">{lg.live} ao vivo</span> : null}
                            <span className="sx-league-count">{lg.rows.length}</span>
                          </button>
                          {isClosed ? null : (
                            <div className="sx-league-body">
                              {lg.rows.map((f) => (
                                <EventRow key={f.key} f={f} onSelectBet={onSelectBet}
                                          selectedBets={selectedBets} nowMs={nowMs} favorite={favorites.includes(f.key)} onFavorite={toggleFavorite} onBuild={openBuilder} marketView={marketView} />
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            )}

            <p style={{ fontSize: 11.5, color: "var(--mut)", marginTop: 12 }}>{sports.note}</p>
          </>
        ) : !error ? <div className="sx-loading" role="status">Carregando calendário e mercados…</div> : null}
        <details className="sx-guide"><summary>Entenda os mercados e as cotações</summary><p><b>1 · X · 2:</b> vitória da casa, empate ou vitória do visitante. <b>Total:</b> mais ou menos que a linha indicada. <b>Dupla chance:</b> dois resultados na mesma seleção. <b>Empate anula:</b> devolução em caso de empate.</p><p>As cotações identificadas como Modelo são simuladas; Provedor indica preços publicados pela fonte. O retorno potencial inclui o valor apostado. Partidas encerradas exibem resultados e não aceitam seleções.</p></details>
      </div>
      </div>
      </>}
    </>
  );
}
