// Supply PLAYWRIGHT_MODULE when Playwright is installed outside this project.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH || undefined,args:['--no-sandbox']});
const origin=process.env.OPERATOR_QA_URL || 'http://127.0.0.1:8784';
const fixture={key:'qa:São Paulo/away&1',sport:'soccer',home:'São Paulo',away:'Santos',competition:'Liga de teste',country:'Brasil',kickoff:'2026-10-27T20:00:00Z',status:'SCHEDULED',markets:[{kind:'1x2',selections:['home','draw','away'],prices:[2,3,4],pricing:'market'}]};
let checks=0;
await fs.mkdir('/tmp/operator-match-qa',{recursive:true});
for (const width of [1440,768,390,320]) {
 const ctx=await browser.newContext({viewport:{width,height:900},permissions:['clipboard-read','clipboard-write']});
 const page=await ctx.newPage(); const errors=[]; page.on('pageerror', e=>errors.push(e.message));
 let mode='normal'; let release;
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/api/sports') {
   if(mode==='delay') await new Promise(r=>release=r);
   if(mode==='error') return route.fulfill({status:503,json:{error:'unavailable'}});
   return route.fulfill({json:{source:'Controlled QA',fixtures:mode==='missing'?[]:[fixture]}});
  }
  return route.fulfill({json:path.endsWith('/providers')?{providers:[],enabled:false}:{}});
 });
 const detail=page.locator('#market-detail-title');
 await page.goto(origin);
 await page.locator('.sx-build').first().click();
 await detail.waitFor();
 assert.equal(new URL(page.url()).searchParams.get('match'),fixture.key); checks++;
 await page.getByRole('button',{name:'Copiar link da partida'}).click();
 await page.getByText('Link copiado.',{exact:true}).waitFor();
 const clipboard=await page.evaluate(()=>navigator.clipboard.readText());
 assert.equal(new URL(clipboard).searchParams.get('match'),fixture.key); checks++;
 await page.reload(); await detail.waitFor();
 await page.getByRole('button',{name:'Copiar link da partida'}).waitFor();
 assert.equal(await detail.innerText(),'São Paulo × Santos'); checks++;
 await page.getByRole('button',{name:'Voltar aos mercados'}).click();
 await page.locator('.sx-build').first().waitFor();
 assert.equal(new URL(page.url()).searchParams.get('match'),null); checks++;
 await page.goBack(); await detail.waitFor(); checks++;
 await page.goForward(); await page.locator('.sx-build').first().waitFor(); checks++;
 await page.locator('.sx-build').first().click(); await detail.waitFor();
 await page.goBack(); await page.locator('.sx-build').first().waitFor();
 assert.equal(await page.evaluate(()=>document.activeElement?.dataset.detailKey),fixture.key); checks++;
 mode='delay'; await page.goto(clipboard);
 await page.getByText('Buscando a partida…',{exact:true}).waitFor();
 assert.equal(await page.getByText('Esta partida saiu do feed',{exact:true}).count(),0); checks++;
 release(); await page.getByRole('button',{name:'Copiar link da partida'}).waitFor();
 await page.evaluate(()=>{Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>Promise.reject(new Error('denied'))}})});
 await page.getByRole('button',{name:'Copiar link da partida'}).click();
 await page.getByLabel('Link da partida').waitFor();
 assert.equal(await page.getByLabel('Link da partida').inputValue(),clipboard); checks++;
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)); checks++;
 await page.screenshot({path:`/tmp/operator-match-qa/${width}.png`,fullPage:true});
 mode='missing'; await page.reload(); await page.getByText('Esta partida saiu do feed',{exact:true}).waitFor(); checks++;
 mode='error'; await page.reload(); await page.getByText('Não foi possível carregar a partida',{exact:true}).waitFor();
 mode='normal'; await page.getByRole('button',{name:'Tentar novamente'}).click();
 await page.getByRole('button',{name:'Copiar link da partida'}).waitFor(); checks++;
 assert.deepEqual(errors,[]); checks++;
 await ctx.close();
}
// Authenticated interactions use controlled session/API fixtures only.
for (const width of [1440,390]) {
 const ctx=await browser.newContext({viewport:{width,height:900}});
 await ctx.addInitScript(()=>{
   localStorage.setItem('casa-player',JSON.stringify({player_id:'qa-player',token:'qa-only'}));
   localStorage.setItem('casa-theme','dark');
 });
 const page=await ctx.newPage();
 const errors=[]; page.on('pageerror', e=>errors.push(e.message));
 await page.route('**/api/**', route=>{
   const path=new URL(route.request().url()).pathname;
   const data=path==='/api/sports'?{source:'Controlled QA',fixtures:[fixture]}:
     path==='/api/player'?{player_id:'qa-player',name:'QA Player',available_minor:10000,bonus_minor:0}:
     path==='/api/catalog'?{games:[],provider_demos:[]}:
     path==='/api/history'?{bets:[],rounds:[],ledger:[]}:
     path.endsWith('/providers')?{providers:[],enabled:false}:{};
   return route.fulfill({json:data});
 });
 await page.goto(origin+'/?match='+encodeURIComponent(fixture.key));
 await page.locator('.market-detail-prices button').first().waitFor();
 await page.locator('.market-detail-prices button').first().click();
 assert.equal(await page.locator('.market-detail-prices button').first().getAttribute('aria-pressed'),'true'); checks++;
 await page.getByRole('button',{name:'Voltar aos mercados'}).click();
 await page.locator('.sx-build').first().click();
 assert.equal(await page.locator('.market-detail-prices button').first().getAttribute('aria-pressed'),'true'); checks++;
 await page.getByRole('button',{name:'Análise avançada'}).click();
 assert.equal(new URL(page.url()).searchParams.get('match'),null); checks++;
 await page.goBack(); await page.locator('#market-detail-title').waitFor(); checks++;
 await page.getByRole('button',{name:'Voltar aos mercados'}).click();
 await page.locator('.sx-build').first().waitFor(); checks++;
 assert.equal(await page.locator('html').getAttribute('data-theme'),'dark'); checks++;
 assert.deepEqual(errors,[]); checks++;
 await ctx.close();
}
await browser.close();
console.log(`${checks} browser checks passed across 1440/768/390/320: links, copy/fallback, reload, back/forward, focus, pending/missing/error/retry, overflow, runtime errors.`);
