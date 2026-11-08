"use client";

import { validMarkets } from '../../lib/sports.mjs';

/** Read-only recommendations; cards navigate to the sports board. */
export default function CasinoSports({ sports, loading, slow, error, updatedAt, retry, onSport }) {
  const priced = (sports?.fixtures || [])
    .map(fixture => ({ ...fixture, markets: validMarkets(fixture) }))
    .filter(fixture => fixture.markets.length > 0).slice(0, 3);
  return <div>
    {error ? <div className="sx-feed-error" role="status">
      <div><strong>{sports ? 'Atualização indisponível' : 'Não foi possível carregar as cotações.'}</strong>
        <p>{error}{sports ? ' As últimas cotações recebidas continuam visíveis para consulta.' : ''}</p></div>
      <button className="ghost" disabled={loading} onClick={retry}>{loading ? 'Atualizando…' : 'Tentar novamente'}</button>
    </div> : null}
    {!sports && !error ? <div role="status"><p className="sub">{slow ? 'A conexão está demorando.' : 'Carregando partidas…'}</p>
      {slow ? <button className="ghost" onClick={retry}>Tentar novamente</button> : null}</div> : null}
    {sports && loading ? <p className="sub" role="status">Atualizando cotações…</p> : null}
    {sports && updatedAt ? <p className="sub">Última atualização: <time dateTime={new Date(updatedAt).toISOString()}>{new Date(updatedAt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time></p> : null}
    {sports ? priced.length === 0 ? <p className="sub">Nenhuma partida com preço disponível no último calendário recebido.</p> : <div className="rowscroll" aria-busy={!!loading}>
      {priced.map(fixture => <button className="boost boost-link" key={fixture.key} onClick={() => onSport?.(false)} aria-label={`Ver ${fixture.home} × ${fixture.away} no quadro esportivo`}>
        <div className="boost-kind">{fixture.competition}</div>
        <div className="boost-name">{fixture.home} × {fixture.away}</div>
        <div className="boost-kind">{fixture.markets[0].kind}{fixture.markets[0].line != null ? ' · ' + fixture.markets[0].line : ''} · {fixture.markets[0].pricing === 'market' ? 'Provedor' : 'Modelo'}</div>
        {fixture.markets[0].selections.map((selection, index) => <div className="boost-odd" key={selection}>{selection} {fixture.markets[0].prices[index].toFixed(2)}</div>)}
      </button>)}
    </div> : null}
  </div>;
}
