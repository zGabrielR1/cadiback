"use client";

import { useRef, useState } from 'react';
import { betIdentity } from '../../lib/sports.mjs';
import { BRL } from '../../lib/api';
import { amountMinor } from '../../lib/money.mjs';

const MARKET_NAMES = { '1x2': 'Resultado da partida', moneyline: 'Vencedor', dc: 'Dupla chance', dnb: 'Empate anula', ah: 'Handicap', btts: 'Ambas marcam', total: 'Total', 'total-h1': 'Total no 1º tempo', 'total-h2': 'Total no 2º tempo', cards: 'Cartões amarelos', corners: 'Escanteios', fouls: 'Faltas', 'scorer-h': 'Marcador · Casa', 'scorer-a': 'Marcador · Visitante' };

export default function BetslipTray({ bets, profile, betAmount, onBetAmount, busy, onRemove, onClear, onPlace, state={status:'idle'}, availability={changed:[],unavailable:[]}, onAcceptQuote, onHistory }) {
  const [expanded, setExpanded] = useState(false);
  const toggle = useRef(null);
  if (!bets.length && state.status !== 'accepted') return null;
  if (state.status === 'accepted') return <section className="betslip-tray betslip-receipt is-expanded" aria-label="Comprovante de aposta"><div className="betslip-head"><strong>Aposta recebida</strong><button className="betslip-clear" aria-label="Fechar comprovante" onClick={onClear}>×</button></div><div className="betslip-body"><p role="status">Confirmada pelo servidor.</p><dl><div><dt>Referência</dt><dd>{state.receipt.round_id}</dd></div><div><dt>Valor aceito</dt><dd>{BRL(state.receipt.stake_minor)}</dd></div><div><dt>Cotação aceita</dt><dd>{Number(state.receipt.price).toFixed(2)}</dd></div></dl><p className="betslip-estimate">O resultado e a liquidação podem ser acompanhados no histórico.</p><button className="betslip-submit" onClick={onHistory}>Ver histórico</button><button className="ghost" onClick={onClear}>Continuar nas partidas</button></div></section>;
  const totalOdds = bets.reduce((acc, bet) => acc * bet.price, 1);
  const amount = amountMinor(betAmount);
  const validStake = amount !== null;
  const stakeMinor = amount || 0;
  const insufficient = profile && stakeMinor > profile.available_minor + (profile.bonus_minor || 0);
  const error = !validStake ? 'Informe um valor de aposta válido.' : insufficient ? 'Saldo insuficiente para este valor.' : '';
  const payout = BRL(Math.round(stakeMinor * totalOdds));
  return (
    <section className={'betslip-tray' + (expanded ? ' is-expanded' : '')} aria-label="Boletim de apostas" onKeyDown={event => {
      if (event.key === 'Escape' && expanded) { event.preventDefault(); setExpanded(false); toggle.current?.focus(); }
    }}>
      <div className="betslip-head">
        <div className="betslip-desktop-title"><span>Boletim de apostas</span><b>{bets.length}</b></div>
        <button ref={toggle} className="betslip-toggle" aria-expanded={expanded} aria-controls="betslip-content" onClick={() => setExpanded(value => !value)}><span>Boletim <b>{bets.length}</b><small>{bets.length===1?bets[0].selection:`${bets.length} partidas`} · {BRL(stakeMinor)}</small></span><span>{expanded ? 'Recolher' : 'Abrir'} <span aria-hidden="true">{expanded ? '⌄' : '⌃'}</span></span></button>
        <button className="betslip-clear" disabled={busy} onClick={onClear} aria-label="Limpar boletim">×</button>
      </div>
      <div id="betslip-content" className="betslip-body">
        {profile ? <div className="betslip-balance"><span>Saldo disponível</span><b>{BRL(profile.available_minor)}</b></div> : <p className="betslip-login-note">Entre na sua conta para confirmar a aposta.</p>}
        <div className="betslip-selections">{bets.map(bet => <div className="betslip-match" key={betIdentity(bet)}><div><span className="betslip-event">{bet.home} × {bet.away}</span><span className="betslip-competition">{bet.competition}</span><span className="betslip-market">{MARKET_NAMES[bet.marketKind] || 'Mercado selecionado'}{bet.line != null ? ` · ${bet.line}` : ''}</span><strong>{bet.selection}</strong>{availability.unavailable.includes(betIdentity(bet))?<span className="betslip-error">Mercado indisponível</span>:availability.changed.some(item=>item.id===betIdentity(bet))?<span className="betslip-changed">Cotação mudou. Confira antes de enviar.</span>:null}</div><span className="betslip-price">{bet.price.toFixed(2)}</span><button disabled={busy} aria-label={'Remover seleção ' + bet.selection} className="betslip-remove" onClick={() => onRemove(bet)}>×</button></div>)}</div>
        {bets.length > 1 ? <div className="betslip-pick"><span>Múltipla · {bets.length} seleções</span><b>{totalOdds.toFixed(2)}</b></div> : null}
        <label htmlFor="betslip-stake">Valor da aposta</label>
        <div className="betslip-stake-row"><span>R$</span><input id="betslip-stake" disabled={busy} inputMode="decimal" value={betAmount} onChange={event => onBetAmount(event.target.value)} aria-invalid={!!error} aria-describedby={error ? 'betslip-error' : undefined} /></div>
        <div className="betslip-quick-chips">{['5', '10', '25', '50', '100'].map(value => <button disabled={busy} key={value} onClick={() => onBetAmount(value)}>R$ {value}</button>)}</div>
        {error ? <p id="betslip-error" className="betslip-error" role="status">{error}</p> : null}
        <div className="betslip-payout"><span>Retorno potencial</span><b>{payout}</b></div>
        <p className="betslip-estimate">Estimativa com as cotações selecionadas. A confirmação depende da aceitação pelo servidor.</p>
        {state.message ? <p className={state.status==='error'?'betslip-error':'betslip-notice'} role="status">{state.message}</p> : null}
        {state.status==='review' ? <div className="betslip-quote-review"><ul>{state.quote.legs.map((leg,index)=><li key={index}><span>{leg.selection}</span><span><s>{bets[index]?.price.toFixed(2)}</s> → {leg.price.toFixed(2)}</span></li>)}</ul><button className="betslip-submit" onClick={onAcceptQuote}>Aceitar novas cotações</button></div> : <button className="betslip-submit" disabled={busy || !!error || availability.unavailable.length>0} onClick={onPlace}>{busy ? state.message || 'Enviando aposta…' : state.status==='error' ? 'Conferir e tentar novamente' : 'Confirmar aposta demo'}</button>}
      </div>
    </section>
  );
}
