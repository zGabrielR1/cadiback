/* Component render smoke checks, without a web server or live APIs.
 * Run: node scripts/check_market_render.cjs (Node 22.12+, npm ci in web).
 * Uses the installed Next compiler to load the actual JSX components. This is
 * static React rendering: effects, hydration, clicks and layout are not tested.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const web = path.resolve(__dirname, '../web');
const fromWeb = Module.createRequire(path.join(web, 'package.json'));
const { transformSync } = fromWeb('next/dist/build/swc');
const React = fromWeb('react');
const { renderToStaticMarkup } = fromWeb('react-dom/server');
const previousLoader = Module._extensions['.jsx'];
let renders = 0;

Module._extensions['.jsx'] = (loaded, filename) => {
  assert.ok(filename.startsWith(path.join(web, 'app') + path.sep));
  const result = transformSync(fs.readFileSync(filename, 'utf8'), {
    filename,
    jsc: {
      parser: { syntax: 'ecmascript', jsx: true },
      transform: { react: { runtime: 'automatic' } },
      target: 'es2022',
    },
    module: { type: 'commonjs' },
  });
  loaded._compile(result.code, filename);
};

const freeze = value => {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
};

try {
  const component = name => fromWeb(path.join(web, 'app/components', name + '.jsx')).default;
  const SportsHome = component('SportsHome');
  const MarketDetail = component('MarketDetail');
  const BetBuilder = component('BetBuilder');
  const CasinoSports = component('CasinoSports');
  const { readSportsFeed } = fromWeb(path.join(web, 'lib/sports-feed.mjs'));
  const render = (Component, props) => {
    renders++;
    return renderToStaticMarkup(React.createElement(Component, props));
  };
  const market = freeze({ kind: '1x2', selections: ['Casa', 'Empate', 'Fora'], prices: [2, 3, 4], pricing: 'market' });
  const cases = [
    ['absent', undefined, false], ['null', null, false], ['object', {}, false],
    ['string', 'invalid', false], ['empty', [], false],
    ['malformed entries', [null, false, 0, 'invalid', {}], false],
    ['object outcome', [{ ...market, selections: ['Casa', {}, 'Fora'] }], false],
    ['null outcome', [{ ...market, selections: ['Casa', null, 'Fora'] }], false],
    ['blank outcome', [{ ...market, selections: ['Casa', '  ', 'Fora'] }], false],
    ['mixed', [null, {}, market, { ...market, prices: [1, 2, 3] }], true],
    ['healthy', [market], true],
  ];
  for (const [name, markets, hasPrices] of cases) {
    const fixture = freeze({ key: 'qa-one', home: 'Casa QA', away: 'Fora QA',
      competition: 'Liga QA', sport: 'soccer', status: 'LIVE', markets });
    const sibling = freeze({ ...fixture, key: 'qa-two', home: 'Equipe preservada', markets: [market] });
    for (const authenticated of [false, true]) {
      const context = `${name}, ${authenticated ? 'member' : 'guest'}`;
      const detail = render(MarketDetail, { fixture, authenticated, selectedBets: [] });
      assert.ok(detail.includes('Casa QA'), context);
      assert.equal(detail.includes('class="market-detail-market"'), hasPrices, context);
      assert.equal(detail.includes('A fonte não enviou cotações válidas para esta partida.'), !hasPrices, context);
      if (hasPrices) {
        assert.match(detail, authenticated ? /<button[^>]*aria-pressed="false"/ : /class="market-detail-price"/, context);
        assert.ok(detail.includes('2.00'), context);
      }
      const board = render(SportsHome, { sports: readSportsFeed({ fixtures: [fixture, sibling] }),
        authenticated, selectedBets: [], design: 'auteur' });
      assert.ok(board.includes('Casa QA') && board.includes('Equipe preservada'), context);
      assert.equal(board.includes('class="sx-nomarket"'), !hasPrices, context);
    }
    const builder = render(BetBuilder, { fixtures: [fixture, sibling], initialKey: fixture.key });
    assert.ok(builder.includes('Casa QA'), name);
    assert.equal(builder.includes('class="builder-market"'), hasPrices, name);
    assert.equal(builder.includes('Mercados ainda indisponíveis'), !hasPrices, name);
  }
  const fixture = { key: 'saved', home: 'Casa preservada', away: 'Fora preservada',
    status: 'LIVE', sport: 'soccer', markets: [market] };
  const saved = readSportsFeed({ fixtures: [fixture] });
  assert.throws(() => readSportsFeed({ fixtures: [null] }), /invalid sports feed/);
  const oddsTags = html => [...html.matchAll(/<button\b[^>]*>/g)]
    .map(match => match[0]).filter(tag => /class="sx-odd|title="Cotação:/.test(tag));
  for (const authenticated of [false, true]) {
    const props = { sports: saved, authenticated, selectedBets: [], design: 'auteur' };
    const paused = render(SportsHome, { ...props, error: 'Atualização inválida.' });
    assert.ok(paused.includes('Casa preservada') && paused.includes('Tentar novamente'));
    const pausedPrices = oddsTags(paused);
    assert.ok(pausedPrices.length > 0);
    assert.ok(pausedPrices.every(tag => tag.includes('disabled=""')));
    const resumed = render(SportsHome, props);
    assert.ok(resumed.includes('Casa preservada') && !resumed.includes('Atualização indisponível'));
    assert.equal(oddsTags(resumed).length, pausedPrices.length);
    assert.ok(oddsTags(resumed).every(tag => !tag.includes('disabled=""')));
    const initialFailure = render(SportsHome, { ...props, sports: null, error: 'Atualização inválida.' });
    assert.ok(initialFailure.includes('As partidas ainda não chegaram.') && initialFailure.includes('Tentar novamente'));
    const detail = render(MarketDetail, { fixture, authenticated, selectedBets: [], error: 'Atualização inválida.' });
    assert.ok(detail.includes('Casa preservada') && detail.includes('Tentar novamente'));
    if (authenticated) assert.match(detail, /<button[^>]*disabled=""/);
  }
  const receivedAt = Date.parse('2026-10-28T18:00:00Z');
  const casino = (overrides = {}) => ({ sports: saved, loading: false, slow: false,
    error: '', updatedAt: receivedAt, ...overrides });
  const firstLoad = render(CasinoSports, casino({ sports: null, loading: true, updatedAt: null }));
  assert.ok(firstLoad.includes('Carregando partidas…') && !firstLoad.includes('Tentar novamente'));
  const slowLoad = render(CasinoSports, casino({ sports: null, loading: true, slow: true, updatedAt: null }));
  assert.ok(slowLoad.includes('A conexão está demorando.') && slowLoad.includes('Tentar novamente'));
  const firstError = render(CasinoSports, casino({ sports: null, error: 'Falha de atualização.', updatedAt: null }));
  assert.ok(firstError.includes('Não foi possível carregar as cotações.') && firstError.includes('Tentar novamente'));
  assert.ok(!firstError.includes('Carregando partidas…') && !firstError.includes('boost-link'));
  const freshCasino = render(CasinoSports, casino());
  assert.ok(freshCasino.includes('Casa preservada') && freshCasino.includes('2026-10-28T18:00:00.000Z'));
  assert.ok(!freshCasino.includes('Tentar novamente') && !freshCasino.includes('indisponível'));
  const refreshingCasino = render(CasinoSports, casino({ loading: true }));
  assert.ok(refreshingCasino.includes('Atualizando cotações…') && refreshingCasino.includes('Casa preservada'));
  for (const loading of [false, true]) {
    const staleCasino = render(CasinoSports, casino({ error: 'Falha de atualização.', loading }));
    assert.ok(staleCasino.includes('Casa preservada') && staleCasino.includes('As últimas cotações recebidas continuam visíveis para consulta.'));
    assert.ok(staleCasino.includes('2026-10-28T18:00:00.000Z'));
    const tags = [...staleCasino.matchAll(/<button\b[^>]*>/g)].map(match => match[0]);
    const retry = tags.find(tag => tag.includes('class="ghost"'));
    assert.equal(retry.includes('disabled=""'), loading);
    assert.ok(tags.filter(tag => tag.includes('boost-link')).every(tag => !tag.includes('disabled=""')));
  }
  for (const sports of [{ fixtures: [] }, { fixtures: [{ ...fixture, markets: [null] }] }]) {
    const emptyCasino = render(CasinoSports, casino({ sports }));
    assert.ok(emptyCasino.includes('Nenhuma partida com preço disponível no último calendário recebido.'));
    assert.ok(!emptyCasino.includes('boost-link'));
  }
  const cappedCasino = render(CasinoSports, casino({ sports: { fixtures: Array.from({ length: 4 }, (_, index) => ({ ...fixture, key: String(index) })) } }));
  assert.equal((cappedCasino.match(/class="boost boost-link"/g) || []).length, 3);
  const buttons = element => {
    if (Array.isArray(element)) return element.flatMap(buttons);
    if (!React.isValidElement(element)) return [];
    return [...(element.type === 'button' ? [element] : []), ...buttons(element.props.children)];
  };
  const calls = [];
  const controls = buttons(CasinoSports(casino({ error: 'Falha de atualização.', retry: () => calls.push('retry'), onSport: live => calls.push(['sport', live]) })));
  controls.find(button => button.props.className === 'ghost').props.onClick();
  controls.find(button => button.props.className === 'boost boost-link').props.onClick();
  assert.deepEqual(calls, ['retry', ['sport', false]]);
  console.log(`PASS: ${renders} component renders; malformed markets, sports/casino feed recovery, member builder; casino retry/navigation callbacks.`);
} finally {
  if (previousLoader) Module._extensions['.jsx'] = previousLoader;
  else delete Module._extensions['.jsx'];
}
