"use client";

import { useEffect, useRef, useState } from "react";
import { validMarkets, betIdentity, matchState } from "../../lib/sports.mjs";
import { sportProfile, statPair, builderBet } from "../../lib/bet-builder.mjs";
import OddsButton from "./OddsButton";
import { matchLink, matchFiltersFromUrl } from "../../lib/match-link.mjs";
import { filterMatchMarkets, marketCategories, marketLabel } from "../../lib/market-discovery.mjs";
import { canCalendarMatch, matchCalendar } from "../../lib/match-calendar.mjs";

const timestamp = value => {
  const date = new Date(value);
  return value && Number.isFinite(date.getTime()) ? date.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "Ainda não informado";
};

export default function MarketDetail({ fixture, source, updatedAt, loading, error, onRetry, authenticated, onSelectBet, selectedBets, onLogin, onBack, onResearch, favorite, onFavorite, pending = false }) {
  const heading = useRef(null);
  const marketSearch = useRef(null);
  const [marketQuery, setMarketQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [selectedOnly, setSelectedOnly] = useState(false);
  const clearMarketFilters = () => { setMarketQuery(""); setCategory("all"); setSelectedOnly(false); requestAnimationFrame(() => marketSearch.current?.focus({ preventScroll: true })); };
  const [shareState, setShareState] = useState("");
  const [shareUrl, setShareUrl] = useState("");
  const [calendarState, setCalendarState] = useState("");
  const downloadCalendar = () => {
    let url;
    const anchor = document.createElement("a");
    try {
      const calendar = matchCalendar(fixture, window.location.href);
      url = URL.createObjectURL(new Blob([calendar.content], { type: "text/calendar;charset=utf-8" }));
      anchor.href = url;
      anchor.download = calendar.filename;
      document.body.appendChild(anchor);
      anchor.click();
      setCalendarState("Abra o arquivo .ics no seu calendário. Alterações de horário não são sincronizadas.");
    } catch {
      setCalendarState("Não foi possível preparar o calendário. Atualize os dados e tente novamente.");
    } finally {
      anchor.remove();
      if (url) setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  };
  useEffect(() => {
    const filters = matchFiltersFromUrl(window.location.href);
    setCategory(filters.category);
    setMarketQuery(filters.query);
  }, []);
  const copyLink = async () => {
    const url = matchLink(window.location.href, fixture.key, { category, query: marketQuery });
    setShareUrl(url);
    try {
      await navigator.clipboard.writeText(url);
      setShareState("Link copiado.");
    } catch {
      setShareState("Selecione e copie o link abaixo.");
    }
  };
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);
  const profile = sportProfile(fixture?.sport);
  const markets = validMarkets(fixture || {});
  const shownMarkets = filterMatchMarkets(markets, { sport: fixture?.sport, category, query: marketQuery,
    selectedOnly: authenticated && selectedOnly, fixtureKey: fixture?.key, selectedBets });
  const categories = marketCategories(markets).filter(item => item.count > 0 || item.id === category || item.id === "all");
  const selectedMarketCount = authenticated ? filterMatchMarkets(markets, { selectedOnly: true, fixtureKey: fixture?.key, selectedBets }).length : 0;
  const filtered = category !== "all" || !!marketQuery.trim() || (authenticated && selectedOnly);
  const { unavailable, ended, live, label: statusLabel } = matchState(fixture);
  const stats = profile.stats.map(stat => ({ ...stat, pair: statPair(fixture, stat.key) }));
  const supplied = stats.filter(stat => stat.pair.some(value => value !== null));
  const paused = ended || unavailable || loading || !!error;

  return <article className="market-detail" aria-labelledby="market-detail-title">
    <div className="market-detail-nav"><button className="ghost" onClick={onBack}>← Voltar aos mercados</button>{fixture ? <><button className="ghost" onClick={copyLink}>Copiar link da partida</button><button className="ghost" aria-pressed={favorite} onClick={() => onFavorite(fixture.key)}>{favorite ? "Remover dos favoritos" : "Salvar partida"}</button></> : null}</div>
    {shareState ? <div className="market-detail-notice" role="status"><p>{shareState}</p>{shareState !== "Link copiado." ? <input aria-label="Link da partida" readOnly value={shareUrl} onFocus={event => event.target.select()} /> : null}</div> : null}
    <header className="market-detail-header">
      <p>{fixture ? [fixture.competition, fixture.country].filter(Boolean).join(" · ") : pending ? "Carregando partida" : "Mercado indisponível"}</p>
      <h1 id="market-detail-title" ref={heading} tabIndex={-1}>{fixture ? `${fixture.home} × ${fixture.away}` : pending ? "Buscando a partida…" : error ? "Não foi possível carregar a partida" : "Esta partida saiu do feed"}</h1>
      {fixture ? <div className="market-detail-score"><strong>{live || ended ? `${fixture.home_score ?? "—"} : ${fixture.away_score ?? "—"}` : unavailable ? statusLabel : "Pré-jogo"}</strong><span>{live ? fixture.progress || "Ao vivo" : ended ? "Encerrada" : unavailable ? `${statusLabel} · seleções pausadas` : timestamp(fixture.kickoff)}</span></div> : <p>{pending ? "Aguarde enquanto consultamos os dados e as cotações." : error ? "Tente atualizar os dados ou volte aos mercados." : "Volte aos mercados para consultar as partidas disponíveis agora."}</p>}
    </header>
    {canCalendarMatch(fixture) ? <div className="market-detail-calendar"><p className="market-detail-caption"><time dateTime={fixture.kickoff}>Início: {new Date(fixture.kickoff).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short" })}</time></p><button className="ghost" onClick={downloadCalendar} disabled={loading || !!error}>Adicionar ao calendário</button></div> : null}
    {calendarState ? <p className="market-detail-caption" role="status">{calendarState}</p> : null}
    <dl className="market-detail-provenance"><div><dt>Fonte do calendário</dt><dd>{source || "Não informada"}</dd></div><div><dt>Última atualização recebida</dt><dd>{timestamp(updatedAt)}</dd></div><div><dt>Mercados disponíveis</dt><dd>{markets.length}</dd></div></dl>
    {error ? <div className="market-detail-notice" role="status"><p>{error} {fixture ? "Exibindo os últimos dados recebidos. As seleções estão pausadas." : "Ainda não há dados para esta partida."}</p><button className="ghost" onClick={onRetry} disabled={loading}>Tentar novamente</button></div> : loading ? <p role="status">Atualizando dados e cotações…</p> : null}
    {fixture ? <><nav className="market-detail-sections" aria-label="Seções da partida"><a href="#detail-markets-title">Cotações</a><a href="#detail-stats-title">Estatísticas</a></nav><div className="market-detail-grid">
      <section className="market-detail-markets" aria-labelledby="detail-markets-title"><h2 id="detail-markets-title">Cotações atuais</h2><p className="market-detail-caption">Valores decimais. Cada mercado identifica se a cotação vem do provedor ou do modelo.</p>
        {markets.length || filtered ? <div className="market-finder">
          <label className="market-finder-search">Buscar mercados<input ref={marketSearch} type="search" aria-label="Buscar mercados nesta partida" placeholder="Mercado, seleção ou linha…" maxLength={200} value={marketQuery} onChange={event => setMarketQuery(event.target.value)} /></label>
          <div className="market-finder-categories" role="group" aria-label="Categorias de mercado">{categories.map(item => <button key={item.id} className="ghost" aria-pressed={category === item.id} onClick={() => setCategory(item.id)}>{item.label} <span>{item.count}</span></button>)}</div>
          <div className="market-finder-summary"><p role="status">{shownMarkets.length} de {markets.length} mercados</p>{authenticated ? <button className="ghost" aria-pressed={selectedOnly} onClick={() => setSelectedOnly(value => !value)}>Minhas seleções ({selectedMarketCount})</button> : null}{filtered ? <button className="ghost" onClick={clearMarketFilters}>Limpar filtros de mercado</button> : null}</div>
        </div> : null}
        {shownMarkets.length ? shownMarkets.map((market, index) => <section className="market-detail-market" key={market.key || `${market.kind}:${market.line ?? ""}:${index}`}>
          <div className="market-detail-market-name"><h3>{marketLabel(market.kind, fixture.sport)}{market.line != null ? ` · ${market.line}` : ""}</h3><span>{market.pricing === "market" ? "Provedor" : "Modelo"}</span></div>
          <div className="market-detail-prices" style={market.selections.length <= 3 ? { gridTemplateColumns: `repeat(${market.selections.length}, minmax(0, 1fr))` } : undefined}>{market.selections.map((selection, i) => {
            const bet = builderBet(fixture, market, selection);
            const selected = selectedBets?.some(item => betIdentity(item) === betIdentity(bet));
            return authenticated ? <OddsButton key={selection} price={market.prices[i]} aria-pressed={!!selected} disabled={paused} className={selected ? "on" : ""} onClick={() => onSelectBet(bet)}><span>{selection}</span><b>{market.prices[i].toFixed(2)}</b></OddsButton> : <div className="market-detail-price" key={selection}><span>{selection}</span><b>{market.prices[i].toFixed(2)}</b></div>;
          })}</div>
        </section>) : markets.length || filtered ? <div className="market-finder-empty"><h3>Nenhum mercado neste filtro</h3><p>{selectedOnly && authenticated && !selectedMarketCount ? "Você ainda não tem seleções disponíveis nesta partida. Consulte todos os mercados para escolher uma cotação." : authenticated ? "Experimente outra categoria, seleção ou linha. Suas seleções no boletim são mantidas." : "Experimente outra categoria, seleção ou linha. Os dados da partida continuam disponíveis."}</p><button className="ghost" onClick={clearMarketFilters}>Ver todos os mercados</button></div> : <p className="market-detail-empty">A fonte não enviou cotações válidas para esta partida.</p>}
        {ended || unavailable ? <p className="market-detail-caption">{ended ? "Partida encerrada." : `Partida ${statusLabel.toLowerCase()}.`} As cotações exibidas são as últimas recebidas e não aceitam seleções.</p> : null}
      </section>
      <aside className="market-detail-stats"><section aria-labelledby="detail-stats-title"><h2 id="detail-stats-title">Estatísticas da partida</h2><p className="market-detail-caption">Dados deste jogo, sem estimativas históricas.</p>
        {supplied.length ? <><div className="market-detail-stat-teams"><span>{fixture.home}</span><span>{fixture.away}</span></div><dl>{supplied.map(stat => <div className="market-detail-stat" key={stat.key}><dt>{stat.label}</dt><dd><span>{stat.pair[0] === null ? "—" : `${stat.pair[0]}${stat.unit || ""}`}</span><span>{stat.pair[1] === null ? "—" : `${stat.pair[1]}${stat.unit || ""}`}</span></dd></div>)}</dl><p className="market-detail-caption">— indica um dado não informado pela fonte.</p></> : <p className="market-detail-empty">A fonte ainda não disponibilizou estatísticas para esta partida.</p>}
      </section>{authenticated ? <section className="market-detail-account"><h2>Explore a partida</h2><button className="ghost" onClick={onResearch}>Análise avançada</button></section> : null}</aside>
    </div></> : null}
  </article>;
}
