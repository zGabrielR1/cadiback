import { test } from 'node:test';
import assert from 'node:assert/strict';
import { matchKeyFromUrl, matchLink, matchFiltersFromUrl, navigateMatch } from './match-link.mjs';

test('fixture identities round-trip without leaking unrelated parameters or hashes', () => {
  const key = 'soccer:São Paulo/away?&=+#';
  const link = matchLink('https://example.test/?token=private&visual=blue#reset=secret', key);
  assert.equal(matchKeyFromUrl(link), key);
  assert.deepEqual([...new URL(link).searchParams.keys()], ['match']);
  assert.equal(new URL(link).hash, '');
  assert.equal(new URL(link).origin, 'https://example.test');
});

test('empty, oversized and control-character identities are ignored', () => {
  for (const query of ['', '?match=', '?match=%00bad', '?match=%0Abad', '?match=' + 'x'.repeat(513)]) {
    assert.equal(matchKeyFromUrl('https://example.test/' + query), null);
  }
  assert.equal(matchKeyFromUrl('/?match=normal-id'), 'normal-id');
});

test('navigation preserves unrelated queries, clears detail anchors and notifies mounted views', () => {
  const previous = globalThis.window;
  const calls = [];
  const location = new URL('https://example.test/?mode=local#detail-stats-title');
  globalThis.window = {
    location,
    history: {
      pushState: (state, title, url) => { calls.push(['push', url]); location.href = new URL(url, location).href; },
      replaceState: (state, title, url) => { calls.push(['replace', url]); location.href = new URL(url, location).href; },
    },
    dispatchEvent: event => calls.push(['event', event.type]),
  };
  try {
    navigateMatch('a&b');
    assert.equal(matchKeyFromUrl(location.href), 'a&b');
    assert.equal(location.searchParams.get('mode'), 'local');
    assert.equal(location.hash, '');
    navigateMatch(null, { replace: true });
    assert.equal(matchKeyFromUrl(location.href), null);
    assert.deepEqual(calls, [
      ['push', '/?mode=local&match=a%26b'], ['event', 'operator-match-change'],
      ['replace', '/?mode=local'], ['event', 'operator-match-change'],
    ]);
  } finally { globalThis.window = previous; }
});


test('public market filters round-trip while private selection state is excluded', () => {
  const link = matchLink('https://example.test/?token=secret#private', 'match-1', {
    category: 'totals', query: 'góls 2,5 & mais', selectedOnly: true, token: 'private',
  });
  assert.deepEqual(matchFiltersFromUrl(link), { category: 'totals', query: 'góls 2,5 & mais' });
  assert.deepEqual([...new URL(link).searchParams.keys()], ['match', 'marketCategory', 'marketSearch']);
  assert.equal(new URL(link).hash, '');
});

test('untrusted market filters are bounded and ignored without a fixture', () => {
  for (const value of ['/?marketCategory=totals&marketSearch=gols', '/?match=x&marketCategory=bad&marketSearch=%00secret', '/?match=x&marketSearch=' + 'x'.repeat(201)]) {
    assert.deepEqual(matchFiltersFromUrl(value), { category: 'all', query: '' });
  }
  const link = matchLink('https://example.test', 'x', { category: 'bad', query: ' x '.repeat(100) });
  assert.equal(matchFiltersFromUrl(link).category, 'all');
  assert.equal(matchFiltersFromUrl(link).query.length, 200);
});

test('leaving or switching matches drops filters belonging to the old match', () => {
  const previous = globalThis.window;
  const location = new URL('https://example.test/?match=a&marketCategory=totals&marketSearch=gols&mode=local');
  globalThis.window = { location, history: { pushState: (_, __, url) => { location.href = new URL(url, location).href; } }, dispatchEvent() {} };
  try {
    navigateMatch('b');
    assert.deepEqual(matchFiltersFromUrl(location.href), { category: 'all', query: '' });
    assert.equal(location.searchParams.get('mode'), 'local');
    assert.equal(matchKeyFromUrl(location.href), 'b');
  } finally { globalThis.window = previous; }
});
