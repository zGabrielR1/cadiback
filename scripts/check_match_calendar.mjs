// Local controlled APIs only: exports must never submit a quote, bet or payment.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || undefined, args: ['--no-sandbox'] });
const origin = process.env.OPERATOR_QA_URL || 'http://127.0.0.1:8784';
const output = '/tmp/operator-calendar-qa';
await fs.mkdir(output, { recursive: true });
let checks = 0;
try {
  for (const width of [1440, 768, 390, 320]) for (const member of [false, true]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, timezoneId: 'America/Sao_Paulo', acceptDownloads: true, reducedMotion: 'reduce' });
    if (member) await context.addInitScript(() => localStorage.setItem('casa-player', JSON.stringify({ player_id: 'qa-player', token: 'qa-only' })));
    const page = await context.newPage();
    page.setDefaultTimeout(8000);
    await page.clock.install({ time: new Date('2026-10-27T12:00:00Z') });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let status = 'STATUS_SCHEDULED', kickoff = '2026-11-01T16:30:00-03:00', failed = false, writes = 0;
    const fixture = () => ({ key: 'qa:São Paulo/1', home: 'São Paulo', away: 'Santos', competition: 'Liga teste', country: 'Brasil', sport: 'soccer', status, kickoff,
      markets: [{ kind: 'total', line: 2.5, selections: ['Mais', 'Menos'], prices: [1.8, 2.1], pricing: 'market' }] });
    await context.route('**/api/**', route => {
      const path = new URL(route.request().url()).pathname;
      // The existing member poll calls /api/settle; it is stubbed here too.
      if (route.request().method() !== 'GET' && path !== '/api/settle') writes++;
      if (path === '/api/sports') return route.fulfill(failed ? { status: 503, json: { error: 'offline' } } : { json: { source: 'Controlled QA', fixtures: [fixture()] } });
      return route.fulfill({ json: path === '/api/player' ? { player_id: 'qa-player', name: 'QA Player', available_minor: 10000, bonus_minor: 0 } : path === '/api/catalog' ? { games: [], provider_demos: [] } : path === '/api/history' ? { bets: [], rounds: [], ledger: [] } : {} });
    });
    await page.goto(origin + '/?match=' + encodeURIComponent('qa:São Paulo/1') + '&marketCategory=totals&marketSearch=gols');
    const button = page.getByRole('button', { name: 'Adicionar ao calendário', exact: true });
    await button.waitFor();
    await page.waitForFunction(() => ![...document.querySelectorAll('button')].find(button => button.textContent === 'Adicionar ao calendário')?.disabled);
    assert.equal(await page.locator('.market-detail-calendar time').getAttribute('datetime'), kickoff); checks++;
    assert.match(await page.locator('.market-detail-calendar time').innerText(), /01\/11\/2026.*16:30/); checks++;
    const selected = page.locator('.market-detail-prices button[aria-pressed=true]');
    if (member) { await page.locator('.market-detail-prices button').first().click(); assert.equal(await selected.count(), 1); checks++; }
    await button.focus();
    const pending = page.waitForEvent('download');
    await button.press('Enter');
    const download = await pending;
    const path = `${output}/${width}-${member ? 'member' : 'guest'}.ics`;
    await download.saveAs(path);
    const content = (await fs.readFile(path, 'utf8')).replace(/\r\n /g, '');
    assert.equal(download.suggestedFilename(), 'sao-paulo-santos.ics'); checks++;
    assert.match(content, /DTSTART:20261101T193000Z/); checks++;
    assert.match(content, /SUMMARY:São Paulo × Santos/); checks++;
    const link = new URL(content.match(/^URL:(.+)\r$/m)[1]);
    assert.deepEqual([...link.searchParams], [['match', 'qa:São Paulo/1']]); checks++;
    assert.doesNotMatch(content, /qa-only|marketSearch|marketCategory|DTEND|VALARM/); checks++;
    await page.getByText('Abra o arquivo .ics no seu calendário. Alterações de horário não são sincronizadas.', { exact: true }).waitFor(); checks++;
    assert.equal(await page.getByRole('searchbox', { name: 'Buscar mercados nesta partida' }).inputValue(), 'gols'); checks++;
    if (member) { assert.equal(await selected.count(), 1); checks++; }
    for (const theme of ['light', 'dark']) {
      await page.evaluate(theme => document.documentElement.setAttribute('data-theme', theme), theme);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true); checks++;
      await page.screenshot({ path: `${output}/${width}-${member ? 'member' : 'guest'}-${theme}.png`, animations: 'disabled' });
    }
    // A failed refresh retains the last match but pauses export until recovery.
    failed = true;
    await page.clock.fastForward(15001);
    await page.getByRole('button', { name: 'Tentar novamente', exact: true }).waitFor();
    assert.equal(await button.isDisabled(), true); checks++;
    failed = false;
    await page.getByRole('button', { name: 'Tentar novamente', exact: true }).click();
    await page.waitForFunction(() => ![...document.querySelectorAll('button')].find(button => button.textContent === 'Adicionar ao calendário')?.disabled); checks++;
    // Export uses the current kickoff after a successful feed update.
    kickoff = '2026-11-02T18:00:00Z';
    await page.clock.fastForward(15001);
    await page.getByText('Atualizando dados e cotações…', { exact: true }).waitFor({ state: 'hidden' });
    const updatedDownload = page.waitForEvent('download');
    await button.click();
    const updated = await updatedDownload;
    await updated.saveAs(path);
    const next = (await fs.readFile(path, 'utf8')).replace(/\r\n /g, '');
    assert.match(next, /DTSTART:20261102T180000Z/); checks++;
    assert.equal(next.match(/^UID:.+$/m)[0], content.match(/^UID:.+$/m)[0]); checks++;
    // A browser download preparation failure offers a readable retry message.
    await page.evaluate(() => { URL.createObjectURL = () => { throw new Error('download unavailable'); }; });
    await button.click();
    await page.getByText('Não foi possível preparar o calendário. Atualize os dados e tente novamente.', { exact: true }).waitFor(); checks++;
    for (const unavailable of ['LIVE', 'IN_PROGRESS', 'STATUS_FINAL', 'POSTPONED', 'CANCELLED', 'SUSPENDED', 'ABANDONED', 'UNKNOWN']) {
      status = unavailable;
      await page.reload();
      await page.locator('.market-detail-market').waitFor();
      assert.equal(await button.count(), 0, unavailable); checks++;
    }
    status = 'STATUS_SCHEDULED';
    for (const invalid of ['', 'invalid', '2026-11-01T16:30:00', '2026-10-26T12:00:00Z']) {
      kickoff = invalid;
      await page.reload();
      await page.locator('.market-detail-market').waitFor();
      assert.equal(await button.count(), 0, invalid); checks++;
    }
    assert.equal(writes, 0); checks++;
    assert.deepEqual(errors, []); checks++;
    await context.close();
  }
  console.log(`${checks} controlled match-calendar browser checks passed at four widths for guests/members.`);
} finally { await browser.close(); }
