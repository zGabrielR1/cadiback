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

const RESULT = ['1x2', 'moneyline', 'dc', 'dnb', 'ah', 'total', 'total-h1', 'total-h2'];
export const SPORT_LABELS = {soccer:'Futebol',futsal:'Futsal',football:'Futebol americano',basketball:'Basquete',tennis:'Tênis',volleyball:'Vôlei',ice_hockey:'Hóquei no gelo',hockey:'Hóquei',baseball:'Beisebol',american_football:'Futebol americano',rugby:'Rugby',handball:'Handebol',cricket:'Críquete',esports:'Esports',mma:'MMA',boxing:'Boxe',table_tennis:'Tênis de mesa'};
export function sportProfile(sport = 'soccer') {
  sport = ({football:'american_football',hockey:'ice_hockey',futsal:'soccer'})[sport] || sport;
  if (sport === 'soccer') return {groups:BUILDER_GROUPS,stats:BUILDER_STATS,total:'Total de gols'};
  const stats = {
    basketball:[['points','Pontos'],['rebounds','Rebotes'],['assists','Assistências'],['fouls','Faltas pessoais'],['three_pointers','Cestas de três']],
    tennis:[['aces','Aces'],['double_faults','Duplas faltas'],['break_points_won','Break points convertidos'],['games_won','Games vencidos']],
    table_tennis:[['points','Pontos'],['sets_won','Sets vencidos']],
    volleyball:[['aces','Aces'],['blocks','Bloqueios'],['attack_points','Pontos de ataque'],['sets_won','Sets vencidos']],
    ice_hockey:[['shots_on_target','Chutes ao gol'],['penalty_minutes','Minutos de penalidade'],['saves','Defesas']],
    baseball:[['hits','Rebatidas'],['runs','Corridas'],['errors','Erros'],['strikeouts','Strikeouts']],
    american_football:[['total_yards','Jardas totais'],['passing_yards','Jardas de passe'],['rushing_yards','Jardas terrestres'],['touchdowns','Touchdowns']],
    handball:[['goals','Gols'],['saves','Defesas'],['turnovers','Perdas de bola']],
    cricket:[['runs','Corridas'],['wickets','Wickets'],['overs','Overs']],
    esports:[['kills','Abates'],['deaths','Mortes'],['assists','Assistências']],
  };
  const total = ['tennis','table_tennis'].includes(sport)?'Total de games / pontos':sport==='baseball'?'Total de corridas':['hockey','ice_hockey','handball'].includes(sport)?'Total de gols':'Total de pontos';
  const groups=[{id:'result',label:'Resultado e totais',kinds:RESULT}];
  if(sport==='basketball')groups.push({id:'discipline',label:'Faltas',kinds:['fouls']});
  if(sport==='rugby')groups.push({id:'discipline',label:'Disciplina',kinds:['cards','red-cards']});
  return {groups,stats:(stats[sport]||[]).map(([key,label])=>({key,label})),total};
}

// Missing is never converted to zero, and current-match counts never become
// historical team averages. Both sides must be valid to draw a comparison.
export function statPair(fixture, key) {
  const section = fixture?.stats?.match || fixture?.stats || {};
  const pair = section[key];
  if (!Array.isArray(pair) || pair.length !== 2) return [null, null];
  return pair.map(value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null);
}

export function builderMarkets(fixture, group = 'result') {
  const kinds = sportProfile(fixture?.sport || 'soccer').groups.find(item => item.id === group)?.kinds || [];
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
