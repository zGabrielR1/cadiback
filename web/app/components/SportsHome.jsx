"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { filterFixtures, betIdentity, validMarkets, matchState } from "../../lib/sports.mjs";
import BetBuilder from "./BetBuilder";
import MarketDetail from "./MarketDetail";
import OddsButton from "./OddsButton";
import UIIcon from "./UIIcon";
import { matchKeyFromUrl, navigateMatch } from "../../lib/match-link.mjs";

const SPORT_ORDER = [
  "soccer", "basketball", "tennis", "hockey", "volleyball", "futsal",
  "handball", "esports", "baseball", "football", "rugby", "cricket",
];

const PAGE_SIZE = 8;

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
  return matchState(f).live;
}

function isFinal(f) {
  return matchState(f).ended;
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

function Countdown({ iso, nowMs }) {
  const target = useMemo(() => {
    if (!iso) return null;
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? null : d.getTime();
  }, [iso]);
  if (!target || target <= nowMs) return null;
  const diff = target - nowMs;
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  const secs = Math.floor((diff % 60000) / 1000);
  const parts = [];
  if (days > 0) parts.push(days + "d");
  if (hours > 0 || days > 0) parts.push(String(hours).padStart(2, "0") + "h");
  parts.push(String(mins).padStart(2, "0") + "m");
  if (diff < 3600000) parts.push(String(secs).padStart(2, "0") + "s");
  return <span className="sx-countdown" aria-label="Tempo até o início">{parts.join(" ")}</span>;
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
function EventRow({ f, onSelectBet, selectedBets, nowMs, favorite, onFavorite, onBuild, marketView, onFocus, focused, paused }) {
  const [open, setOpen] = useState(false);
  const markets = pricedMarkets(f);
  const primary = marketView === 'result' ? markets.find(m => PRIMARY_KINDS.has(m.kind)) || markets[0] : markets.find(m=>m.kind===marketView) || markets[0];
  const prevScore = useRef({ home: f.home_score, away: f.away_score });
  const [scoreFlash, setScoreFlash] = useState(false);
  useEffect(() => {
    const prev = prevScore.current;
    if (isLive(f) && (prev.home !== f.home_score || prev.away !== f.away_score)) {
      setScoreFlash(true);
      const t = setTimeout(() => setScoreFlash(false), 1600);
      prevScore.current = { home: f.home_score, away: f.away_score };
      return () => clearTimeout(t);
    }
    prevScore.current = { home: f.home_score, away: f.away_score };
    return undefined;
  }, [f.home_score, f.away_score, f]);
  const extras = markets.filter((m) => m !== primary);
  const TeamTag = onBuild ? 'button' : 'div';
  const live = isLive(f);
  const final = isFinal(f);
  const availability = matchState(f);
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

  const renderOdds = (m) => {
    const label = (KIND_LABEL[m.kind] || m.kind) + (m.line != null ? " · " + m.line : "") + " · " + (m.pricing === "market" ? "Provedor" : "Modelo");
    return (
    <div className="sx-market-block" key={m.key || m.kind + String(m.line)}><span className="sx-market-label" aria-hidden="true">{label}</span><div className="sx-odds" role="group" aria-label={label}>
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
          disabled={!availability.selectable || paused}
          aria-pressed={!!isPicked(m, sel)}
          title={"Cotacao: " + sel + " @ " + m.prices[i].toFixed(2)}
          onClick={pick(m, sel, m.prices[i])}
        >
          <span className="sx-odd-tick">{tick(m.kind, i, m.selections)}</span>
          <span className="sx-odd-price">{m.prices[i].toFixed(2)}</span>
        </OddsButton>
      ))}
    </div></div>
    );
  };

  return (
    <div className={"sx-row" + (live ? " live" : "")} data-focused={focused || undefined}>
      <div className="sx-state">
        <button className="sx-save" aria-label={(favorite ? "Remover favorito: " : "Favoritar: ") + f.home + " × " + f.away} aria-pressed={favorite} onClick={() => onFavorite(f.key)}><UIIcon name="star" size={19} fill={favorite ? "currentColor" : "none"} /></button>
        {live ? (
          <span className="sx-live" aria-label={"Ao vivo" + (state ? ", " + state : "")}>
            <i aria-hidden="true" />
            {state}
          </span>
        ) : availability.unavailable ? (
          <span className="sx-final" aria-label={availability.label}>—</span>
        ) : final ? (
          <span className="sx-final">ENC</span>
        ) : (
          <span className="sx-time">{kickLabel(f.kickoff)}</span>
        )}
      </div>

      <TeamTag data-detail-key={f.key} className="sx-teams" onClick={TeamTag==='button'?()=>(onFocus || onBuild)(f.key):undefined} aria-label={TeamTag==='button'?`Ver partida: ${f.home} × ${f.away}`:undefined}>
        {availability.unavailable ? <span className="sx-unavailable-label">{availability.label}</span> : null}
        <div className={"sx-team" + (showScore && home != null && (away == null || home > away) ? " lead" : "")}>
          <span className="club-team-initial" aria-hidden="true">{f.home.slice(0, 2).toUpperCase()}</span><span className="sx-name">{f.home}</span>
          {showScore ? <span className={"sx-score" + (scoreFlash ? " sx-score-flash" : "")}>{home ?? "–"}</span> : null}
        </div>
        <div className={"sx-team" + (showScore && away != null && (home == null || away > home) ? " lead" : "")}>
          <span className="club-team-initial" aria-hidden="true">{f.away.slice(0, 2).toUpperCase()}</span><span className="sx-name">{f.away}</span>
          {showScore ? <span className={"sx-score" + (scoreFlash ? " sx-score-flash" : "")}>{away ?? "–"}</span> : null}
        </div>
      </TeamTag>

      <div className="sx-markets">
        {primary ? renderOdds(primary) : <span className="sx-nomarket">mercados em atualização</span>}
        <div className="sx-market-actions">
        {onBuild ? <button data-detail-key={f.key} className="sx-build" onClick={() => onBuild(f.key)}>Ver detalhes <UIIcon name="arrow" size={16} /></button> : null}
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

export default function SportsHome({ sports, liveOnly, onSelectBet, onUseSingleBet, selectedBets, onLive, query = "", onQuery, loading = false, error = "", updatedAt = null, onRetry, authenticated = false, onCasino, onExplore, favoritesOnly = false, onFavoritesOnly, guestInvitation, design = "classic", builderRequest = 0, onBuilderHandled, slowLoading = false }) {
  const [detailKey, setDetailKey] = useState(null);
  const [builderOpen, setBuilderOpen] = useState(false);
  useEffect(() => {
    const sync = () => {
      const key = matchKeyFromUrl(window.location.href);
      if (key !== null) setBuilderOpen(false);
      setDetailKey(key);
    };
    sync();
    window.addEventListener("popstate", sync);
    window.addEventListener("operator-match-change", sync);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener("operator-match-change", sync);
    };
  }, []);
  const [focusedKey, setFocusedKey] = useState(null);
  const detailOrigin = useRef(null);
  const detailScroll = useRef(0);
  const openDetail = key => { detailOrigin.current = document.activeElement; detailScroll.current = window.scrollY; navigateMatch(key); setDetailKey(key); window.scrollTo({top:0,behavior:'instant'}); };
  const detailWasOpen = useRef(false);
  useEffect(() => {
    if (detailKey !== null) { detailWasOpen.current = true; return; }
    if (!detailWasOpen.current) return;
    detailWasOpen.current = false;
    if (builderOpen) return;
    const frame = requestAnimationFrame(() => {
      window.scrollTo({ top: detailScroll.current, behavior: "instant" });
      const origin = detailOrigin.current;
      if (origin?.isConnected) origin.focus({ preventScroll: true });
      else {
        const selector = origin?.classList.contains("sx-build") ? ".sx-build" : origin?.classList.contains("sx-teams") ? ".sx-teams" : ".market-trend-detail";
        document.querySelector(selector + '[data-detail-key="' + CSS.escape(String(origin?.dataset.detailKey || "")) + '"]')?.focus({ preventScroll: true });
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [detailKey, builderOpen]);
  const closeDetail = () => { navigateMatch(null); setDetailKey(null); };
  const [builderKey, setBuilderKey] = useState('');
  const listScroll = useRef(0);
  const openBuilder = key => { if (!authenticated) return; listScroll.current=window.scrollY; onExplore?.(); setBuilderKey(key || ''); setBuilderOpen(true); window.setTimeout(() => document.getElementById('sports-workspace')?.scrollIntoView({ block: 'start' }), 0); };
  const closeBuilder = () => { setBuilderOpen(false); window.setTimeout(()=>window.scrollTo({top:listScroll.current,behavior:'instant'}),0); };
  useEffect(() => {
    if (!builderRequest || !authenticated) return;
    navigateMatch(null, { replace: true }); setDetailKey(null); setBuilderKey(""); setBuilderOpen(true); onBuilderHandled?.();
  }, [builderRequest, authenticated, onBuilderHandled]);
  const [moreSports, setMoreSports] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [marketView, setMarketView] = useState('result');
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [sport, setSport] = useState(null);
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [date, setDate] = useState("all");
  const [league, setLeague] = useState("");
  const setFavoritesOnly = value => onFavoritesOnly?.(typeof value === "function" ? value(favoritesOnly) : value);
  const [favorites, setFavorites] = useState([]);
  useEffect(() => {
    const read = () => {
      try {
        const saved = JSON.parse(localStorage.getItem("candi-sport-favorites") || "[]");
        if (Array.isArray(saved)) setFavorites([...new Set(saved.filter(x => typeof x === "string"))]);
      } catch {}
    };
    const sync = event => { if (event.key === "candi-sport-favorites" || event.key === null) read(); };
    read();
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);
  // Enter a collection or begin a new search across sports. Subsequent explicit
  // sport choices narrow that collection/search until the next entry.
  const previousDiscovery = useRef({ searching: false, favoritesOnly: false });
  useEffect(() => {
    const searching = !!query.trim();
    const previous = previousDiscovery.current;
    if ((searching && !previous.searching) || (favoritesOnly && !previous.favoritesOnly)) {
      setSport("all"); setLeague(""); setClosed({});
    }
    previousDiscovery.current = { searching, favoritesOnly };
  }, [query, favoritesOnly]);
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

  const savedInFeed = useMemo(() => fixtures.filter(f => favorites.includes(f.key)), [fixtures, favorites]);
  const discoveryPool = favoritesOnly ? savedInFeed : fixtures;
  const liveCount = discoveryPool.filter(isLive).length;
  const sportPool = liveOnly ? discoveryPool.filter(isLive) : discoveryPool;
  const sportsShown = useMemo(() => {
    const pool = liveOnly ? discoveryPool.filter(isLive) : discoveryPool;
    const seen = [...new Set(pool.map((f) => f.sport || "soccer"))];
    return seen.sort((a, b) => {
      const ia = SPORT_ORDER.indexOf(a);
      const ib = SPORT_ORDER.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
    });
  }, [discoveryPool, liveOnly]);

  const navSports = moreSports ? sportsShown : sportsShown.slice(0, 5);
  const chooseSport = item => { setSport(item); setLeague(""); setClosed({}); requestAnimationFrame(() => document.getElementById("sports-board")?.scrollIntoView({block:"start"})); };

  const activeSport = sport === "all" ? null : sport ||
    ((query.trim() || favoritesOnly) ? null :
      sportsShown.find(s => fixtures.some(f => (f.sport || "soccer") === s && isLive(f))) || sportsShown[0] || null);

  const leagues = [...new Set(fixtures.filter(f => !activeSport || (f.sport || "soccer") === activeSport).map(f => f.competition).filter(Boolean))].sort();
  const shown = useMemo(() => filterFixtures(fixtures, { liveOnly, sport: activeSport, query, date, league, favoritesOnly, favorites, nowMs }), [fixtures, liveOnly, activeSport, query, date, league, favoritesOnly, favorites, nowMs]);
  const visible = useMemo(() => shown.slice(0, visibleCount), [shown, visibleCount]);
  useEffect(() => { setVisibleCount(PAGE_SIZE); }, [query, date, league, favoritesOnly, liveOnly, activeSport]);
  const resetFilters = () => { setDate("all"); setLeague(""); setFavoritesOnly(false); onQuery?.(""); onLive?.(false); setSport("all"); setClosed({}); };
  const recoverFavorites = () => { setDate("all"); setLeague(""); onQuery?.(""); onLive?.(false); setSport("all"); setClosed({}); };
  const activeFilters = [
    ...(sport && sport !== "all" ? [{ key: "sport", label: meta(sport).label, clear: () => chooseSport("all") }] : []),
    ...(liveOnly ? [{ key: "live", label: "Ao vivo", clear: () => onLive?.(false) }] : []),
    ...(date !== "all" ? [{ key: "date", label: ({ today: "Hoje", tomorrow: "Amanhã", upcoming: "Próximas partidas", results: "Resultados" })[date], clear: () => setDate("all") }] : []),
    ...(league ? [{ key: "league", label: league, clear: () => setLeague("") }] : []),
    ...(favoritesOnly ? [{ key: "favorites", label: "Favoritos", clear: () => setFavoritesOnly(false) }] : []),
    ...(query ? [{ key: "query", label: `Busca: ${query}`, clear: () => onQuery?.("") }] : []),
  ];

  const groups = useMemo(() => {
    const countries = new Map();
    for (const f of visible) {
      const country = f.country || "Internacional";
      if (!countries.has(country)) countries.set(country, new Map());
      const leagues = countries.get(country);
      const league = f.competition || "Outros";
      const key = JSON.stringify([f.sport || "soccer", league]);
      if (!leagues.has(key)) leagues.set(key, []);
      leagues.get(key).push(f);
    }
    return [...countries.entries()].map(([country, leagues]) => ({
      country,
      leagues: [...leagues.values()].map(rows => ({
        league: rows[0].competition || "Outros",
        sport: rows[0].sport || "soccer",
        rows,
        live: rows.filter(isLive).length,
      })),
    }));
  }, [visible]);

  const toggle = (country, sport, league) =>
    setClosed((prev) => {
      const key = JSON.stringify([country, sport, league]);
      return { ...prev, [key]: !prev[key] };
    });

  if (detailKey !== null) return <MarketDetail key={detailKey} pending={!sports && loading} fixture={fixtures.find(f => f.key === detailKey)} source={sports?.source} updatedAt={updatedAt} loading={loading} error={error} onRetry={onRetry} authenticated={authenticated} onSelectBet={onSelectBet} selectedBets={selectedBets} onLogin={() => onSelectBet?.()} onBack={closeDetail} onResearch={() => { const key=detailKey; navigateMatch(null); setDetailKey(null); openBuilder(key); }} favorite={favorites.includes(detailKey)} onFavorite={toggleFavorite} />;

  const featured = shown.filter(f => matchState(f).selectable && pricedMarkets(f).length).slice(0, design === "blue" ? 2 : 3);
  const focus = shown.find(f => f.key === focusedKey) || shown[0];
  const focusMarket = focus ? pricedMarkets(focus)[0] : null;
  const showFeatured = design !== "auteur" && !liveOnly && !query && !favoritesOnly && featured.length > 0;
  const boardHeading = <div className="sporthead"><div><h1>{favoritesOnly ? "Suas partidas favoritas" : liveOnly ? "Mercados ao vivo" : query ? "Resultados da busca" : design === "auteur" ? (activeSport ? meta(activeSport).label : "Esportes") : design === "blue" ? "O jogo começa nos números." : "Mercados esportivos"}</h1><p className="sub">{favoritesOnly ? `Favoritos neste calendário: ${savedInFeed.length} de ${favorites.length} salvos neste navegador.` : liveOnly ? "Partidas em andamento, placares e cotações." : query ? `Resultados para “${query}” · ${activeSport ? meta(activeSport).label : "todos os esportes"}.` : "Escolha o esporte, encontre a partida e consulte suas cotações."}</p></div><div className="sportfeed">{sports ? <><span className="badge b-ok">{liveCount} ao vivo</span><span>{loading ? "Atualizando… · " : ""}Fonte: {sports.source}{updatedAt ? " · " + new Date(updatedAt).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : ""}</span></> : <span>{error ? "Fonte temporariamente indisponível" : "Carregando partidas…"}</span>}</div></div>;

  return <>
    <div id="sports-workspace" />
    {builderOpen ? <BetBuilder key={builderKey} fixtures={fixtures} initialKey={builderKey} query={query} source={sports?.source} loading={loading} error={error} updatedAt={updatedAt} onRetry={onRetry} onUseSingleBet={onUseSingleBet} onBack={closeBuilder} /> : <div className={"sports-board-layout market-workspace" + (railCollapsed ? " rail-collapsed" : "") + (showFeatured ? "" : " no-highlights")} data-feed-state={!sports || !fixtures.length ? "empty" : "ready"} onClick={onExplore}>
      <section className="workspace-featured" aria-label="Partidas em destaque">
        {design === "blue" || design === "auteur" ? boardHeading : null}
        {design === "auteur" && shown.length > 0 && !query && !favoritesOnly ? <div className="auteur-scores" aria-label="Placares em destaque">{shown.filter(f => matchState(f).selectable).slice(0,3).map(f => <button key={f.key} onClick={() => setFocusedKey(f.key)}><span><b>{isLive(f) ? liveLabel(f, nowMs) || "Ao vivo" : kickLabel(f.kickoff)}</b> {f.competition}</span><strong>{f.home}<b>{isLive(f) ? f.home_score ?? "—" : "—"}</b></strong><strong>{f.away}<b>{isLive(f) ? f.away_score ?? "—" : "—"}</b></strong></button>)}</div> : null}
        {showFeatured ? <div className="market-trends"><div className="market-trends-heading"><h2>{design === "blue" ? "Em campo hoje" : "Próximos jogos"}</h2><p>Ao vivo e próximos jogos com cotações disponíveis.</p></div><div className="market-trends-grid">{featured.map(f => {
          const market = pricedMarkets(f).find(m => PRIMARY_KINDS.has(m.kind)) || pricedMarkets(f)[0];
          const live = isLive(f);
          return <article className="market-trend" key={f.key}>
            <div className="feature-meta"><span>{live ? "Ao vivo" : kickLabel(f.kickoff)} · {f.competition}</span>{!live ? <Countdown iso={f.kickoff} nowMs={nowMs} /> : null}{design === "blue" ? <button className="sx-save" aria-label={(favorites.includes(f.key) ? "Remover favorito: " : "Favoritar: ") + f.home + " × " + f.away} aria-pressed={favorites.includes(f.key)} onClick={() => toggleFavorite(f.key)}><UIIcon name="star" size={18} fill={favorites.includes(f.key) ? "currentColor" : "none"} /></button> : null}</div>
            <h3><button data-detail-key={f.key} className="market-trend-detail" onClick={() => openDetail(f.key)}>{design === "blue" ? <><span className="feature-team"><span className="feature-initial" aria-hidden="true">{f.home.slice(0,2).toUpperCase()}</span>{f.home}</span><span className="feature-clock"><b>{live ? `${f.home_score ?? "—"} : ${f.away_score ?? "—"}` : kickLabel(f.kickoff)}</b><small>{live ? liveLabel(f, nowMs) || "Ao vivo" : "Pré-jogo"}</small></span><span className="feature-team feature-away"><span className="feature-initial" aria-hidden="true">{f.away.slice(0,2).toUpperCase()}</span>{f.away}</span></> : <>{f.home} × {f.away}</>}</button></h3>
            <p className="feature-provenance">{KIND_LABEL[market.kind] || market.kind}{market.line != null ? " · " + market.line : ""} · {market.pricing === "market" ? "Provedor" : "Modelo"}</p>
            <div className="market-trend-odds">{market.selections.map((selection,i) => {
              const bet = betFor(f,market,selection,market.prices[i]);
              const selected = selectedBets?.some(item => betIdentity(item) === betIdentity(bet));
              return <OddsButton key={selection} disabled={loading || !!error} price={market.prices[i]} aria-pressed={!!selected} title={"Cotação: " + selection} onClick={() => authenticated ? onSelectBet?.(bet) : openDetail(f.key)}><span>{tick(market.kind,i,market.selections)}</span><b>{market.prices[i].toFixed(2)}</b></OddsButton>;
            })}</div>
          </article>;
        })}</div></div> : null}
      </section>
      <aside className="sport-rail" aria-label="Navegação de esportes">
        <div className="sport-rail-head"><span>{design === "blue" ? "Esportes" : "Explorar"}</span><button aria-label={railCollapsed ? "Expandir navegação esportiva" : "Recolher navegação esportiva"} aria-expanded={!railCollapsed} onClick={() => setRailCollapsed(value => !value)}>{railCollapsed ? "›" : "‹"}</button></div>
        {design === "classic" ? <>
        <button className="sport-rail-item" aria-pressed={!!liveOnly} title="Eventos ao vivo" onClick={() => onLive?.(!liveOnly)}><UIIcon name="live" size={18} /><span className="rail-label">Ao vivo</span><span className="rail-count">{liveCount}</span></button>
        <button className="sport-rail-item" aria-pressed={favoritesOnly} title="Favoritos" onClick={() => setFavoritesOnly(value => !value)}><UIIcon name="star" size={18} /><span className="rail-label">Favoritos</span><span className="rail-count">{favorites.length}</span></button>
        <div className="rail-section-label">Esportes</div>
        </> : null}
        <button className="sport-rail-item" aria-pressed={!activeSport} aria-label="Todos os esportes" title="Todos os esportes" onClick={() => chooseSport("all")}><UIIcon name="data" size={18}/><span className="rail-label">Todos os esportes</span><span className="rail-count">{sportPool.length}</span></button>
        {navSports.map(item => <button key={item} className="sport-rail-item" aria-pressed={activeSport === item} aria-label={meta(item).label} title={meta(item).label} onClick={() => chooseSport(item)}><SportIcon sport={item} size={18} /><span className="rail-label">{meta(item).label}</span><span className="rail-count">{sportPool.filter(f => (f.sport || "soccer") === item).length}</span></button>)}
          {sportsShown.length > 5 ? <button className="sport-more" aria-expanded={moreSports} onClick={() => setMoreSports(value => !value)}>{moreSports ? "Menos esportes" : "Outros esportes"}</button> : null}
          <div className="rail-detail">
            <div className="rail-section-label">Competições</div>
            {leagues.slice(0, 6).map(item => <button className="rail-league" key={item} aria-pressed={league === item} onClick={() => setLeague(league === item ? '' : item)}>{item}</button>)}
            <details><summary>Países e ligas</summary>{[...new Set(fixtures.filter(f => !activeSport || (f.sport || 'soccer') === activeSport).map(f => f.country || 'Internacional'))].sort().map(country => <details className="rail-country" key={country}><summary>{country}</summary>{[...new Set(fixtures.filter(f => (f.country || 'Internacional') === country && (!activeSport || (f.sport || 'soccer') === activeSport)).map(f => f.competition).filter(Boolean))].map(item => <button className="rail-league" key={item} aria-pressed={league === item} onClick={() => setLeague(item)}>{item}</button>)}</details>)}</details>
          </div>
      </aside>
      <div className="workspace-tabs sx-sports" aria-label="Escolher esporte"><button className={"sx-tab" + (!activeSport ? " on" : "")} aria-pressed={!activeSport} aria-label="Todos os esportes" onClick={() => chooseSport("all")}><UIIcon name="data" size={19}/><span>Todos</span><span className="sx-tab-count">{sportPool.length}</span></button>{navSports.map(item => <button className={"sx-tab" + (item === activeSport ? " on" : "")} aria-pressed={item === activeSport} key={item} onClick={() => chooseSport(item)}><SportIcon sport={item} size={19} /><span>{meta(item).label}</span><span className="sx-tab-count">{sportPool.filter(f => (f.sport || "soccer") === item).length}</span></button>)}
      {sportsShown.length > 5 ? <button className="mobile-sport-more" aria-expanded={moreSports} onClick={() => setMoreSports(value => !value)}>{moreSports ? "Menos esportes" : "Outros esportes"}</button> : null}</div>
      <main id="sports-board" className="ed-board" tabIndex={-1}>
        {design === "classic" ? boardHeading : sports ? <div className="board-section-heading"><h2>{liveOnly ? "Partidas ao vivo" : "Todas as partidas"}</h2><span>{shown.length} partidas</span></div> : null}
        <p className="sr-only" role="status">{shown.length} partidas encontradas.</p>
        {design === "classic" ? guestInvitation : null}
        {error && sports ? <section className="sx-feed-error" role="status"><div><strong>{sports ? "Atualização indisponível" : "Não conseguimos carregar as partidas"}</strong><p>{error}{sports ? " As últimas partidas carregadas continuam visíveis." : ""}</p></div><button className="ghost" disabled={loading} onClick={onRetry}>{loading ? "Atualizando…" : "Tentar novamente"}</button></section> : null}
        {sports ? <>
            {design === "blue" || design === "auteur" ? <div className="blue-toolbar">
              <button className={"blue-live-toggle" + (liveOnly ? " on" : "")} aria-pressed={!!liveOnly} onClick={() => onLive?.(!liveOnly)}>Ao vivo</button>
              <label>Mercado<select value={marketView} onChange={e=>setMarketView(e.target.value)}><option value="result">Resultado</option><option value="total">Total</option><option value="btts">Ambas marcam</option><option value="corners">Escanteios</option><option value="cards">Cartões</option></select></label>
              <label>Quando<select value={date} onChange={e=>setDate(e.target.value)}><option value="all">Todas as datas</option><option value="today">Hoje</option><option value="tomorrow">Amanhã</option><option value="upcoming">Próximas partidas</option><option value="results">Resultados</option></select></label>
              <details className="blue-extra-filters"><summary>Filtros{league || favoritesOnly ? " · ativos" : ""}</summary><div>
                <label>Competição<select value={league} onChange={e=>setLeague(e.target.value)}><option value="">Todas as competições</option>{leagues.map(l=><option key={l}>{l}</option>)}</select></label>
                <button className="ghost" aria-pressed={favoritesOnly} onClick={()=>setFavoritesOnly(v=>!v)}>Favoritos ({favorites.length})</button>
                <button className="ghost" onClick={resetFilters}>Limpar filtros</button>
              </div></details>
            </div> : <>
            <div className={'sx-toolbar' + (filterOpen?' filters-open':'')}>
              <button className="mobile-filter-trigger" aria-expanded={filterOpen} onClick={()=>setFilterOpen(value=>!value)}>Filtros{date!=='all'||league||favoritesOnly?' · ativos':''}</button>
              <label className="sx-market-view">Mercado<select value={marketView} onChange={e=>setMarketView(e.target.value)}><option value="result">Resultado</option><option value="total">Total</option><option value="btts">Ambas marcam</option><option value="corners">Escanteios</option><option value="cards">Cartões</option></select></label>
              <button className="mobile-live-filter" aria-pressed={!!liveOnly} onClick={()=>onLive?.(!liveOnly)}>Ao vivo</button>
              <label>Quando<select value={date} onChange={e => setDate(e.target.value)}><option value="all">Todas as datas</option><option value="today">Hoje</option><option value="tomorrow">Amanhã</option><option value="upcoming">Próximas partidas</option><option value="results">Resultados</option></select></label>
              <label>Competição<select value={league} onChange={e => setLeague(e.target.value)}><option value="">Todas as competições</option>{leagues.map(l => <option key={l}>{l}</option>)}</select></label>
              <button className={"sx-filter" + (favoritesOnly ? " on" : "")} aria-pressed={favoritesOnly} onClick={() => setFavoritesOnly(v => !v)}><UIIcon name="star" size={15} /> Favoritos ({favorites.length})</button>
              <button className="sx-filter" onClick={resetFilters}>Limpar filtros</button>
            </div>
            </>}
            {(design === "blue" || design === "auteur") && activeFilters.length > 0 ? <div className="blue-active-filters" aria-label="Filtros ativos">
              {activeFilters.map(filter => <button key={filter.key} className="ghost" aria-label={`Remover filtro: ${filter.label}`} onClick={filter.clear}><span>{filter.label}</span><UIIcon name="close" size={14} /></button>)}
              <button className="ghost blue-reset-filters" onClick={resetFilters}>Limpar tudo</button>
            </div> : null}
            {design === "blue" ? <div className="blue-board-columns"><span>Partida / horário</span><span>Cotações · mercado selecionado</span></div> : null}
            <div className={"sx-controls" + (design === "blue" ? " blue-legacy-controls" : "")}>
              <button
                aria-pressed={!!liveOnly}
                className={"sx-filter" + (liveOnly ? " on" : "")}
                onClick={() => onLive && onLive(!liveOnly)}
              >
                {liveOnly ? "somente ao vivo" : "mostrar só ao vivo"}
              </button>
              <span className="sx-controls-note">
                {visibleCount < shown.length ? `Mostrando ${visible.length} de ${shown.length} partidas` : `${shown.length} partidas · ${groups.length} países`}
              </span>
            </div>

            {shown.length === 0 ? (
              <section className="panel">
                {!fixtures.length ? <><UIIcon name="data" size={30}/><h3>Sem partidas disponíveis agora.</h3><p className="sub">O calendário ainda não trouxe eventos. Consulte novamente em instantes.</p><button className="ghost" onClick={onRetry} disabled={loading}>Atualizar calendário</button></> : <>

                <p className="sub">
                  {favoritesOnly
                    ? !favorites.length ? "Você ainda não salvou partidas." : !savedInFeed.length ? "Seus favoritos não estão no calendário atual." : "Nenhum favorito corresponde aos filtros."
                    : liveOnly
                    ? activeSport ? "Nenhuma partida ao vivo neste esporte agora." : "Nenhuma partida ao vivo agora."
                    : query
                      ? `Nenhuma partida para “${query}”.`
                      : "Nenhuma partida corresponde aos filtros. Experimente outra data, competição ou busca."}
                </p>
                {favoritesOnly ? <><p className="sub">{!favorites.length ? "Use a estrela ao lado de uma partida para encontrá-la aqui. Seus favoritos ficam salvos neste navegador." : !savedInFeed.length ? "As partidas continuam salvas e reaparecem quando estiverem disponíveis na fonte." : "Remova os filtros para consultar todas as partidas que você salvou."}</p><button className="ghost" onClick={savedInFeed.length ? recoverFavorites : resetFilters}>{savedInFeed.length ? "Mostrar todos os favoritos" : "Explorar partidas"}</button></> : <button className="ghost" onClick={() => { resetFilters(); requestAnimationFrame(() => document.getElementById("search")?.focus()); }}>Limpar filtros e busca</button>}
                </>}
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
                      const key = JSON.stringify([group.country, lg.sport, lg.league]);
                      const isClosed = closed[key];
                      return (
                        <div className="sx-league" key={key}>
                          <button className="sx-league-head" aria-expanded={!isClosed} onClick={() => toggle(group.country, lg.sport, lg.league)}>
                            <span className={"sx-caret" + (isClosed ? " closed" : "")}>▾</span>
                            <span className="sx-league-name">{design === "blue" ? group.country + " / " : ""}{!activeSport ? meta(lg.sport).label + " · " : ""}{lg.league}</span>
                            {lg.live ? <span className="sx-league-live">{lg.live} ao vivo</span> : null}
                            <span className="sx-league-count">{lg.rows.length}</span>
                          </button>
                          {isClosed ? null : (
                            <div className="sx-league-body">
                              {lg.rows.map((f) => (
                                <EventRow key={f.key} f={f} onSelectBet={authenticated ? onSelectBet : () => openDetail(f.key)}
                                          selectedBets={selectedBets} paused={loading || !!error} nowMs={nowMs} favorite={favorites.includes(f.key)} onFavorite={toggleFavorite} onBuild={openDetail} onFocus={design === "auteur" ? key => { setFocusedKey(key); if (window.matchMedia("(max-width:760px)").matches) requestAnimationFrame(() => document.querySelector(".auteur-research")?.scrollIntoView({block:"start"})); } : undefined} focused={design === "auteur" && focus?.key === f.key} marketView={marketView} />
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
            {visibleCount < shown.length ? (
              <button className="sx-load-more" onClick={() => setVisibleCount(count => count + PAGE_SIZE)}>
                Mostrar mais {Math.min(PAGE_SIZE, shown.length - visibleCount)} partidas
              </button>
            ) : null}

          <p className="source-note">Fonte do calendário: {sports.source || "Não informada"}. {sports.note}</p>
        </> : <section className={"sports-feed-state" + (error ? " feed-failed" : "")} aria-busy={loading} role="status"><UIIcon name={error ? "data" : "live"} size={30}/><h2>{error ? "As partidas ainda não chegaram." : slowLoading ? "A conexão está demorando." : "Preparando as partidas."}</h2><p>{error ? "O feed não respondeu desta vez. Tente carregar o calendário novamente." : slowLoading ? "Você pode tentar novamente sem perder suas preferências." : "Buscando o calendário, os placares e as cotações mais recentes."}</p>{error || slowLoading ? <button className="ghost" onClick={onRetry}>Tentar novamente</button> : <div className="sports-skeleton" aria-hidden="true">{[1,2,3].map(row => <div key={row}><i/><span/><b/></div>)}</div>}</section>}
        {sports && fixtures.length > 0 ? <details className="sx-guide"><summary>Entenda os mercados e as cotações</summary><p><b>1 · X · 2:</b> vitória da casa, empate ou vitória do visitante. <b>Total:</b> mais ou menos que a linha indicada. <b>Dupla chance:</b> dois resultados na mesma seleção. <b>Empate anula:</b> devolução em caso de empate.</p><p>As cotações identificadas como Modelo são simuladas; Provedor indica preços publicados pela fonte. As cotações são decimais e podem mudar. Partidas encerradas exibem resultados.</p></details> : null}
      </main>
      {design === "auteur" ? <aside className="auteur-research" aria-label="Contexto da partida"><div className="auteur-desk-title"><h2>Partida em foco</h2><UIIcon name="arrow" size={16} /></div>{focus ? <><div className="auteur-focus"><span>{isLive(focus) ? "Ao vivo · " + (liveLabel(focus, nowMs) || "Em andamento") : matchState(focus).selectable ? "Pré-jogo · " + kickLabel(focus.kickoff) : matchState(focus).label}</span><h3>{focus.home}<br />{focus.away}</h3><strong className="auteur-focus-score">{isLive(focus) || isFinal(focus) ? `${focus.home_score ?? "—"} : ${focus.away_score ?? "—"}` : matchState(focus).unavailable ? matchState(focus).label : kickLabel(focus.kickoff)}</strong><p>{focus.competition}</p></div><section><h3>Leitura do mercado</h3><p>Compare as cotações e consulte a origem de cada mercado.</p><dl><div><dt>Mercado em foco</dt><dd>{focusMarket ? KIND_LABEL[focusMarket.kind] || focusMarket.kind : "Em atualização"}</dd></div><div><dt>Precificação</dt><dd>{focusMarket ? focusMarket.pricing === "market" ? "Provedor" : "Modelo" : "Não informada"}</dd></div></dl><button className="auteur-detail-link" onClick={() => openDetail(focus.key)}>Explorar todos os mercados <UIIcon name="arrow" size={16}/></button></section><section><h3>Dados da partida</h3><p>{focus.stats ? "Consulte as estatísticas fornecidas para esta partida na visão detalhada." : "A fonte ainda não disponibilizou estatísticas para esta partida."}</p></section>{authenticated ? <section className="auteur-slip-empty"><h3>Seu boletim</h3><p>{selectedBets?.length ? `${selectedBets.length} seleções no boletim. Confira o valor antes de confirmar.` : "Escolha uma cotação para começar."}</p></section> : null}</> : <p>{loading ? "Carregando partidas…" : "Escolha outro esporte ou remova os filtros para encontrar uma partida."}</p>}</aside> : null}
    </div>}
  </>;
}
