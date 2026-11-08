import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

const source = await readFile(new URL('./localCache.js', import.meta.url), 'utf8');
const { readRecent, rememberGame, clearRecent, RECENT_LIMIT } =
  await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const KEY = 'casa-recent';
const game = { game_id: 'healthy', title: 'Jogo São Paulo', provider: 'provider_demo',
  category: 'Slots', cover: '/games/healthy.svg', rtp: 96.5, demo_url: 'https://example.test/demo', notes: 'Demo' };

function storage(t, raw) {
  const original = globalThis.window;
  const values = new Map(raw === undefined ? [] : [[KEY, raw]]);
  const store = { getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  globalThis.window = { localStorage: store };
  t.after(() => { if (original === undefined) delete globalThis.window; else globalThis.window = original; });
  return { store, values };
}

test('malformed timestamps cannot throw or outrank a valid recent game', t => {
  storage(t, JSON.stringify({ v: 2, entries: [
    { game_id: 'object', ts: { valueOf: null, toString: null } },
    { game_id: 'array', ts: [999999] }, { game_id: 'infinite', ts: 'Infinity' },
    { game_id: 'nonnumeric', ts: 'invalid' }, { game_id: game.game_id, ts: 12, game },
    { game_id: 'numeric-string', ts: '10' },
  ] }));
  const rows = readRecent();
  assert.deepEqual(rows.map(row => row.game_id).slice(0, 2), ['healthy', 'numeric-string']);
  assert.ok(rows.slice(2).every(row => row.ts === 0));
  assert.deepEqual(rows[0].game, game);
});

test('invalid identities are skipped; mismatched snapshots stay id-only', t => {
  const invalid = [null, [], false, 1, 'invalid', ...[{}, [], 1, false, ' '].map(game_id => ({ game_id }))];
  storage(t, JSON.stringify({ entries: [...invalid,
    { game_id: 'ordered', ts: 2, game }, { ts: 1, game },
  ] }));
  const rows = readRecent();
  assert.deepEqual(rows.map(row => row.game_id), ['ordered', 'healthy']);
  assert.equal(rows[0].game, null);
  assert.deepEqual(rows[1].game, game);
});

test('bad cached labels and fields cannot escape as renderable game snapshots', t => {
  const fields = ['title', 'provider', 'category', 'cover', 'demo_url', 'notes', 'rtp'];
  storage(t, JSON.stringify({ v: 2, entries: [
    ...fields.map((field, index) => ({ game_id: String(index), ts: index,
      game: { ...game, game_id: String(index), [field]: {} } })),
    { game_id: 'blank', game: { game_id: 'blank', title: ' ' } },
    { game_id: 'incomplete', game: { game_id: 'incomplete' } },
    { game_id: 'healthy', ts: 100, game },
  ] }));
  const rows = readRecent();
  assert.deepEqual(rows[0].game, game);
  assert.ok(rows.slice(1).every(row => row.game === null));
});

test('valid writes retain exact labels, trim extra fields, deduplicate and respect the limit', t => {
  storage(t);
  for (let index = 0; index < RECENT_LIMIT + 3; index++) rememberGame({ ...game, game_id: String(index) });
  const padded = { ...game, game_id: ' padded ', title: ' Éder ', rtp: '96.5', internal: 'omit' };
  rememberGame(padded);
  const rows = rememberGame(padded);
  assert.equal(rows.length, RECENT_LIMIT);
  assert.equal(rows.filter(row => row.game_id === padded.game_id).length, 1);
  assert.deepEqual(rows[0].game, { ...game, game_id: ' padded ', title: ' Éder ', rtp: '96.5' });
  assert.deepEqual(readRecent()[0].game, rows[0].game);
});

test('invalid writes preserve existing recents and their stored bytes', t => {
  const raw = JSON.stringify({ v: 2, entries: [{ game_id: 'healthy', ts: 1, game }] });
  const { values } = storage(t, raw);
  for (const input of [null, [], {}, { ...game, game_id: {} }, { ...game, title: {} }, { ...game, rtp: Infinity }]) {
    assert.equal(rememberGame(input)[0].game_id, 'healthy');
    assert.equal(values.get(KEY), raw);
  }
});

test('quota failure keeps id-only ordering and clear removes the cache', t => {
  const { store, values } = storage(t);
  const setItem = store.setItem;
  store.setItem = (key, value) => {
    if (key === KEY && JSON.parse(value).entries.some(row => row.game)) throw new Error('quota');
    setItem(key, value);
  };
  rememberGame(game);
  const rows = readRecent();
  assert.equal(rows[0].game_id, 'healthy');
  assert.equal(rows[0].game, null);
  clearRecent();
  assert.equal(values.has(KEY), false);
});

test('missing, denied, corrupt and unavailable storage remains best-effort', t => {
  const { store, values } = storage(t);
  for (const raw of ['{bad', 'null', '42', '{}', '{"entries":{}}']) {
    values.set(KEY, raw);
    assert.deepEqual(readRecent(), []);
  }
  store.getItem = () => { throw new Error('unavailable'); };
  assert.deepEqual(readRecent(), []);
  Object.defineProperty(window, 'localStorage', { get() { throw new Error('denied'); } });
  assert.deepEqual(readRecent(), []);
  assert.doesNotThrow(() => rememberGame(game));
  assert.doesNotThrow(clearRecent);
  delete globalThis.window;
  assert.deepEqual(readRecent(), []);
});
