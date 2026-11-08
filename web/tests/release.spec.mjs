import { test, expect } from '@playwright/test';

const fixture = { key: 'release-match', home: 'Flamengo', away: 'Santos', competition: 'Liga de teste',
  country: 'Brasil', sport: 'soccer', status: 'scheduled', kickoff: '2030-01-01T18:00:00Z',
  markets: [{ kind: '1x2', selections: ['Flamengo','Empate','Santos'], prices: [2,3,4], pricing: 'model' }] };

async function setup(page, { member = false } = {}) {
  let failFeed = false;
  const writes = [];
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  if (member) await page.addInitScript(() => localStorage.setItem('casa-player', JSON.stringify({player_id:'qa-player',token:'qa-token'})));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== 'GET') writes.push(path);
    const responses = {
      '/api/config': { password_reset_enabled: true },
      '/api/betterauth/providers': { enabled:true, providers:[{id:'google',label:'Google'},{id:'facebook',label:'Facebook'},{id:'twitter',label:'X'}] },
      '/api/sports': { source:'Controlled release QA', fixtures:failFeed?[null]:[fixture] },
      '/api/player': {player_id:'qa-player',name:'Ana de teste',available_minor:10000,bonus_minor:0},
      '/api/player/sessions': {sessions:[]},
      '/api/history': {rounds:[{round_id:'test-round',type:'sports',title:'Flamengo x Santos',tier:'pendente',stake_minor:100,payout_minor:0,ts:'2026-11-06T12:00:00Z'}], transactions:[{id:'seed',kind:'deposit',cash_minor:10000,bonus_minor:0,ts:'2026-11-06T12:00:00Z'}]},
      '/api/health': {status:'ok'},
    };
    await route.fulfill({status:path==='/api/betterauth/sign-in/social'?503:200,
      contentType:'application/json',body:JSON.stringify(responses[path] || {})});
  });
  return { writes, errors, failFeed: value => { failFeed = value; } };
}

for (const width of [1440, 1100, 768, 390, 320]) {
  test(`board, filters, social recovery and themes at ${width}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const qa = await setup(page);
    await page.goto('/');
    await expect(page.locator('.sx-row')).toHaveCount(1);
    await page.keyboard.press('Control+k');
    await expect(page.locator('#search')).toBeFocused();
    await page.locator('.blue-extra-filters summary').click();
    await page.keyboard.press('Escape');
    await expect(page.locator('.blue-extra-filters')).not.toHaveAttribute('open', '');
    for (const theme of ['light','dark']) {
      await page.evaluate(t => document.documentElement.dataset.theme = t, theme);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
      await page.screenshot({path:testInfo.outputPath('board-'+theme+'.png'),animations:'disabled'});
    }
    await page.getByRole('button', {name:'Entrar',exact:true}).click();
    await expect(page.getByRole('button', {name:'Continuar com X'})).toBeVisible();
    await page.getByRole('button', {name:'Continuar com X'}).click();
    await expect(page.locator('.auth-modal').getByRole('alert')).toContainText('Tente novamente');
    await expect(page.getByRole('button', {name:'Continuar com X'})).toBeEnabled();
    await page.keyboard.press('Escape');
    expect(qa.writes.every(path => path === '/api/betterauth/sign-in/social' || path === '/api/settle')).toBeTruthy();
    expect(qa.errors).toEqual([]);
  });
}

test('retained feed rejects malformed refresh and recovers', async ({ page }) => {
  const qa = await setup(page);
  await page.goto('/');
  await expect(page.locator('.sx-row')).toHaveCount(1);
  qa.failFeed(true);
  await page.getByRole('button',{name:'Atualizar partidas'}).click();
  await expect(page.getByText('Atualização indisponível',{exact:true})).toBeVisible();
  await expect(page.locator('.sx-row')).toHaveCount(1);
  qa.failFeed(false);
  await page.getByRole('button',{name:'Tentar novamente',exact:true}).click();
  await expect(page.getByText('Atualização indisponível',{exact:true})).toHaveCount(0);
});

for (const width of [1440,768,390,320]) test(`account history filters, wallet activity and CSV at ${width}`, async ({ page }, testInfo) => {
  await page.setViewportSize({width,height:1000});
  await setup(page,{member:true});
  await page.goto('/');
  await page.getByRole('button',{name:'Minha conta',exact:true}).click();
  await page.getByRole('tab',{name:'Histórico',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Movimentações de saldo'})).toBeVisible();
  await page.getByLabel('Buscar no histórico').fill('Flamengo');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({path:testInfo.outputPath('account-history.png'),fullPage:true});
  const download = page.waitForEvent('download');
  await page.getByRole('button',{name:'Baixar CSV'}).click();
  expect((await download).suggestedFilename()).toBe('candibet-historico.csv');
  await page.getByLabel('Resultado',{exact:true}).selectOption('settled');
  await expect(page.getByText('Nenhum registro corresponde aos filtros.')).toBeVisible();
});
