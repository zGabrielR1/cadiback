// Controlled fixture/session responses; no live quote, bet or payment writes.
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH || undefined,args:['--no-sandbox']});
const origin=process.env.OPERATOR_QA_URL || 'http://127.0.0.1:8784';
const market=(kind,line,selections=['Mais','Menos'])=>({kind,line,selections,prices:selections.map((_,i)=>i?2.1:1.8),pricing:'market'});
const markets=[market('moneyline',null,['Casa','Fora']),market('total',2.5),market('total',3.5),market('cards',4.5),market('corners',8.5),market('scorer-h',null,['Éder']),market('special',null,['Especial']),{...market('total',99),prices:[1,2]}];
let checks=0;
await fs.mkdir('/tmp/operator-market-finder-qa',{recursive:true});
for(const width of [1440,768,390,320])for(const member of [false,true]){
 const ctx=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
 if(member)await ctx.addInitScript(()=>localStorage.setItem('casa-player',JSON.stringify({player_id:'qa-player',token:'qa-only'})));
 const page=await ctx.newPage();page.setDefaultTimeout(8000);
 await page.clock.install({time:new Date('2026-10-26T18:00:00Z')});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let phase='normal',writes=0;
 await ctx.route('**/api/**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/api/bet'||path==='/api/sports/quote')writes++;
  if(path==='/api/sports'){
   if(phase==='error')return route.fulfill({status:503,json:{error:'unavailable'}});
   return route.fulfill({json:{source:'Controlled QA',fixtures:[{key:'one',home:'São Paulo',away:'Santos',sport:phase==='basket'?'basketball':'soccer',competition:'Liga de teste',country:'Brasil',status:['SUSPENDED','POSTPONED','CANCELLED','ABANDONED','FINAL'].includes(phase)?phase:'SCHEDULED',kickoff:'2026-10-27T20:00:00Z',markets:phase==='removed'?markets.filter(m=>m.kind!=='moneyline'):phase==='basket'?[market('moneyline',null,['Casa','Fora']),market('total',176.5)]:markets}]}});
  }
  return route.fulfill({json:path==='/api/player'?{player_id:'qa-player',name:'QA Player',available_minor:10000,bonus_minor:0}:path==='/api/catalog'?{games:[],provider_demos:[]}:path==='/api/history'?{bets:[],rounds:[],ledger:[]}:{} });
 });
 const items=page.locator('.market-detail-market');
 const cats=page.getByRole('group',{name:'Categorias de mercado'});
 const search=page.getByRole('searchbox',{name:'Buscar mercados nesta partida'});
 const count=async n=>{if(member)await page.getByRole('button',{name:/^Minhas seleções/}).waitFor();await page.waitForFunction(n=>document.querySelectorAll('.market-detail-market').length===n,n);checks++;};
 const clear=async()=>{await page.getByRole('button',{name:'Ver todos os mercados',exact:true}).click();await page.clock.runFor(32);await page.waitForFunction(()=>document.activeElement?.getAttribute('aria-label')==='Buscar mercados nesta partida');checks++;};
 await page.goto(origin+'/?match=one');await count(7);
 assert.equal(await page.getByRole('button',{name:/^Minhas seleções/}).count(),member?1:0);checks++;
 assert.equal(await page.locator('.market-detail-prices button').count()>0,member);checks++;
 await cats.getByRole('button',{name:/^Totais/}).click();await count(2);
 await search.fill('gols 2,5');await count(1);assert.match(await items.innerText(),/2.5/);checks++;
 assert.equal(await page.locator('#search').inputValue(),'');checks++;
 // Copy the current public filter, then prove a fresh navigation restores it.
 await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async value=>{window.__copiedMatch=value;}}}));
 await page.getByRole('button',{name:'Copiar link da partida',exact:true}).click();
 await page.waitForFunction(()=>!!window.__copiedMatch);
 const shared=await page.evaluate(()=>window.__copiedMatch);
 const sharedUrl=new URL(shared);
 assert.equal(sharedUrl.searchParams.get('marketCategory'),'totals');checks++;
 assert.equal(sharedUrl.searchParams.get('marketSearch'),'gols 2,5');checks++;
 assert.deepEqual([...sharedUrl.searchParams.keys()],['match','marketCategory','marketSearch']);checks++;
 await page.goto(shared);await count(1);
 assert.equal(await search.inputValue(),'gols 2,5');checks++;
 assert.equal(await cats.getByRole('button',{name:/^Totais/}).getAttribute('aria-pressed'),'true');checks++;
 await page.goto(origin+'/?match=one');await count(7);
 await cats.getByRole('button',{name:/^Totais/}).click();await count(2);


 await search.fill('unknown-query'.repeat(20));await count(0);
 if(!await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)){await page.screenshot({path:'/tmp/operator-market-finder-qa/overflow.png',animations:'disabled'});console.log(await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,offenders:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,16).map(e=>({tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right}))})));throw Error('overflow '+width+' member='+member)}checks++;
 await clear();await count(7);
 await cats.getByRole('button',{name:/^Jogadores/}).click();await search.fill('eder');await count(1);
 assert.match(await items.innerText(),/Éder/);checks++;
 await page.getByRole('button',{name:'Limpar filtros de mercado',exact:true}).click();await count(7);
 await cats.getByRole('button',{name:/^Outros/}).click();await count(1);assert.match(await items.innerText(),/special/);checks++;
 await cats.getByRole('button',{name:/^Resultado/}).press('Enter');await count(1);
 phase='removed';await page.clock.fastForward(15001);await count(0);
 const missingCategory=cats.getByRole('button',{name:/^Resultado/});
 assert.equal(await missingCategory.getAttribute('aria-pressed'),'true');checks++;
 assert.match(await missingCategory.innerText(),/0/);checks++;
 await clear();await count(6);
 phase='error';await page.clock.fastForward(15001);await page.getByRole('button',{name:'Tentar novamente',exact:true}).waitFor();
 assert.equal(await items.count(),6);checks++;
 phase='normal';await page.getByRole('button',{name:'Tentar novamente',exact:true}).click();await count(7);
 if(member){
  await items.first().locator('.market-detail-prices button').first().click();
  await page.getByRole('button',{name:/^Minhas seleções/}).click();await count(1);
  assert.equal(await items.locator('button[aria-pressed=true]').count(),1);checks++;
  await cats.getByRole('button',{name:/^Totais/}).click();await count(0);
  await clear();await count(7);
  assert.equal(await page.locator('.market-detail-prices button[aria-pressed=true]').count(),1);checks++;
  await cats.getByRole('button',{name:/^Totais/}).click();
  await items.first().locator('.market-detail-prices button').first().click();
  await page.getByRole('button',{name:/^Minhas seleções/}).click();await count(1);
  assert.match(await items.innerText(),/Total de gols.*2.5/s);checks++;
  assert.equal(await page.locator('.betslip-match').count(),1);checks++;
  for(const status of ['SUSPENDED','POSTPONED','CANCELLED','ABANDONED','FINAL']){
   phase=status;await page.reload();await count(7);
   assert.equal(await page.locator('.market-detail-prices button:not(:disabled)').count(),0);checks++;
  }
  phase='normal';await page.reload();await count(7);
 }
 phase='basket';await page.reload();await count(2);
 await cats.getByRole('button',{name:/^Totais/}).click();await count(1);
 assert.match(await items.innerText(),/Total de pontos.*176.5/s);checks++;
 assert.equal(await cats.getByRole('button',{name:/^Escanteios/}).count(),0);checks++;
 phase='normal';await page.reload();await count(7);
 await cats.getByRole('button',{name:/^Totais/}).click();await count(2);
 await page.locator('.market-finder').evaluate(e=>e.scrollIntoView({block:'start',behavior:'instant'}));
 await page.screenshot({path:`/tmp/operator-market-finder-qa/${width}-${member?'member':'guest'}-light.png`,animations:'disabled'});
 await page.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));
 await page.screenshot({path:`/tmp/operator-market-finder-qa/${width}-${member?'member':'guest'}-dark.png`,animations:'disabled'});
 if(!await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)){await page.screenshot({path:'/tmp/operator-market-finder-qa/overflow.png',animations:'disabled'});console.log(await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,offenders:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,16).map(e=>({tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right}))})));throw Error('overflow '+width+' member='+member)}checks++;
 assert.equal(writes,0);checks++;assert.deepEqual(errors,[]);checks++;
 await ctx.close();
}
await browser.close();console.log(`${checks} controlled market-finder browser checks passed for guests/members at four widths.`);
