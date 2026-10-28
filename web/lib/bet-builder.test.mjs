import { test } from 'node:test';
import assert from 'node:assert/strict';
import { statPair, builderMarkets, builderBet, refreshDraft, toggleDraft, sportProfile } from './bet-builder.mjs';

test('sports use compatible statistics, market groups and feed aliases',()=>{
  for(const sport of ['basketball','tennis','hockey','football','volleyball','baseball','esports']){
    const profile=sportProfile(sport);
    assert(!profile.stats.some(stat=>['yellow_cards','red_cards','corners'].includes(stat.key)));
    assert(!profile.groups.some(group=>group.kinds.includes('corners')));
    assert(!profile.total.includes('gols') || sport==='hockey');
    assert.deepEqual(builderMarkets({sport,markets:[market]},'discipline'),[]);
  }
  assert(sportProfile('football').stats.some(stat=>stat.key==='passing_yards'));
  assert(sportProfile('hockey').stats.some(stat=>stat.key==='saves'));
  assert(sportProfile('futsal').groups.some(group=>group.id==='discipline'));
  assert.deepEqual(sportProfile('unknown-sport').stats,[]);
});

const market = { kind: 'cards', line: 4.5, selections: ['Mais', 'Menos'], prices: [1.8, 2.1] };
const fixture = { key: 'match-a', home: 'Casa', away: 'Visitante', markets: [market], stats: { yellow_cards: [0, 2] } };

test('builder distinguishes missing, partial, invalid and confirmed zero stats', () => {
  assert.deepEqual(statPair(fixture, 'yellow_cards'), [0, 2]);
  assert.deepEqual(statPair(fixture, 'fouls'), [null, null]);
  assert.deepEqual(statPair({ stats: { match: { fouls: [null, 8] } } }, 'fouls'), [null, 8]);
  assert.deepEqual(statPair({ stats: { fouls: ['9', -1] } }, 'fouls'), [null, null]);
});

test('builder exposes only supplied valid markets for the requested group', () => {
  assert.deepEqual(builderMarkets(fixture, 'players'), []);
  assert.deepEqual(builderMarkets(fixture, 'discipline'), [market]);
  assert.deepEqual(builderMarkets({ markets: [{ ...market, prices: [0, 1.8] }] }, 'discipline'), []);
  assert.equal(builderBet(fixture, market, 'Missing player'), null);
});

test('draft refreshes prices and drops removed markets, players and fixtures', () => {
  const bet = builderBet(fixture, market, 'Mais');
  assert.equal(refreshDraft([bet], { ...fixture, markets: [{ ...market, prices: [1.95, 1.9] }] })[0].price, 1.95);
  assert.deepEqual(refreshDraft([bet], { ...fixture, markets: [] }), []);
  assert.deepEqual(refreshDraft([bet], { ...fixture, key: 'match-b' }), []);
  assert.deepEqual(refreshDraft([bet], { ...fixture, markets: [{ ...market, selections: ['Outro'], prices: [2.5] }] }), []);
  assert.equal(toggleDraft([], bet).length, 1);
  assert.equal(toggleDraft([bet], bet).length, 0);
});
