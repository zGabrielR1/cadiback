"use client";

import { useEffect, useRef, useState } from 'react';
import { betIdentity } from '../../lib/sports.mjs';
import { BRL } from '../../lib/api';
import { amountMinor } from '../../lib/money.mjs';
import { applyPriceChanges } from '../../lib/sports-slip.mjs';
import { usePanelResize } from '../../lib/usePanelResize';
import UIIcon from './UIIcon';

const MARKET_NAMES = { '1x2': 'Resultado da partida', moneyline: 'Vencedor', dc: 'Dupla chance', dnb: 'Empate anula', ah: 'Handicap', btts: 'Ambas marcam', total: 'Total', 'total-h1': 'Total no 1º tempo', 'total-h2': 'Total no 2º tempo', cards: 'Cartões amarelos', corners: 'Escanteios', fouls: 'Faltas', 'scorer-h': 'Marcador · Casa', 'scorer-a': 'Marcador · Visitante' };

export default function BetslipTray({ bets, profile, betAmount, onBetAmount, busy, onRemove, onClear, onPlace, state={status:'idle'}, availability={changed:[],unavailable:[]}, onAcceptQuote, onHistory, onAcceptBoardPrices, onRemoveUnavailable, feedLoading = false, feedError = "", onRefresh }) {
  const [expanded, setExpanded] = useState(() => typeof window === 'undefined' ? true : window.matchMedia('(min-width: 1281px)').matches);
  const [confirmClear, setConfirmClear] = useState(false);
  const resize = usePanelResize("casa-betslip-size", 320, 600, -1, 260, typeof window === "undefined" || window.innerWidth < 1281 ? 640 : Math.min(640, window.innerWidth - 850));
  useEffect(() => {
    document.body.style.setProperty("--slip-space", resize.size.width + "px");
    return () => document.body.style.removeProperty("--slip-space");
  }, [resize.size.width]);
  const panelStyle = {"--slip-width": resize.size.width + "px", "--slip-height": resize.size.height + "px"};
  // Keep the drawer state in sync with the viewport: rotating or resizing a
  // device must not leave it expanded/collapsed incorrectly.
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const mq = window.matchMedia('(min-width: 1281px)');
    const handler = (e) => setExpanded(e.matches);
    if (mq.addEventListener) mq.addEventListener('change', handler);
    else mq.addListener(handler);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', handler);
      else mq.removeListener(handler);
    };
  }, []);
  useEffect(() => {
    if (!confirmClear) return undefined;
    const id = setTimeout(() => setConfirmClear(false), 4000);
    return () => clearTimeout(id);
  }, [confirmClear]);
  const toggle = useRef(null);
  const priceReviewHeading = useRef(null);
  const unavailableHeading = useRef(null);
  const focusReview = ref => { ref.current?.focus({ preventScroll: true }); ref.current?.closest('section')?.scrollIntoView({ block: 'start', inline: 'nearest' }); };
  if (!bets.length && state.status !== 'accepted') return null;
  if (state.status === 'accepted') return <section className="betslip-tray betslip-receipt is-expanded" style={panelStyle} aria-label="Comprovante de aposta"><div className="betslip-head"><strong>Aposta recebida</strong><button className="betslip-clear" aria-label="Fechar comprovante" onClick={onClear}>×</button></div><div className="betslip-body"><p role="status">Confirmada pelo servidor.</p><ul className="betslip-receipt-list">{(state.selections || []).map(bet=><li key={betIdentity(bet)}><span>{bet.home} × {bet.away}</span><strong>{bet.selection} · {bet.price.toFixed(2)}</strong><span>{MARKET_NAMES[bet.marketKind] || bet.marketKind}{bet.line!=null ? ` · ${bet.line}` : ""}</span></li>)}</ul><dl><div><dt>Referência</dt><dd>{state.receipt?.round_id ?? "—"}</dd></div><div><dt>Valor aceito</dt><dd>{BRL(state.receipt?.stake_minor ?? 0)}</dd></div><div><dt>Cotação aceita</dt><dd>{Number(state.receipt?.price ?? 0).toFixed(2)}</dd></div></dl><p className="betslip-estimate">O resultado e a liquidação podem ser acompanhados no histórico.</p><button className="betslip-submit" onClick={onHistory}>Ver histórico</button><button className="ghost" onClick={onClear}>Continuar nas partidas</button></div></section>;
  const totalOdds = Math.round(bets.reduce((acc, bet) => acc * bet.price, 1) * 100) / 100;
  const changedPrices = new Map(state.status === 'review' ? [] : availability.changed.map(change => [change.id, change.price]));
  const nextTotalOdds = Math.round(applyPriceChanges(bets, availability.changed).reduce((acc, bet) => acc * bet.price, 1) * 100) / 100;
  const reviewingBoard = availability.changed.length > 0 && state.status !== 'review';
  const amount = amountMinor(betAmount);
  const validStake = amount !== null;
  const stakeMinor = amount || 0;
  const insufficient = profile && stakeMinor > profile.available_minor + (profile.bonus_minor || 0);
  const error = !validStake ? 'Informe um valor de aposta válido.' : insufficient ? 'Saldo insuficiente para este valor.' : '';
  const payout = BRL(Math.round(stakeMinor * totalOdds));
  const funds = profile ? profile.available_minor + (profile.bonus_minor || 0) : null;
  const adjustStake = minor => onBetAmount((minor / 100).toFixed(2));
  return (
    <section style={panelStyle} className={'betslip-tray' + (expanded ? ' is-expanded' : '')} aria-label="Boletim de apostas" onKeyDown={event => {
      if (event.key === 'Escape' && expanded) { event.preventDefault(); setExpanded(false); toggle.current?.focus(); }
    }}>
      {expanded ? <button type="button" className="betslip-resize" aria-label="Redimensionar boletim" title="Arraste para ajustar largura e altura. Use as setas ou Home para restaurar." {...resize.handle}><UIIcon name="grip" size={18}/></button> : null}
      <div className="betslip-head">
        <div className="betslip-desktop-title"><span>Boletim de apostas</span><b>{bets.length}</b></div>
        <button ref={toggle} className="betslip-toggle" aria-expanded={expanded} aria-controls="betslip-content" onClick={() => setExpanded(value => !value)}><span>Boletim <b>{bets.length}</b><small>{bets.length===1?bets[0].selection:`${bets.length} partidas`} · {BRL(stakeMinor)}</small></span><span>{expanded ? 'Recolher' : 'Abrir'} <span aria-hidden="true">{expanded ? '⌄' : '⌃'}</span></span></button>
        <button className={"betslip-clear" + (confirmClear ? " confirm" : "")} disabled={busy} onClick={() => { if (confirmClear) { setConfirmClear(false); onClear(); } else setConfirmClear(true); }} aria-label={confirmClear ? "Confirmar limpeza do boletim" : "Limpar boletim"}>{confirmClear ? "Limpar?" : "×"}</button>
      </div>
      <div id="betslip-content" className="betslip-body">
        <div className="betslip-type"><strong>{bets.length===1?'Aposta simples':'Aposta múltipla'}</strong><small>{bets.length} {bets.length===1?'partida':'partidas'} · cotação decimal</small></div>
        {profile ? <div className="betslip-balance"><span>Saldo disponível</span><b>{BRL(profile.available_minor)}</b></div> : <p className="betslip-login-note">Entre na sua conta para confirmar a aposta.</p>}
        <div className="betslip-selections">{bets.map(bet => <div className="betslip-match" key={betIdentity(bet)}><div><span className="betslip-event">{bet.home} × {bet.away}</span><span className="betslip-competition">{bet.competition}</span><span className="betslip-market">{MARKET_NAMES[bet.marketKind] || 'Mercado selecionado'}{bet.line != null ? ` · ${bet.line}` : ''}</span><strong>{bet.selection}</strong>{availability.unavailable.includes(betIdentity(bet))?<span className="betslip-error">Mercado indisponível</span>:availability.changed.some(item=>item.id===betIdentity(bet))?<span className="betslip-changed">Cotação mudou. Confira antes de enviar.</span>:null}</div><span className={"betslip-price" + (changedPrices.has(betIdentity(bet)) ? " is-changing" : "")}>{changedPrices.has(betIdentity(bet)) ? <><s aria-label="Cotação selecionada">{bet.price.toFixed(2)}</s><strong aria-label="Nova cotação">{changedPrices.get(betIdentity(bet)).toFixed(2)}</strong></> : bet.price.toFixed(2)}</span><button disabled={busy} aria-label={'Remover seleção ' + bet.selection} className="betslip-remove" onClick={() => onRemove(bet)}>×</button></div>)}</div>
        {availability.unavailable.length > 0 ? <section className="betslip-market-recovery" aria-labelledby="betslip-unavailable-title">
          <h3 id="betslip-unavailable-title" ref={unavailableHeading} tabIndex={-1}>Mercados indisponíveis</h3>
          <p role="status">{availability.unavailable.length === 1 ? "Uma seleção está indisponível." : `${availability.unavailable.length} seleções estão indisponíveis.`} As outras seleções continuam no boletim.</p>
          <button className="ghost" disabled={busy} onClick={onRemoveUnavailable}>Remover seleções indisponíveis</button>
        </section> : null}
        {reviewingBoard ? <section className="betslip-price-review" aria-labelledby="betslip-price-review-title">
          <h3 id="betslip-price-review-title" ref={priceReviewHeading} tabIndex={-1}>Cotações atualizadas</h3>
          <p role="status">{availability.changed.length === 1 ? "Uma cotação mudou." : `${availability.changed.length} cotações mudaram.`} Aceitar atualiza o boletim; a aposta só é enviada ao confirmar.</p>
          {!availability.unavailable.length ? <dl>
            <div><dt>{bets.length > 1 ? "Cotação combinada" : "Cotação da seleção"}</dt><dd><s>{totalOdds.toFixed(2)}</s> → <strong>{nextTotalOdds.toFixed(2)}</strong></dd></div>
            {validStake ? <div><dt>Retorno potencial</dt><dd><s>{payout}</s> → <strong>{BRL(Math.round(stakeMinor * nextTotalOdds))}</strong></dd></div> : null}
          </dl> : <p>Remova as seleções indisponíveis para comparar o retorno.</p>}
          {feedError ? <><p>Atualize as partidas para conferir as novas cotações.</p><button className="ghost" disabled={busy || feedLoading} onClick={onRefresh}>{feedLoading ? "Atualizando partidas…" : "Atualizar partidas"}</button></> : null}
          <button className="ghost" disabled={busy || feedLoading || !!feedError} onClick={onAcceptBoardPrices}>{feedLoading ? "Atualizando cotações…" : "Aceitar cotações atualizadas"}</button>
        </section> : null}
        <div className="betslip-pick"><span>{bets.length>1?'Cotação combinada':'Cotação selecionada'}</span><b>{totalOdds.toFixed(2)}</b></div>
        <label htmlFor="betslip-stake">Valor da aposta</label>
        <div className="betslip-stake-row"><span>R$</span><input id="betslip-stake" disabled={busy} inputMode="decimal" value={betAmount} onChange={event => onBetAmount(event.target.value)} aria-invalid={!!error} aria-describedby={error ? 'betslip-error' : undefined} /></div>
        <div className="betslip-quick-chips">{['5', '10', '25', '50', '100'].map(value => <button disabled={busy} key={value} onClick={() => onBetAmount(value)}>R$ {value}</button>)}</div>
        {funds != null ? <div className="betslip-slider"><input type="range" min="0" max={funds} step="50" value={stakeMinor} disabled={busy} aria-label="Arrastar para ajustar o valor da aposta" onChange={event => onBetAmount((Number(event.target.value) / 100).toFixed(2))} /><div className="betslip-slider-labels"><span>R$ 0</span><span>R$ {(funds / 100).toFixed(0)}</span></div></div> : null}
        <div className="betslip-adjust" aria-label="Ajustar valor da aposta"><button disabled={busy || stakeMinor<2} onClick={()=>adjustStake(Math.floor(stakeMinor/2))}>½ valor</button><button disabled={busy || !validStake || !Number.isSafeInteger(stakeMinor*2) || (funds!=null && stakeMinor*2>funds)} onClick={()=>adjustStake(stakeMinor*2)}>2× valor</button>{funds!=null?<button disabled={busy || funds<10} onClick={()=>adjustStake(Math.floor(funds/10))}>10% do saldo</button>:null}</div>
        {error ? <p id="betslip-error" className="betslip-error" role="status">{error}</p> : null}
        <div className="betslip-payout"><span>Retorno potencial</span><b>{payout}</b></div>
        <dl className="betslip-breakdown"><div><dt>Valor apostado</dt><dd>{BRL(stakeMinor)}</dd></div><div><dt>Lucro potencial</dt><dd>{BRL(Math.max(0,Math.round(stakeMinor*totalOdds)-stakeMinor))}</dd></div>{funds!=null?<><div><dt>Saldo após a aposta</dt><dd>{insufficient?'Saldo insuficiente':BRL(funds-stakeMinor)}</dd></div>{profile.bonus_minor>0?<div><dt>Bônus incluído no saldo</dt><dd>{BRL(profile.bonus_minor)}</dd></div>:null}</>:null}</dl>
        <p className="betslip-estimate">Estimativa com as cotações selecionadas. A confirmação depende da aceitação pelo servidor.</p>
      </div>
      <div className="betslip-footer">
        {state.message ? <p className={state.status==='error'?'betslip-error':'betslip-notice'} role="status">{state.message}</p> : null}
        {availability.unavailable.length > 0 ? <button className="betslip-submit" disabled={busy} onClick={() => focusReview(unavailableHeading)}>Revisar seleções indisponíveis</button> : state.status==='review' ? <div className="betslip-quote-review"><ul>{state.quote.legs.map((leg,index)=><li key={index}><span>{leg.selection}</span><span><s>{bets[index]?.price.toFixed(2)}</s> → {leg.price.toFixed(2)}</span></li>)}</ul><button className="betslip-submit" disabled={busy} onClick={onAcceptQuote}>Aceitar novas cotações</button></div> : reviewingBoard ? <button className="betslip-submit" disabled={busy} onClick={() => focusReview(priceReviewHeading)}>Revisar cotações atualizadas</button> : <button className="betslip-submit" disabled={busy || !!error || availability.unavailable.length>0 || availability.changed.length>0} onClick={onPlace}>{busy ? state.message || 'Enviando aposta…' : availability.changed.length>0 ? 'Aceite as novas cotações' : state.status==='error' ? 'Conferir e tentar novamente' : 'Confirmar aposta demo'}</button>}
        <details className="betslip-terms"><summary>Como funciona este boletim</summary><p>O retorno potencial inclui o valor apostado. Na múltipla, todas as seleções precisam vencer; anulações seguem as regras de liquidação. Só uma seleção por partida é permitida. Alterações de preço exigem sua aceitação, e a aposta só existe após a confirmação do servidor.</p><p>Saldo e retornos exibidos antes da confirmação são estimativas. Acompanhe o resultado no histórico.</p></details>
      </div>
    </section>
  );
}
