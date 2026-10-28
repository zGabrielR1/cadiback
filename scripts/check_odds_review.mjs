// All account, quote and bet responses are intercepted controlled fixtures.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH || undefined,args:['--no-sandbox']});
const origin=process.env.OPERATOR_QA_URL || 'http://127.0.0.1:8784';
const base={sport:'soccer',country:'Brasil',competition:'Liga de teste',kickoff:'2026-10-27T20:00:00Z',status:'SCHEDULED'};
let checks=0;
await fs.mkdir('/tmp/operator-odds-review-qa',{recursive:true});
for(const width of [1440,768,390,320]) {
 const ctx=await browser.newContext({viewport:{width,height:900}});
 await ctx.addInitScript(()=>localStorage.setItem('casa-player',JSON.stringify({player_id:'qa-player',token:'qa-only'})));
 const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.clock.install({time:new Date('2026-10-26T18:00:00Z')});
 let phase='initial',quoteCount=0,betCount=0;
 const prices=()=>phase==='changed'?[2.4,2.8]:phase==='server'?[1.8,3.2]:phase==='mixed'?[1.8,2.6]:phase==='recovered'?[2.8,3.2]:[2,3];
 const fixtures=()=>['one','two'].map((key,i)=>({...base,key,home:i?'Cruzeiro':'São Paulo',away:i?'Atlético':'Santos',status:phase==='all-unavailable'||(phase==='mixed'&&i===0)?'SUSPENDED':'SCHEDULED',markets:[{kind:'moneyline',selections:['Casa','Fora'],prices:[prices()[i],4],pricing:'market'}]}));
 await ctx.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/api/sports') return phase==='error'?route.fulfill({status:503,json:{error:'unavailable'}}):route.fulfill({json:{source:'Controlled QA',fixtures:fixtures()}});
  if(path==='/api/sports/quote') {
   quoteCount++;
   const legs=route.request().postDataJSON().legs.map((leg,i)=>({...leg,price:i?3.2:1.8,home:i?'Cruzeiro':'São Paulo',away:i?'Atlético':'Santos',competition:'Liga de teste'}));
   phase='server';return route.fulfill({json:{legs}});
  }
  if(path==='/api/bet') {
   betCount++;const body=route.request().postDataJSON();
   assert.deepEqual(body.legs.map(leg=>leg.price),[1.8,3.2]);
   return route.fulfill({json:{round_id:'qa-only-receipt',stake_minor:body.stake_minor,price:5.76}});
  }
  return route.fulfill({json:path==='/api/player'?{player_id:'qa-player',name:'QA Player',available_minor:10000,bonus_minor:0}:path==='/api/history'?{bets:[],rounds:[],ledger:[]}:path==='/api/catalog'?{games:[],provider_demos:[]}:{}});
 });
 const slip=page.locator('.betslip-tray');
 const pick=async count=>{
  await page.locator('.sx-row .sx-odd').first().waitFor();
  for(let i=0;i<count;i++) await page.locator('.sx-row').nth(i).locator('.sx-odd').first().click();
  const toggle=slip.locator('.betslip-toggle');
  if(await toggle.getAttribute('aria-expanded')==='false') await toggle.click();
 };
 const poll=async()=>{await page.clock.fastForward(15001);};
 await page.goto(origin);await pick(2);
 assert.equal(await slip.locator('.betslip-match').count(),2);checks++;
 phase='changed';await poll();await slip.locator('.betslip-price-review').waitFor();
 assert.equal(await slip.locator('.betslip-price.is-changing').count(),2);checks++;
 assert.match(await slip.locator('.betslip-price-review dl').innerText(),/6\.00.*6\.72/s);checks++;
 assert.match(await slip.locator('.betslip-price-review dl').innerText(),/60,00.*67,20/s);checks++;
 assert.equal(quoteCount+betCount,0);checks++;
 await slip.getByRole('button',{name:'Revisar cotações atualizadas',exact:true}).click();
 assert.equal(await page.evaluate(()=>document.activeElement.id),'betslip-price-review-title');checks++;
 const reviewPosition=await page.evaluate(()=>{
  const body=document.querySelector('.betslip-body').getBoundingClientRect();
  const heading=document.getElementById('betslip-price-review-title').getBoundingClientRect();
  return {top:heading.top-body.top,height:body.height};
 });
 assert(reviewPosition.top>=0 && reviewPosition.top<50);checks++;
 await page.screenshot({path:`/tmp/operator-odds-review-qa/${width}-light.png`,fullPage:false,animations:'disabled'});
 await page.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));
 await page.clock.runFor(200);

 await page.screenshot({path:`/tmp/operator-odds-review-qa/${width}-dark.png`,fullPage:false,animations:'disabled'});
 await slip.getByRole('button',{name:'Aceitar cotações atualizadas',exact:true}).click();
 assert.equal(await slip.locator('.betslip-price-review').count(),0);checks++;
 assert.deepEqual(await slip.locator('.betslip-match .betslip-price').allTextContents(),['2.40','2.80']);checks++;
 assert.equal(await slip.locator('#betslip-stake').inputValue(),'10');checks++;
 assert.equal(quoteCount+betCount,0);checks++;
 await slip.getByRole('button',{name:'Confirmar aposta demo',exact:true}).click();
 await slip.getByRole('button',{name:'Aceitar novas cotações',exact:true}).waitFor();
 assert.equal(quoteCount,1);assert.equal(betCount,0);checks++;
 await slip.getByRole('button',{name:'Aceitar novas cotações',exact:true}).click();
 await slip.getByRole('button',{name:'Confirmar aposta demo',exact:true}).waitFor();
 assert.equal(betCount,0);checks++;
 await slip.getByRole('button',{name:'Confirmar aposta demo',exact:true}).click();
 await page.getByRole('region',{name:'Comprovante de aposta'}).waitFor();
 assert.equal(betCount,1);checks++;
 await slip.getByRole('button',{name:'Continuar nas partidas'}).click();
 await pick(2);
 phase='mixed';await poll();await slip.getByRole('heading',{name:'Mercados indisponíveis',exact:true}).waitFor();
 assert.equal(await slip.locator('.betslip-price-review dl').count(),0);checks++;
 await slip.getByRole('button',{name:'Revisar seleções indisponíveis',exact:true}).click();
 assert.equal(await page.evaluate(()=>document.activeElement.id),'betslip-unavailable-title');checks++;
 await slip.getByRole('button',{name:'Remover seleções indisponíveis',exact:true}).click();
 assert.equal(await slip.locator('.betslip-match').count(),1);checks++;
 assert.match(await slip.locator('.betslip-match').innerText(),/Cruzeiro/);checks++;
 await slip.getByRole('button',{name:'Aceitar cotações atualizadas',exact:true}).click();
 assert.equal(await slip.locator('.betslip-price').innerText(),'2.60');checks++;
 assert.equal(betCount,1);checks++;
 phase='all-unavailable';await poll();await slip.getByRole('button',{name:'Remover seleções indisponíveis',exact:true}).click();
 assert.equal(await slip.count(),0);checks++;
 phase='initial';await page.reload();await pick(1);
 phase='changed';await poll();await slip.locator('.betslip-price-review').waitFor();
 phase='error';await poll();await slip.getByRole('button',{name:'Atualizar partidas',exact:true}).waitFor();
 assert(await slip.getByRole('button',{name:'Aceitar cotações atualizadas',exact:true}).isDisabled());checks++;
 phase='recovered';await slip.getByRole('button',{name:'Atualizar partidas',exact:true}).click();
 await slip.getByRole('button',{name:'Aceitar cotações atualizadas',exact:true}).click();
 assert.equal(await slip.locator('.betslip-price').innerText(),'2.80');checks++;
 assert.equal(betCount,1);checks++;
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));checks++;
 assert.deepEqual(errors,[]);checks++;
 await ctx.close();
}
await browser.close();console.log(`${checks} controlled odds-review browser checks passed at 1440/768/390/320, including mocked server rechecks and receipts.`);
