"use client";

import { useMemo, useState } from "react";

const SPORT_ORDER = [
  "soccer", "basketball", "tennis", "hockey", "volleyball", "futsal",
  "handball", "esports", "baseball", "football", "rugby", "cricket",
];

const SPORT_META = {
  soccer: { label: "Futebol", icon: "⚽" },
  basketball: { label: "Basquete", icon: "🏀" },
  tennis: { label: "Tênis", icon: "🎾" },
  hockey: { label: "Hóquei", icon: "🏒" },
  volleyball: { label: "Vôlei", icon: "🏐" },
  futsal: { label: "Futsal", icon: "🥅" },
  handball: { label: "Handebol", icon: "🤾" },
  esports: { label: "e-Sports", icon: "🎮" },
  baseball: { label: "Beisebol", icon: "⚾" },
  football: { label: "F. Americano", icon: "🏈" },
  rugby: { label: "Rúgbi", icon: "🏉" },
  cricket: { label: "Críquete", icon: "🏏" },
};

const PRIMARY_KINDS = new Set(["1x2", "moneyline"]);

function meta(sport) {
  return SPORT_META[sport] || { label: sport || "Outros", icon: "🎯" };
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
  if (kind === "total") return i === 0 ? "Mais" : "Menos";
  return selections[i];
}

function pricedMarkets(f) {
  return (f.markets || []).filter(
    (m) => m.prices && m.prices.length === m.selections.length && m.prices.length > 0
  );
}

/** One fixture row, Sofascore-shaped: state on the left, teams stacked with
 *  the score right-aligned, and the main market's odds in a fixed column.
 *  Extra markets (the total) expand under a "mais mercados" toggle. */
function EventRow({ f, onSelectBet, selectedBets }) {
  const [open, setOpen] = useState(false);
  const markets = pricedMarkets(f);
  const primary = markets.find((m) => PRIMARY_KINDS.has(m.kind)) || markets[0];
  const extras = markets.filter((m) => m !== primary);
  const live = isLive(f);
  const final = isFinal(f);
  const home = f.home_score;
  const away = f.away_score;
  const showScore = live || final;

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
    });
  const isPicked = (sel) =>
    selectedBets && selectedBets.some((x) => x.fixtureKey === f.key && x.selection === sel);

  const renderOdds = (m) => (
    <div className="sx-odds" key={m.key}>
      {m.selections.map((sel, i) => (
        <button
          key={sel}
          className={"sx-odd" + (isPicked(sel) ? " on" : "")}
          title={"Apostar em " + sel + " @ " + m.prices[i].toFixed(2)}
          onClick={pick(m, sel, m.prices[i])}
        >
          <span className="sx-odd-tick">{tick(m.kind, i, m.selections)}</span>
          <span className="sx-odd-price">{m.prices[i].toFixed(2)}</span>
        </button>
      ))}
    </div>
  );

  return (
    <div className={"sx-row" + (live ? " live" : "")}>
      <div className="sx-state">
        {live ? (
          <span className="sx-live">
            <i />
            {f.progress || "AO VIVO"}
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
        {extras.length > 0 ? (
          <button className="sx-more" onClick={() => setOpen((v) => !v)}>
            {open ? "menos mercados ▲" : "mais mercados ▼"}
          </button>
        ) : null}
      </div>

      {open && extras.length > 0 ? (
        <div className="sx-extra">
          {extras.map((m) => (
            <div className="sx-extra-row" key={m.key}>
              <span className="sx-extra-kind">
                Total {m.line != null ? m.line : ""}
              </span>
              {renderOdds(m)}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function SportsHome({ sports, liveOnly, onSelectBet, selectedBets, onLive }) {
  const [sport, setSport] = useState(null);
  const [closed, setClosed] = useState({});

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

  const shown = useMemo(() => {
    let pool = fixtures;
    if (liveOnly) pool = pool.filter(isLive);
    if (activeSport) pool = pool.filter((f) => (f.sport || "soccer") === activeSport);
    return pool;
  }, [fixtures, liveOnly, activeSport]);

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
                fonte: {sports.source}
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
                  onClick={() => setSport(s)}
                >
                  <span className="sx-tab-icon">{info.icon}</span>
                  {info.label}
                  <span className="sx-tab-count">{count}</span>
                  {live ? <span className="sx-tab-live">{live}</span> : null}
                </button>
              );
            })}
          </div>

          <div className="sx-controls">
            <button
              className={"sx-filter" + (liveOnly ? " on" : "")}
              onClick={() => onLive && onLive(!liveOnly)}
            >
              {liveOnly ? "● somente ao vivo" : "○ mostrar só ao vivo"}
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
                  : "Nenhuma partida encontrada para este esporte."}
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
                        <button className="sx-league-head" onClick={() => toggle(group.country, lg.league)}>
                          <span className={"sx-caret" + (isClosed ? " closed" : "")}>▾</span>
                          <span className="sx-league-name">{lg.league}</span>
                          {lg.live ? <span className="sx-league-live">{lg.live} ao vivo</span> : null}
                          <span className="sx-league-count">{lg.rows.length}</span>
                        </button>
                        {isClosed ? null : (
                          <div className="sx-league-body">
                            {lg.rows.map((f) => (
                              <EventRow key={f.key} f={f} onSelectBet={onSelectBet}
                                        selectedBets={selectedBets} />
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
      ) : null}
    </>
  );
}
