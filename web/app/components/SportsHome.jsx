"use client";

import { useEffect, useMemo, useState } from "react";
import SpotlightCard from "./reactbits/SpotlightCard";
import { filterFixtures, betIdentity, validMarkets } from "../../lib/sports.mjs";

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
function EventRow({ f, onSelectBet, selectedBets, nowMs, favorite, onFavorite }) {
  const [open, setOpen] = useState(false);
  const markets = pricedMarkets(f);
  const primary = markets.find((m) => PRIMARY_KINDS.has(m.kind)) || markets[0];
  const total = markets.find((m) => m.kind === TOTAL_KIND) || null;
  const extras = markets.filter((m) => m !== primary && m !== total);
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
        <button
          key={sel}
          className={"sx-odd" + (isPicked(m, sel) ? " on" : "")}
          disabled={final}
          aria-pressed={!!isPicked(m, sel)}
          title={"Apostar em " + sel + " @ " + m.prices[i].toFixed(2)}
          onClick={pick(m, sel, m.prices[i])}
        >
          <span className="sx-odd-tick">{tick(m.kind, i, m.selections)}</span>
          <span className="sx-odd-price">{m.prices[i].toFixed(2)}</span>
        </button>
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

      <div className="sx-teams">
        <div className={"sx-team" + (showScore && home != null && (away == null || home > away) ? " lead" : "")}>
          <span className="sx-name">{f.home}</span>
          {showScore ? <span className="sx-score">{home ?? "–"}</span> : null}
        </div>
        <div className={"sx-team" + (showScore && away != null && (home == null || away > home) ? " lead" : "")}>
          <span className="sx-name">{f.away}</span>
          {showScore ? <span className="sx-score">{away ?? "–"}</span> : null}
        </div>
      </div>

      <div className="sx-markets">
        {primary ? renderOdds(primary) : <span className="sx-nomarket">mercados em atualização</span>}
        {total ? renderOdds(total) : null}
        {extras.length > 0 || f.stats ? (
          <button className="sx-more" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            {open ? "menos mercados ▲" : "+" + extras.length + " mercados ▼"}
          </button>
        ) : null}
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

export default function SportsHome({ sports, liveOnly, onSelectBet, selectedBets, onLive, query = "", loading = false, error = "", updatedAt = null, onRetry }) {
  const [sport, setSport] = useState(null);
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
  const featured = shown.find(f => !isFinal(f));
  const resetFilters = () => { setDate("all"); setLeague(""); setFavoritesOnly(false); };

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
      <SpotlightCard className="sx-hero" spotlightColor="#7bf5b4" intensity={0.12}>
        <div className="sx-hero-copy"><span className="sx-eyebrow">CANDIBET / SPORTSBOOK</span>
        <h1>O jogo começa<br /><em>na sua escolha.</em></h1>
        <p>Explore os esportes. Acompanhe cada placar. Encontre seu próximo jogo.</p>
        <div className="sx-metrics"><span><b>{fixtures.length}</b> partidas</span><span><b>{liveCount}</b> ao vivo</span><span><b>{sportsShown.length}</b> esportes</span></div></div>
        <div className="sx-feature"><span className="sx-eyebrow">{featured ? (isLive(featured) ? "EM CAMPO AGORA" : "NA AGENDA") : "SEU PRÓXIMO JOGO"}</span>
          {featured ? <><p>{featured.competition}</p><div className="sx-feature-teams"><b>{featured.home}</b><span>{isLive(featured) ? `${featured.home_score ?? "–"} : ${featured.away_score ?? "–"}` : "VS"}</span><b>{featured.away}</b></div><small>{isLive(featured) ? "Ao vivo · " + liveLabel(featured, nowMs) : kickLabel(featured.kickoff)}</small></> : <p>As partidas disponíveis aparecerão aqui.</p>}
        </div>
      </SpotlightCard>
      {error ? (
        <section className="sx-feed-error" role="status">
          <div><strong>{sports ? "Atualização indisponível" : "Não conseguimos carregar as partidas"}</strong><p>{error}{sports ? " As últimas partidas carregadas continuam visíveis." : ""}</p></div>
          <button className="ghost" disabled={loading} onClick={onRetry}>{loading ? "Atualizando…" : "Tentar novamente"}</button>
        </section>
      ) : null}
      <div className="sporthead">
        <div>
          <h1>{liveOnly ? "Apostas ao Vivo" : "Apostas Esportivas"}</h1>
          <p className="sub">
            {liveOnly
              ? "Partidas em andamento agora, com placar e cotações em tempo real."
              : "Separadas por esporte e competição, com placares e melhores mercados."}
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

          <div className="sx-toolbar">
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
                                        selectedBets={selectedBets} nowMs={nowMs} favorite={favorites.includes(f.key)} onFavorite={toggleFavorite} />
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
    </>
  );
}
