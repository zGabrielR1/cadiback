"use client";

import { useState } from 'react';
import { betIdentity, filterFixtures } from '../../lib/sports.mjs';
import { BUILDER_GROUPS, BUILDER_STATS, builderMarkets, builderBet, statPair, refreshDraft, toggleDraft } from '../../lib/bet-builder.mjs';

const NAMES = { '1x2': 'Resultado da partida', moneyline: 'Vencedor', dc: 'Dupla chance', dnb: 'Empate anula', ah: 'Handicap', btts: 'Ambas marcam', total: 'Total de gols', 'total-h1': 'Gols no 1º tempo', 'total-h2': 'Gols no 2º tempo', fouls: 'Total de faltas', cards: 'Total de cartões amarelos', 'red-cards': 'Cartões vermelhos', corners: 'Total de escanteios', 'scorer-h': 'Marcar a qualquer momento · Casa', 'scorer-a': 'Marcar a qualquer momento · Visitante' };
const ended = fixture => /FINAL|AET|\bFT\b/i.test(fixture?.status || '');
const live = fixture => /IN_PROGRESS|LIVE/i.test(fixture?.status || '');
const quote = value => value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function Comparison({ fixture }) {
  return (
    <section className="builder-panel builder-comparison" aria-labelledby="comparison-title">
      <div className="builder-panel-head"><h2 id="comparison-title">Números da partida</h2><span>{live(fixture) ? 'Ao vivo' : ended(fixture) ? 'Encerrada' : 'Pré-jogo'}</span></div>
      <p className="builder-caption">Contagens deste jogo. Médias históricas ainda não disponíveis.</p>
      <table>
        <thead><tr><th scope="col">Estatística</th><th scope="col">{fixture.home}</th><th scope="col">{fixture.away}</th></tr></thead>
        <tbody>{BUILDER_STATS.map(stat => {
          const pair = statPair(fixture, stat.key);
          return <tr key={stat.key}><th scope="row">{stat.label}</th>{pair.map((value, index) => <td key={index} className={value == null ? 'is-missing' : ''}>{value == null ? <span aria-label="Dado não disponível">—</span> : value.toLocaleString('pt-BR') + (stat.unit || '')}</td>)}</tr>;
        })}</tbody>
      </table>
      <p className="builder-caption">“—” indica dado não enviado pela fonte. Zero indica uma contagem confirmada.</p>
    </section>
  );
}

export default function BetBuilder({ fixtures, initialKey, query = '', source, updatedAt, loading, error, onRetry, onUseSingleBet, onBack }) {
  const [fixtureKey, setFixtureKey] = useState(initialKey || '');
  const [group, setGroup] = useState('result');
  const [draft, setDraft] = useState([]);
  const [notice, setNotice] = useState('');
  const [mobilePane, setMobilePane] = useState('markets');
  const available = fixtures.filter(f => (f.sport || 'soccer') === 'soccer');
  const scoped = filterFixtures(available, { query });
  const fixture = scoped.find(f => f.key === fixtureKey) || scoped.find(f => !ended(f) && BUILDER_STATS.some(stat => statPair(f, stat.key).some(value => value != null))) || scoped.find(f => !ended(f)) || scoped[0];
  const markets = builderMarkets(fixture, group);
  const currentDraft = refreshDraft(draft, fixture);
  const staleCount = draft.filter(bet => bet.fixtureKey === fixture?.key).length - currentDraft.length;
  const suspended = !fixture || ended(fixture) || !!error || !!loading;
  const chosen = bet => currentDraft.some(item => betIdentity(item) === betIdentity(bet));
  const select = bet => { setDraft(previous => toggleDraft(refreshDraft(previous, fixture), bet)); setNotice(''); };

  return (
    <div className="bet-builder" data-ui>
      <div className="builder-title-row"><div><h1>Criar Aposta</h1><p>Leia a partida. Explore os mercados. Prepare suas seleções.</p></div><button className="ghost" onClick={onBack}>Voltar às partidas</button></div>
      <label className="builder-fixture-label" htmlFor="builder-fixture">Partida de futebol</label>
      <select id="builder-fixture" value={fixture?.key || ''} onChange={event => { setFixtureKey(event.target.value); setDraft([]); setNotice(''); }}>
        {!scoped.length ? <option value="">{loading ? 'Carregando partidas…' : 'Nenhuma partida encontrada'}</option> : scoped.map(f => <option key={f.key} value={f.key}>{f.home} × {f.away} · {f.competition}{live(f) ? ' · Ao vivo' : ended(f) ? ' · Encerrada' : ''}</option>)}
      </select>
      {error ? <div className="builder-feed-note" role="status"><span>{error} As seleções ficam pausadas até a atualização.</span><button className="ghost" disabled={loading} onClick={onRetry}>Tentar novamente</button></div> : null}
      {!fixture ? <section className="builder-panel"><h2>{loading ? 'Buscando partidas' : 'Nenhuma partida neste filtro'}</h2><p>{loading ? 'As estatísticas e os mercados aparecem assim que a fonte responder.' : 'Tente outro time na busca ou volte à lista de partidas.'}</p></section> : (
        <>
          <div className="builder-match"><div><span>{fixture.competition}</span><h2>{fixture.home} <span>×</span> {fixture.away}</h2></div><div className="builder-score"><strong>{live(fixture) || ended(fixture) ? `${fixture.home_score ?? '—'} : ${fixture.away_score ?? '—'}` : 'Pré-jogo'}</strong><span>{live(fixture) ? fixture.progress || 'Ao vivo' : ended(fixture) ? 'Encerrada' : fixture.kickoff ? new Date(fixture.kickoff).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : 'Horário a confirmar'}</span></div></div>
          {/* At 1440px: content = comparison 300 + 2×16 gutters + flexible markets + draft 280. */}
          <div className="builder-mobile-tabs" aria-label="Área da partida">
            <button aria-pressed={mobilePane === 'markets'} onClick={() => setMobilePane('markets')}>Mercados</button>
            <button aria-pressed={mobilePane === 'stats'} onClick={() => setMobilePane('stats')}>Estatísticas</button>
            <button aria-pressed={mobilePane === 'draft'} onClick={() => setMobilePane('draft')}>Rascunho ({currentDraft.length})</button>
          </div>
          <div className="builder-grid" data-pane={mobilePane}>
            <Comparison fixture={fixture} />
            <section className="builder-panel builder-market-panel" aria-labelledby="builder-market-title">
              <div className="builder-panel-head"><h2 id="builder-market-title">Mercados</h2><span>{markets.length} {markets.length === 1 ? 'disponível' : 'disponíveis'}</span></div>
              <div className="builder-tabs" role="tablist" aria-label="Tipos de mercado">{BUILDER_GROUPS.map(item => <button key={item.id} id={'builder-tab-' + item.id} role="tab" aria-selected={group === item.id} aria-controls="builder-market-content" tabIndex={group === item.id ? 0 : -1} onKeyDown={event => {
                if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
                event.preventDefault(); const index = BUILDER_GROUPS.findIndex(g => g.id === group);
                const next = event.key === 'Home' ? 0 : event.key === 'End' ? BUILDER_GROUPS.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + BUILDER_GROUPS.length) % BUILDER_GROUPS.length;
                setGroup(BUILDER_GROUPS[next].id); document.getElementById('builder-tab-' + BUILDER_GROUPS[next].id)?.focus();
              }} onClick={() => setGroup(item.id)}>{item.label}</button>)}</div>
              <div id="builder-market-content" role="tabpanel" aria-labelledby={'builder-tab-' + group}>
                {group === 'players' ? <p className="builder-context">Marcadores enviados pela fonte. Finalizações, faltas e cartões por jogador ainda não estão disponíveis.</p> : group === 'discipline' ? <p className="builder-context">As cotações abaixo são para o total da partida. Veja a contagem de cada equipe na comparação.</p> : null}
                {markets.length ? markets.map(market => <div className="builder-market" key={market.key || market.kind + String(market.line)}>
                  <div className="builder-market-name"><h3>{NAMES[market.kind] || market.kind}{market.line != null ? ` · ${market.line}` : ''}</h3><span>{market.pricing === 'market' ? 'Cotação do provedor' : 'Cotação do modelo'}</span></div>
                  <div className="builder-prices">{market.selections.map(selection => {
                    const bet = builderBet(fixture, market, selection);
                    return <button key={selection} aria-pressed={chosen(bet)} disabled={suspended} onClick={() => select(bet)}><span>{selection}</span><strong>{quote(bet.price)}</strong></button>;
                  })}</div>
                </div>) : <div className="builder-empty"><h3>{group === 'players' ? 'Marcadores ainda indisponíveis' : 'Mercados ainda indisponíveis'}</h3><p>{group === 'players' ? 'Precisamos de escalações e cotações de jogadores para esta partida. Nenhum nome ou preço foi estimado.' : 'A fonte ainda não enviou cotações válidas para este grupo. Você pode consultar os dados da partida e explorar os outros mercados.'}</p></div>}
                {suspended && markets.length ? <p className="builder-caption" role="status">{ended(fixture) ? 'Partida encerrada. Mercados apenas para consulta.' : 'Atualizando cotações. Aguarde para selecionar.'}</p> : null}
              </div>
              <details className="builder-coverage"><summary>Quais dados ainda faltam?</summary><ul><li>Médias de faltas e cartões dos últimos jogos de cada equipe.</li><li>Cartões, faltas e finalizações por jogador.</li><li>Escalações completas e histórico de marcadores.</li><li>Cotação conjunta para combinar seleções da mesma partida.</li></ul><p>Esses dados não são inferidos a partir do placar. A disponibilidade varia por partida.</p></details>
            </section>
            <aside className="builder-panel builder-draft" aria-labelledby="builder-draft-title">
              <div className="builder-panel-head"><h2 id="builder-draft-title">Seu rascunho</h2><span>{currentDraft.length} {currentDraft.length === 1 ? 'seleção' : 'seleções'}</span></div>
              {currentDraft.length ? <ul>{currentDraft.map(bet => <li key={betIdentity(bet)}><div><span>{NAMES[bet.marketKind] || bet.marketKind}{bet.line != null ? ` · ${bet.line}` : ''}</span><strong>{bet.selection}</strong></div><b>{quote(bet.price)}</b><button className="draft-remove" aria-label={'Remover ' + bet.selection} onClick={() => select(bet)}>×</button><button className="draft-single" disabled={suspended} onClick={() => { onUseSingleBet(bet); setNotice('Seleção enviada como aposta simples. O boletim anterior foi substituído.'); }}>Usar como aposta simples</button></li>)}</ul> : <p className="builder-empty-draft">Selecione uma cotação para começar. Seu rascunho fica aqui enquanto você compara os mercados.</p>}
              {staleCount > 0 ? <p className="builder-caption" role="status">{staleCount} seleção(ões) saiu(ram) do mercado e não pode(m) ser usada(s).</p> : null}
              <div className="builder-combination"><span>Cotação combinada</span><strong>—</strong></div>
              <p className="builder-caption">A combinação da mesma partida ainda não está disponível. As cotações individuais não podem ser multiplicadas para criar esse preço.</p>
              <button className="builder-combine" disabled>Criar combinação · em breve</button>
              {notice ? <p className="builder-notice" role="status">{notice}</p> : null}
            </aside>
          </div>
          <p className="builder-source">Fonte: {source || 'aguardando confirmação'}{updatedAt ? ' · Atualizado às ' + new Date(updatedAt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : ''}. Estatísticas do jogo e cotações têm coberturas diferentes.</p>
        </>
      )}
    </div>
  );
}
