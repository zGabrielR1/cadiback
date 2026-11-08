import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { readSportsFeed } from './sports-feed.mjs';

// Execute the actual hook body with controlled hook state, requests and timers.
// This checks its effect lifecycle, not React hydration or browser rendering.
const source = (await readFile(new URL('./useSportsFeed.js', import.meta.url), 'utf8'))
  .replace(/^import .*;\n/gm, '').replace('export function useSportsFeed', 'function useSportsFeed');
const createHook = new Function('useState', 'useEffect', 'api', 'readSportsFeed',
  'setTimeout', 'clearTimeout', 'Date', source + '\nreturn useSportsFeed;');

function harness(api) {
  const state = [], timers = new Map();
  let cursor = 0, deps, effect, cleanup, now = 1000, timerId = 0;
  const hook = createHook(initial => {
    const index = cursor++;
    if (!(index in state)) state[index] = initial;
    return [state[index], value => { state[index] = typeof value === 'function' ? value(state[index]) : value; }];
  }, (next, nextDeps) => {
    if (!deps || nextDeps.some((value, index) => value !== deps[index])) {
      deps = nextDeps;
      effect = next;
    }
  }, api, readSportsFeed, (callback, delay) => {
    const id = ++timerId;
    timers.set(id, { callback, due: now + delay });
    return id;
  }, id => timers.delete(id), { now: () => now });
  const render = (active = true) => {
    cursor = 0;
    const result = hook(active);
    if (effect) {
      cleanup?.();
      const next = effect;
      effect = undefined;
      cleanup = next();
    }
    return result;
  };
  return { render, timers,
    async settle(active = true) { await new Promise(resolve => setImmediate(resolve)); return render(active); },
    advance(ms) {
      now += ms;
      for (const [id, timer] of [...timers]) if (timer.due <= now) {
        timers.delete(id);
        timer.callback();
      }
    },
    close() { cleanup?.(); },
  };
}

const feed = { fixtures: [{ key: 'one', home: 'Casa', away: 'Fora' }] };

test('malformed refresh keeps the last successful board and timestamp until retry succeeds', async t => {
  const recovered = { fixtures: [{ ...feed.fixtures[0], home_score: 1 }] };
  const responses = [feed, { fixtures: [null] }, recovered];
  const calls = [];
  const app = harness(async (method, path, body, options) => {
    calls.push({ method, path, body, options });
    return responses.shift();
  });
  t.after(() => app.close());
  app.render();
  const first = await app.settle();
  assert.equal(first.sports, feed);
  assert.equal(first.updatedAt, 1000);
  app.advance(15000);
  const failed = await app.settle();
  assert.equal(failed.sports, feed);
  assert.equal(failed.updatedAt, first.updatedAt);
  assert.equal(failed.loading, false);
  assert.match(failed.error, /Tente novamente/);
  assert.equal(app.timers.size, 1);
  failed.retry();
  app.render();
  const success = await app.settle();
  assert.equal(success.sports, recovered);
  assert.equal(success.updatedAt, 16000);
  assert.equal(success.error, '');
  assert.equal(success.loading, false);
  assert.equal(app.timers.size, 1);
  assert.equal(calls.length, 3);
  assert.equal(calls[0].options.signal.aborted, true);
  assert.ok(calls.every(call => call.method === 'GET' && call.path === '/api/sports' && call.body === undefined));
});

test('malformed first load remains an error, then a valid empty feed clears it', async t => {
  const responses = [{ fixtures: [false] }, { fixtures: [] }];
  const app = harness(async () => responses.shift());
  t.after(() => app.close());
  app.render();
  const failed = await app.settle();
  assert.equal(failed.sports, null);
  assert.equal(failed.updatedAt, null);
  assert.match(failed.error, /Tente novamente/);
  app.advance(15000);
  const empty = await app.settle();
  assert.deepEqual(empty.sports, { fixtures: [] });
  assert.equal(empty.error, '');
});

test('leaving the sports view aborts its request and ignores a late valid response', async () => {
  let resolve, signal;
  const app = harness((method, path, body, options) => {
    signal = options.signal;
    return new Promise(done => { resolve = done; });
  });
  app.render();
  app.render(false);
  assert.equal(signal.aborted, true);
  assert.equal(app.timers.size, 0);
  resolve(feed);
  const left = await app.settle(false);
  assert.equal(left.sports, null);
  assert.equal(left.updatedAt, null);
  assert.equal(app.timers.size, 0);
  app.close();
});

test('slow requests never overlap polls and retry aborts the old response before recovery', async t => {
  const requests = [];
  const app = harness((method, path, body, options) => new Promise(resolve => {
    requests.push({ resolve, signal: options.signal });
  }));
  t.after(() => app.close());
  app.render();
  app.advance(6000);
  assert.equal(app.render().slow, true);
  app.advance(30000);
  assert.equal(requests.length, 1);
  app.render().retry();
  app.render();
  assert.equal(requests[0].signal.aborted, true);
  assert.equal(requests.length, 2);
  const recovered = { fixtures: [{ ...feed.fixtures[0], home_score: 2 }] };
  requests[1].resolve(recovered);
  const fresh = await app.settle();
  assert.equal(fresh.sports, recovered);
  assert.equal(fresh.slow, false);
  assert.equal(fresh.loading, false);
  requests[0].resolve(feed);
  assert.equal((await app.settle()).sports, recovered);
  assert.equal(app.timers.size, 1);
});
