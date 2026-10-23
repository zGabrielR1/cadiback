import { validMarkets, betIdentity } from './sports.mjs';

export const BUILDER_GROUPS = [
  { id: 'result', label: 'Resultado e gols', kinds: ['1x2', 'moneyline', 'dc', 'dnb', 'ah', 'btts', 'total', 'total-h1', 'total-h2'] },
  { id: 'discipline', label: 'Faltas e cartões', kinds: ['fouls', 'cards', 'red-cards'] },
  { id: 'corners', label: 'Escanteios', kinds: ['corners'] },
  { id: 'players', label: 'Jogadores', kinds: ['scorer-h', 'scorer-a'] },
];

export const BUILDER_STATS = [
  { key: 'fouls', label: 'Faltas cometidas' },
  { key: 'yellow_cards', label: 'Cartões amarelos' },
  { key: 'red_cards', label: 'Cartões vermelhos' },
  { key: 'corners', label: 'Escanteios' },
  { key: 'shots', label: 'Finalizações' },
  { key: 'shots_on_target', label: 'Finalizações no gol' },
  { key: 'possession', label: 'Posse de bola', unit: '%' },
];

// Missing is never converted to zero, and current-match counts never become
// historical team averages. Both sides must be valid to draw a comparison.
export function statPair(fixture, key) {
  const section = fixture?.stats?.match || fixture?.stats || {};
  const pair = section[key];
  if (!Array.isArray(pair) || pair.length !== 2) return [null, null];
  return pair.map(value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null);
}

export function builderMarkets(fixture, group = 'result') {
  const kinds = BUILDER_GROUPS.find(item => item.id === group)?.kinds || [];
  return validMarkets(fixture || {}).filter(market => kinds.includes(market.kind));
}

export function builderBet(fixture, market, selection) {
  const index = market?.selections?.indexOf(selection) ?? -1;
  if (!fixture || index < 0 || !validMarkets({ markets: [market] }).length) return null;
  return { fixtureKey: fixture.key, home: fixture.home, away: fixture.away,
    competition: fixture.competition, marketKind: market.kind,
    selection, price: market.prices[index], line: market.line ?? null };
}

// Reconcile draft selections with each refresh. Never silently submit an old
// price, a removed player, or a market that no longer exists.
export function refreshDraft(draft, fixture) {
  return draft.flatMap(bet => {
    if (bet.fixtureKey !== fixture?.key) return [];
    const market = validMarkets(fixture).find(m => m.kind === bet.marketKind && String(m.line ?? '') === String(bet.line ?? '') && m.selections.includes(bet.selection));
    const next = market && builderBet(fixture, market, bet.selection);
    return next ? [next] : [];
  });
}

export function toggleDraft(draft, bet) {
  return draft.some(item => betIdentity(item) === betIdentity(bet))
    ? draft.filter(item => betIdentity(item) !== betIdentity(bet)) : [...draft, bet];
}
