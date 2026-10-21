import { test } from 'node:test';
import assert from 'node:assert/strict';
import { betIdentity, filterFixtures, validMarkets } from './sports.mjs';

test('selections distinguish fixture, market and line; absent lines agree', () => {
  const bet = { fixtureKey: 'a', marketKind: 'total', line: 2.5, selection: 'over' };
  assert.notEqual(betIdentity(bet), betIdentity({ ...bet, line: 3.5 }));
  assert.notEqual(betIdentity(bet), betIdentity({ ...bet, marketKind: 'total-h1' }));
  assert.equal(betIdentity({ ...bet, line: null }), betIdentity({ ...bet, line: undefined }));
});

test('markets reject incomplete, nonnumeric and invalid prices', () => {
  const market = { selections: ['home', 'away'], prices: [1.5, 2.5] };
  assert.deepEqual(validMarkets({ markets: [market, { ...market, prices: [2] }, { ...market, prices: [NaN, 2] }, { ...market, prices: [1, 2] }] }), [market]);
});

test('search, dates, live state and favorites combine without mutating fixtures', () => {
  const nowMs = new Date(2026, 9, 21, 12).getTime();
  const fixtures = [
    { key: 'a', sport: 'soccer', home: 'São Paulo', competition: 'Liga', kickoff: new Date(2026, 9, 21, 14).toISOString(), status: 'SCHEDULED' },
    { key: 'b', sport: 'soccer', home: 'São Paulo', competition: 'Liga', kickoff: new Date(2026, 9, 22, 14).toISOString(), status: 'FINAL' },
  ];
  assert.deepEqual(filterFixtures(fixtures, { nowMs, query: 'sao liga', date: 'today', favoritesOnly: true, favorites: ['a'] }), [fixtures[0]]);
  assert.deepEqual(filterFixtures(fixtures, { nowMs, date: 'tomorrow', liveOnly: true }), []);
  assert.deepEqual(filterFixtures(fixtures, { nowMs, date: 'upcoming' }), [fixtures[0]]);
  assert.deepEqual(filterFixtures(fixtures, { nowMs, date: 'results' }), [fixtures[1]]);
  assert.equal(fixtures.length, 2);
});
