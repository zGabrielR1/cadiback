// Controlled local APIs: no live account, quote, bet or payment operations.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || undefined, args: ['--no-sandbox'] });
const origin = process.env.OPERATOR_QA_URL || 'http://127.0.0.1:8784';
const output = '/tmp/operator-availability-qa';
await fs.mkdir(output, { recursive: true });
let checks = 0;
try {
  for (const width of [1440, 768, 390, 320]) for (const member of [false, true]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
    if (member) await context.addInitScript(() => localStorage.setItem('casa-player', JSON.stringify({ player_id: 'qa-player', token: 'qa-only' })));
    const page = await context.newPage(); page.setDefaultTimeout(8000);
    await page.clock.install({ time: new Date('2026-10-27T12:00:00Z') });
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    let status = 'STATUS_SCHEDULED', failed = false, writes = 0;
    await context.route('**/api/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (route.request().method() !== 'GET' && path !== '/api/settle') writes++;
      if (path === '/api/sports') return route.fulfill(failed ? { status: 503, json: { error: 'offline' } } : { json: { source: 'Controlled QA', fixtures: [{ key: 'one', home: 'Casa', away: 'Fora', competition: 'Liga teste', country: 'Brasil', sport: 'soccer', kickoff: '2026-11-01T20:00:00Z', status,
        markets: [{ kind: '1x2', selections: ['Casa', 'Empate', 'Fora'], prices: [2, 3, 4], pricing: 'market' }, { kind: 'total', line: 2.5, selections: ['Mais', 'Menos'], prices: [1.8, 2.1], pricing: 'market' }] }] } });
      return route.fulfill({ json: path === '/api/player' ? { player_id: 'qa-player', name: 'QA Player', available_minor: 10000, bonus_minor: 0 } : path === '/api/catalog' ? { games: [], provider_demos: [] } : path === '/api/history' ? { bets: [], rounds: [], ledger: [] } : {} });
    });
    await page.goto(origin);
    const row = page.locator('.sx-row');
    const odds = row.locator('.sx-odds button');
    await odds.first().waitFor();
    await page.waitForFunction(() => document.querySelector('.sx-row .sx-odds button')?.disabled === false);
    if (member) {
      await odds.first().click(); assert.equal(await row.locator('button[aria-pressed=true].sx-odd').count(), 1); checks++;
      const toggle = page.locator('.betslip-toggle[aria-expanded=true]');
      if (await toggle.count()) await toggle.click();
    }
    for (const [next, label] of [['POSTPONED', 'Adiada'], ['CANCELLED', 'Cancelada'], ['SUSPENDED_LIVE', 'Suspensa'], ['ABANDONED_FINAL', 'Abandonada'], ['FINAL', 'ENC']]) {
      status = next;
      await page.clock.fastForward(15001);
      await row.getByText(label, { exact: true }).waitFor();
      assert.equal(await odds.evaluateAll(buttons => buttons.every(button => button.disabled)), true); checks++;
      assert.equal(await page.locator('.market-trend').count(), 0); checks++;
      assert.equal(await page.locator('.auteur-scores button').count(), 0); checks++;
      assert.equal(await row.locator('.sx-build:enabled').count(), 1); checks++;
      await row.getByRole('button', { name: 'Ver detalhes', exact: true }).click();
      await page.locator('#market-detail-title').waitFor();
      assert.equal(await page.locator('.market-detail-prices button:not(:disabled)').count(), 0); checks++;
      assert.equal(await page.getByRole('button', { name: 'Adicionar ao calendário', exact: true }).count(), 0); checks++;
      await page.getByRole('button', { name: 'Salvar partida', exact: true }).press('Enter');
      await page.getByRole('button', { name: 'Remover dos favoritos', exact: true }).press('Enter'); checks++;
      await page.getByRole('button', { name: /Voltar aos mercados/ }).click();
      await row.waitFor();
    }
    status = 'IN_PROGRESS'; await page.clock.fastForward(15001);
    await row.locator('.sx-live').waitFor();
    assert.equal(await odds.first().isDisabled(), false); checks++;
    if (member) { assert.equal(await row.locator('button[aria-pressed=true].sx-odd').count(), 1); checks++; }
    // Feed errors pause both board and featured selection controls.
    failed = true; await page.clock.fastForward(15001);
    await page.getByRole('button', { name: 'Tentar novamente', exact: true }).waitFor();
    assert.equal(await odds.first().isDisabled(), true); checks++;
    assert.equal(await page.locator('.market-trend-odds button:not(:disabled)').count(), 0); checks++;
    failed = false; await page.getByRole('button', { name: 'Tentar novamente', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('.sx-row .sx-odds button')?.disabled === false); checks++;
    if (member) {
      await row.getByRole('button', { name: 'Ver detalhes', exact: true }).click();
      await page.getByRole('button', { name: 'Análise avançada', exact: true }).click();
      const prices = page.locator('.builder-prices button');
      await prices.first().click();
      assert.equal(await prices.evaluateAll(buttons => buttons.filter(button => button.getAttribute('aria-pressed') === 'true').length), 1); checks++;
      status = 'POSTPONED'; await page.clock.fastForward(15001);
      await page.getByText('Partida adiada. Mercados apenas para consulta.', { exact: true }).waitFor();
      assert.equal(await prices.evaluateAll(buttons => buttons.every(button => button.disabled)), true); checks++;
      assert.equal(await page.locator('.draft-single').isDisabled(), true); checks++;
      assert.equal(await prices.evaluateAll(buttons => buttons.filter(button => button.getAttribute('aria-pressed') === 'true').length), 1); checks++;
      status = 'IN_PROGRESS'; await page.clock.fastForward(15001);
      await page.waitForFunction(() => document.querySelector('.builder-prices button')?.disabled === false);
      assert.equal(await page.locator('.draft-single').isDisabled(), false); checks++;
      status = 'SUSPENDED'; await page.clock.fastForward(15001);
      await page.getByText('Partida suspensa. Mercados apenas para consulta.', { exact: true }).waitFor();
      if (width <= 760) await page.getByRole('button', { name: /^Rascunho \(/ }).click();
      await page.getByRole('button', { name: 'Remover Casa', exact: true }).click();
      assert.equal(await page.locator('.draft-single').count(), 0); checks++;
    }
    if (!member) { status = 'ABANDONED'; await page.clock.fastForward(15001); await row.getByText('Abandonada', { exact: true }).waitFor(); }
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    for (const theme of ['light', 'dark']) {
      await page.evaluate(theme => document.documentElement.setAttribute('data-theme', theme), theme);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true); checks++;
      await page.screenshot({ path: `${output}/${width}-${member ? 'member' : 'guest'}-${theme}.png`, animations: 'disabled' });
    }
    assert.equal(writes, 0); checks++;
    assert.deepEqual(errors, []); checks++;
    await context.close();
  }
  console.log(`${checks} controlled match-availability browser checks passed for guests/members at four widths.`);
} finally { await browser.close(); }
