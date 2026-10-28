import { test } from 'node:test';
import assert from 'node:assert/strict';
import { betIdentity, filterFixtures, validMarkets, matchState } from './sports.mjs';

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

test('all-sport search and favorites find matches beyond the default sport', () => {
  const fixtures = [
    { key: 'football', sport: 'soccer', home: 'São Paulo', competition: 'Liga' },
    { key: 'basket', sport: 'basketball', home: 'Franca', competition: 'Liga' },
    { key: 'tennis', sport: 'tennis', home: 'Beatriz', competition: 'Aberto' },
  ];
  assert.deepEqual(filterFixtures(fixtures, { sport: null, favoritesOnly: true, favorites: ['basket', 'tennis', 'absent'] }), fixtures.slice(1));
  assert.deepEqual(filterFixtures(fixtures, { query: 'basquete franca' }), [fixtures[1]]);
  assert.deepEqual(filterFixtures(fixtures, { query: 'tenis beatriz' }), [fixtures[2]]);
  assert.deepEqual(filterFixtures(fixtures, { query: 'futebol sao' }), [fixtures[0]]);
  assert.deepEqual(filterFixtures(fixtures, { sport: 'soccer', query: 'basquete' }), []);
  assert.deepEqual(filterFixtures(fixtures, { favoritesOnly: true, favorites: ['absent'] }), []);
  assert.equal(fixtures.length, 3);
});


test('unavailable match states share labels and override live/final hints', () => {
  for (const [status, label] of [['POSTPONED', 'Adiada'], ['STATUS_CANCELLED', 'Cancelada'], ['SUSPENDED_LIVE', 'Suspensa'], ['ABANDONED_FINAL', 'Abandonada']]) {
    const state = matchState({ status });
    assert.equal(state.label, label);
    assert.equal(state.selectable, false);
    assert.equal(state.unavailable, true);
    assert.equal(state.live, false);
    assert.equal(state.ended, false);
  }
  for (const status of ['FINAL', 'STATUS_FINAL', 'AET', 'FT']) {
    assert.equal(matchState({ status }).selectable, false);
    assert.equal(matchState({ status }).label, 'Encerrada');
  }
  for (const status of ['SCHEDULED', 'STATUS_SCHEDULED', 'LIVE', 'IN_PROGRESS', undefined]) {
    assert.equal(matchState({ status }).selectable, true);
  }
  assert.equal(matchState(null).selectable, false);
});

test('upcoming and live discovery exclude unavailable matches without hiding them from all dates', () => {
  const nowMs = Date.parse('2026-10-27T12:00:00Z');
  const fixtures = ['STATUS_SCHEDULED', 'POSTPONED', 'CANCELLED', 'SUSPENDED_LIVE', 'ABANDONED', 'FINAL', 'LIVE'].map((status, index) => ({ key: String(index), status, kickoff: '2026-11-01T12:00:00Z' }));
  assert.deepEqual(filterFixtures(fixtures, { date: 'upcoming', nowMs }), [fixtures[0]]);
  assert.deepEqual(filterFixtures(fixtures, { liveOnly: true, nowMs }), [fixtures[6]]);
  assert.deepEqual(filterFixtures(fixtures, { date: 'results', nowMs }), [fixtures[5]]);
  assert.deepEqual(filterFixtures(fixtures, { nowMs }), fixtures);
});
