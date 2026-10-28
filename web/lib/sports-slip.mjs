import { betIdentity, validMarkets, matchState } from './sports.mjs';

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
    if (!matchState(fixture).selectable || index<0) unavailable.push(betIdentity(bet));
    else if (market.prices[index]!==bet.price) changed.push({id:betIdentity(bet),price:market.prices[index]});
  }
  return {changed,unavailable};
}

/** Explicit acceptance updates only prices for existing selection identities. */
export function applyPriceChanges(bets, changes) {
  const prices = new Map(changes
    .filter(change => typeof change.id === 'string' && Number.isFinite(change.price) && change.price > 1)
    .map(change => [change.id, change.price]));
  return bets.map(bet => {
    const price = prices.get(betIdentity(bet));
    return price === undefined || price === bet.price ? bet : { ...bet, price };
  });
}
