import { test, expect } from '@playwright/test';

async function setup(page, { challenge = false } = {}) {
  const writes = [];
  let status = 'prepared';
  let paymentId;
  const charge = () => ({deposit_id:'embedded-browser-test',amount_minor:1000,status,
    payment_id:paymentId,checkout_mode:'embedded',public_key:'public-test',
    ...(challenge && status === 'pending' ? {three_ds_info:{external_resource_url:'https://issuer.example/challenge',creq:'test-creq'}} : {})});
  await page.addInitScript(() => localStorage.setItem('casa-player',JSON.stringify({player_id:'qa-player',token:'qa-token'})));
  await page.route('https://sdk.mercadopago.com/js/v2', route => route.fulfill({contentType:'text/javascript',body:`
    window.__mpMounts = [];
    window.MercadoPago = class {
      bricks() { return { create: async (type, id, settings) => {
        window.__mpMounts.push({type,settings});
        const root = document.getElementById(id);
        const button = document.createElement('button');
        button.textContent = type === 'cardPayment' ? 'Enviar cartão de teste' : 'Desafio do banco';
        button.onclick = async () => {
          if (type !== 'cardPayment') return;
          await settings.callbacks.onSubmit({token:'browser-token-value',payment_method_id:'visa',installments:1,
            payer:{email:'ana@example.com',identification:{type:'CPF',number:'52998224725'}}});
        };
        root.append(button); settings.callbacks.onReady();
        return {unmount:() => root.replaceChildren()};
      }}; }
    };` }));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== 'GET') writes.push({path,body:route.request().postDataJSON()});
    let body = {};
    if (path === '/api/player') body={player_id:'qa-player',available_minor:status==='paid'?11000:10000,bonus_minor:0,name:'Ana'};
    if (path === '/api/health') body={status:'ok'};
    if (path === '/api/history') body={rounds:[],transactions:[]};
    if (path === '/api/sports') body={fixtures:[]};
    if (path === '/api/deposit/limits') body={method:new URL(route.request().url()).searchParams.get('method'),min_minor:500,currency:'brl',provider:'Mercado Pago'};
    if (path === '/api/deposit/card') body=charge();
    if (path === '/api/deposit/card/pay') { status=challenge?'pending':'paid';paymentId='12345';body=charge(); }
    if (path === '/api/deposit/card/status') body=charge();
    await route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
  });
  return {writes, approve:() => {status='paid';}};
}

async function openCard(page) {
  await page.goto('/');
  await page.locator('.header-cash').click();
  await page.getByLabel('Método de Depósito').selectOption('debit');
  await page.getByLabel('Valor (R$)',{exact:true}).fill('10');
  await page.getByRole('button',{name:'Preencher dados do cartão',exact:true}).click();
  await expect(page.getByRole('button',{name:'Enviar cartão de teste'})).toBeVisible();
}

for (const width of [1440,390]) test(`embedded card submits without leaving cashier at ${width}`,async ({page}) => {
  await page.setViewportSize({width,height:1000});
  const qa=await setup(page);
  await openCard(page);
  await expect(page.getByRole('link',{name:'Abrir checkout seguro'})).toHaveCount(0);
  const url=page.url();
  await page.getByRole('button',{name:'Enviar cartão de teste'}).click();
  await expect(page.getByText('Pagamento confirmado. Saldo atualizado.',{exact:true})).toBeVisible();
  expect(page.url()).toBe(url);
  expect(qa.writes.filter(w=>w.path==='/api/deposit/card/pay')).toHaveLength(1);
  const storage=await page.evaluate(()=>sessionStorage.getItem('operator-card:qa-player'));
  expect(storage).not.toContain('browser-token');
  expect(storage).not.toContain('ana@example.com');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.reload();
  await page.locator('.header-cash').click();
  await expect(page.getByText('Pagamento confirmado. Saldo atualizado.',{exact:true})).toBeVisible();
});

test('bank challenge stays embedded and credits only after server verification',async ({page}) => {
  const qa=await setup(page,{challenge:true});
  await openCard(page);
  await page.getByRole('button',{name:'Enviar cartão de teste'}).click();
  await expect(page.getByRole('button',{name:'Desafio do banco'})).toBeVisible();
  await expect(page.getByText('Pagamento confirmado. Saldo atualizado.',{exact:true})).toHaveCount(0);
  const initialization=await page.evaluate(()=>window.__mpMounts.find(m=>m.type==='statusScreen').settings.initialization);
  expect(initialization).toEqual({paymentId:'12345',additionalInfo:{externalResourceURL:'https://issuer.example/challenge',creq:'test-creq'}});
  qa.approve();
  await page.getByRole('button',{name:'Verificar pagamento',exact:true}).click();
  await expect(page.getByText('Pagamento confirmado. Saldo atualizado.',{exact:true})).toBeVisible();
});
