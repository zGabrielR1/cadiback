"use client";

import { useMemo, useState } from "react";

function when(iso) {
  if (!iso) return "";
  const text = String(iso);
  if (text.length === 10) return text.split("-").reverse().join("/");
  const d = new Date(text);
  if (Number.isNaN(d.getTime())) return text;
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isLive(f) {
  return /IN_PROGRESS|LIVE/i.test(f.status || "");
}

export default function SportsHome({ sports, liveOnly, onSelectBet, selectedBets }) {
  const [league, setLeague] = useState("Todos");

  const fixtures = sports ? sports.fixtures : [];
  const leagues = useMemo(() => {
    const seen = [];
    for (const f of fixtures) {
      const c = f.competition || "Outros";
      if (!seen.includes(c)) seen.push(c);
    }
    return ["Todos", ...seen];
  }, [fixtures]);

  const shown = fixtures.filter((f) => {
    if (liveOnly && !isLive(f)) return false;
    if (league !== "Todos" && (f.competition || "Outros") !== league) return false;
    return true;
  });

  return (
    <>
      <div className="sporthead">
        <div>
          <h1>{liveOnly ? "Apostas ao Vivo" : "Apostas Esportivas"}</h1>
          <p className="sub">
            {liveOnly
              ? "Partidas em andamento com cotações em tempo real."
              : "Próximos jogos, principais campeonatos e melhores mercados."}
          </p>
        </div>
        <div className="sportfeed">
          {sports ? (
            <>
              <span className="badge b-ok">feed ao vivo</span>
              <span style={{ color: "var(--mut)", fontSize: 11.5 }}>
                {sports.source}
              </span>
            </>
          ) : (
            <span style={{ color: "var(--mut)", fontSize: 12 }}>carregando partidas…</span>
          )}
        </div>
      </div>

      <div className="chips" style={{ marginTop: 12 }}>
        {leagues.map((c) => (
          <button
            key={c}
            className={"qlink" + (league === c ? " on" : "")}
            onClick={() => setLeague(c)}
          >
            {c}
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <section className="panel">
          <p className="sub">
            {liveOnly
              ? "Nenhuma partida ao vivo no momento."
              : "Nenhuma partida encontrada nesta competição."}
          </p>
        </section>
      ) : (
        <div className="events">
          {shown.map((f) => (
            <div className="event" key={f.key}>
              <div className="event-top">
                <span className="event-league">{f.competition}</span>
                <span className="event-time">
                  {isLive(f) ? (
                    <span className="live-dot">● AO VIVO</span>
                  ) : (
                    when(f.kickoff)
                  )}
                </span>
              </div>
              <div className="event-teams">
                <b>{f.home}</b>
                <span className="vs">×</span>
                <b>{f.away}</b>
              </div>
              {(() => {
                const priced = f.markets.filter(
                  (m) => m.prices && m.prices.length === m.selections.length && m.prices.length > 0
                );
                return priced.length === 0 ? (
                  <div className="event-nomarket">mercados em atualização</div>
                ) : (
                   priced.map((m) => (
                  <div className="event-market" key={m.key}>
                    <span className="mk-kind">{m.kind}</span>
                    <div className="mk-odds">
                      {m.selections.map((sel, i) => {
                        const isSelected =
                          selectedBets &&
                          selectedBets.some(
                            (x) => x.fixtureKey === f.key && x.selection === sel
                          );
                        return (
                          <button
                            key={sel}
                            className={"odd-btn" + (isSelected ? " selected" : "")}
                            style={isSelected ? { borderColor: "var(--acc)", background: "var(--acc-soft)" } : {}}
                            title={`Apostar em ${sel} @ ${m.prices[i].toFixed(2)}`}
                            onClick={() =>
                              onSelectBet &&
                              onSelectBet({
                                fixtureKey: f.key,
                                home: f.home,
                                away: f.away,
                                competition: f.competition,
                                marketKind: m.kind,
                                selection: sel,
                                price: m.prices[i],
                              })
                            }
                          >
                            <span className="odd-label">{sel}</span>
                            <span className="odd-price">{m.prices[i].toFixed(2)}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  ))
                );
              })()}
            </div>
          ))}
        </div>
      )}

      {sports ? (
        <p style={{ fontSize: 11.5, color: "var(--mut)", marginTop: 10 }}>
          {sports.note}
        </p>
      ) : null}
    </>
  );
}
