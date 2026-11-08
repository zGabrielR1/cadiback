import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readSportsFeed } from './sports-feed.mjs';

const fixture = { key: 'one', home: 'São Paulo', away: 'Santos' };

test('valid feeds preserve identities, optional data, zero scores and empty calendars', () => {
  for (const fixtures of [[], [fixture], [{ ...fixture, home: '', away: '', status: null,
    sport: 'future_sport', kickoff: '', home_score: 0, away_score: null, markets: [null] }]]) {
    const feed = Object.freeze({ fixtures: Object.freeze(fixtures), source: null });
    assert.equal(readSportsFeed(feed), feed);
    assert.equal(feed.fixtures, fixtures);
  }
});

test('invalid feed envelopes and rendered metadata fail closed', () => {
  for (const feed of [null, [], {}, { fixtures: {} }, { fixtures: [fixture], source: {} },
    { fixtures: [fixture], note: [] }]) {
    assert.throws(() => readSportsFeed(feed), /invalid sports feed/);
  }
});

test('malformed fixtures, keys and display headers reject the entire refresh', () => {
  const invalid = [null, [], false, 1, 'invalid', {},
    ...[null, 1, '', ' '].map(key => ({ ...fixture, key })),
    ...['home', 'away', 'sport', 'competition', 'country', 'status', 'progress', 'kickoff']
      .map(key => ({ ...fixture, [key]: {} })),
    ...['home_score', 'away_score'].flatMap(key => [NaN, Infinity, {}, '2'].map(value => ({ ...fixture, [key]: value }))),
  ];
  for (const entry of invalid) {
    assert.throws(() => readSportsFeed({ fixtures: [{ ...fixture, key: 'healthy' }, entry] }), /invalid sports feed/);
  }
});

test('duplicate fixture identities reject the refresh rather than ambiguously target saved selections', () => {
  assert.throws(() => readSportsFeed({ fixtures: [fixture, { ...fixture, home: 'Other' }] }), /invalid sports feed/);
  const distinct = { fixtures: [fixture, { ...fixture, key: 'two' }] };
  assert.equal(readSportsFeed(distinct), distinct);
});
