import { betIdentity } from './sports.mjs';
import { sportProfile } from './bet-builder.mjs';

const LABELS = {
  '1x2': 'Resultado da partida', moneyline: 'Vencedor', dc: 'Dupla chance',
  dnb: 'Empate anula', ah: 'Handicap', btts: 'Ambas marcam',
  corners: 'Escanteios', cards: 'Cartões amarelos', 'red-cards': 'Cartões vermelhos',
  fouls: 'Faltas', 'scorer-h': 'Marcadores da casa', 'scorer-a': 'Marcadores visitantes',
};
const CATEGORIES = [
  { id: 'result', label: 'Resultado', kinds: ['1x2', 'moneyline', 'dc', 'dnb', 'ah'] },
  { id: 'totals', label: 'Totais', kinds: ['total', 'total-h1', 'total-h2', 'btts'] },
  { id: 'discipline', label: 'Faltas e cartões', kinds: ['fouls', 'cards', 'red-cards'] },
  { id: 'corners', label: 'Escanteios', kinds: ['corners'] },
  { id: 'players', label: 'Jogadores', kinds: ['scorer-h', 'scorer-a'] },
  { id: 'other', label: 'Outros', kinds: [] },
];
const normalized = value => String(value ?? '').normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/(\d),(\d)/g, '$1.$2');
const categoryFor = market => CATEGORIES.find(category => category.kinds.includes(market.kind))?.id || 'other';

export function marketLabel(kind, sport) {
  const profile = sportProfile(sport);
  if (kind === 'total') return profile.total;
  if (kind === 'total-h1' || kind === 'total-h2') {
    const period = kind === 'total-h1' ? '1º' : '2º';
    return ['soccer', 'futsal', undefined].includes(sport)
      ? `Total de gols · ${period} tempo` : `${profile.total} · ${period} período`;
  }
  return LABELS[kind] || kind || 'Mercado';
}

export function marketCategories(markets) {
  return [{ id: 'all', label: 'Todos', count: markets.length }, ...CATEGORIES.map(category => ({
    id: category.id, label: category.label,
    count: markets.filter(market => categoryFor(market) === category.id).length,
  }))];
}

export function filterMatchMarkets(markets, { sport, category = 'all', query = '', selectedOnly = false, fixtureKey, selectedBets = [] } = {}) {
  const terms = normalized(query).trim().split(/\s+/).filter(Boolean);
  const selected = new Set(selectedBets.map(betIdentity));
  return markets.filter(market => {
    if (category !== 'all' && categoryFor(market) !== category) return false;
    if (selectedOnly && !market.selections.some(selection => selected.has(betIdentity({
      fixtureKey, marketKind: market.kind, line: market.line, selection,
    })))) return false;
    const text = normalized([marketLabel(market.kind, sport), market.kind,
      market.line, ...market.selections, market.pricing === 'market' ? 'provedor' : 'modelo'].join(' '));
    return terms.every(term => text.includes(term));
  });
}
