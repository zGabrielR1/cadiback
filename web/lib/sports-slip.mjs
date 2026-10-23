import { betIdentity, validMarkets } from './sports.mjs';

export function toggleSelection(previous, bet) {
  if (previous.some(item => betIdentity(item) === betIdentity(bet))) return previous.filter(item => betIdentity(item) !== betIdentity(bet));
  return [...previous.filter(item => item.fixtureKey !== bet.fixtureKey), bet];
}

export function toLegs(bets) {
  return bets.map(bet => ({fixture_key:bet.fixtureKey, market_kind:bet.marketKind, line:bet.line ?? null, selection:bet.selection, price:bet.price}));
}

export function fromQuote(quote) {
  return quote.legs.map(leg => ({fixtureKey:leg.fixture_key, marketKind:leg.market_kind, line:leg.line ?? null, selection:leg.selection, price:leg.price, home:leg.home, away:leg.away, competition:leg.competition}));
}

export function selectionAvailability(bets, sports) {
  if (!sports) return { changed: [], unavailable: [] };
  const changed=[], unavailable=[];
  for (const bet of bets) {
    const fixture=sports.fixtures.find(f=>f.key===bet.fixtureKey);
    const market=fixture && validMarkets(fixture).find(m=>m.kind===bet.marketKind && String(m.line??'')===String(bet.line??''));
    const index=market?.selections.indexOf(bet.selection) ?? -1;
    if (!fixture || /FINAL|AET|\bFT\b|CANCEL|POSTPON|SUSPEND|ABANDON/i.test(fixture.status||'') || index<0) unavailable.push(betIdentity(bet));
    else if (market.prices[index]!==bet.price) changed.push({id:betIdentity(bet),price:market.prices[index]});
  }
  return {changed,unavailable};
}
