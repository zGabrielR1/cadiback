import {test} from 'node:test';
import assert from 'node:assert/strict';
import {
  grantPortalAccess,
  hasPortalAccess,
  normalizeAccessCode,
  portalCode,
  revokePortalAccess,
} from './access.mjs';

function storage(initial = {}) {
  const rows = new Map(Object.entries(initial));
  return {
    getItem: key => (rows.has(key) ? rows.get(key) : null),
    setItem: (key, value) => rows.set(key, String(value)),
    removeItem: key => rows.delete(key),
  };
}

test('access codes ignore case, accents and surrounding space', () => {
  assert.equal(normalizeAccessCode('  Feed-Seguro  '), 'feed-seguro');
  assert.equal(normalizeAccessCode('CÓDIGO   OPERACIONAL'), 'codigo operacional');
  assert.equal(normalizeAccessCode(''), '');
});

test('a session stays locked until the operational code is accepted', () => {
  const store = storage();
  assert.equal(hasPortalAccess(store), false);
  assert.equal(grantPortalAccess('not-the-code', store), false);
  assert.equal(hasPortalAccess(store), false);

  assert.equal(grantPortalAccess(portalCode().toUpperCase(), store), true);
  assert.equal(hasPortalAccess(store), true);

  revokePortalAccess(store);
  assert.equal(hasPortalAccess(store), false);
});

test('an unavailable storage keeps the public surface locked', () => {
  assert.equal(hasPortalAccess({ getItem() { throw new Error('blocked'); } }), false);
  assert.equal(grantPortalAccess(portalCode(), { setItem() { throw new Error('blocked'); } }), false);
});
