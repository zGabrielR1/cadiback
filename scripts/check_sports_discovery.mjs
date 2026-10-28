// Controlled UI fixtures; no live account or payment operations.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH || undefined,args:['--no-sandbox']});
const origin=process.env.OPERATOR_QA_URL || 'http://127.0.0.1:8784';
const base={country:'Brasil',kickoff:'2026-10-27T20:00:00Z',status:'SCHEDULED',markets:[{kind:'moneyline',selections:['Casa','Fora'],prices:[2,3],pricing:'market'}]};
const fixtures=[
 {...base,key:'soccer',sport:'soccer',home:'São Paulo',away:'Santos',competition:'Liga Nacional',status:'IN_PROGRESS',home_score:1,away_score:0},
 {...base,key:'basket',sport:'basketball',home:'Franca',away:'Bauru',competition:'Liga Nacional'},
 {...base,key:'tennis',sport:'tennis',home:'Beatriz',away:'Ana',competition:'Aberto'},
];
let checks=0;
await fs.mkdir('/tmp/operator-discovery-qa',{recursive:true});
for(const width of [1440,768,390,320]) {
 const ctx=await browser.newContext({viewport:{width,height:900}});
 await ctx.addInitScript(()=>{
  if(!localStorage.getItem('qa-seeded')){
   localStorage.setItem('candi-sport-favorites',JSON.stringify(['basket','tennis','missing']));
   localStorage.setItem('qa-seeded','1');
  }
 });
 await ctx.route('**/api/**',r=>r.fulfill({json:new URL(r.request().url()).pathname==='/api/sports'?{source:'Controlled QA',fixtures}:{}}));
 const page=await ctx.newPage(); const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 const row=page.locator('.sx-row');
 const waitRows=async n=>{await page.waitForFunction(n=>document.querySelectorAll('.sx-row').length===n,n);checks++;};
 const favorites=()=>page.getByRole('navigation',{name:'Navegação principal'}).getByRole('button',{name:'Favoritos',exact:true});
 const sportNav=()=>page.locator(width>1000?'.sport-rail':'.workspace-tabs');
 const query=()=>page.locator('#search');
 await page.goto(origin); await waitRows(1);
 await favorites().click(); await waitRows(2);
 assert.match((await row.allTextContents()).join(' '),/Franca/);checks++;
 await sportNav().getByRole('button',{name:/^Basquete/}).click(); await waitRows(1);
 await page.getByRole('button',{name:'Remover filtro: Basquete',exact:true}).click(); await waitRows(2);
 await page.getByRole('combobox',{name:/Quando/}).selectOption('results');
 await page.getByText('Nenhum favorito corresponde aos filtros.',{exact:true}).waitFor();checks++;
 await page.getByRole('button',{name:'Mostrar todos os favoritos'}).click(); await waitRows(2);
 assert.match(await page.locator('h1').innerText(),/favoritas/);checks++;
 await page.getByRole('button',{name:'Remover favorito: Franca × Bauru',exact:true}).click(); await waitRows(1);
 await page.reload(); await favorites().click(); await waitRows(1);
 assert.match(await row.innerText(),/Beatriz/);checks++;
 const other=await ctx.newPage(); await other.goto(origin);
 await other.evaluate(()=>localStorage.setItem('candi-sport-favorites',JSON.stringify(['soccer'])));
 await page.getByRole('button',{name:'Remover favorito: São Paulo × Santos',exact:true}).waitFor();checks++;
 await other.evaluate(()=>localStorage.setItem('candi-sport-favorites',JSON.stringify(['missing'])));
 await page.getByText('Seus favoritos não estão no calendário atual.',{exact:true}).waitFor();checks++;
 await other.evaluate(()=>localStorage.removeItem('candi-sport-favorites'));
 await page.getByText('Você ainda não salvou partidas.',{exact:true}).waitFor();checks++;
 await page.getByRole('button',{name:'Explorar partidas'}).click(); await waitRows(3);
 assert.equal(await page.locator('.sx-league').count(),3);checks++;
 const soccerGroup=page.locator('.sx-league').filter({hasText:'Futebol · Liga Nacional'});
 await soccerGroup.locator('.sx-league-head').click(); await waitRows(2);
 assert.match((await row.allTextContents()).join(' '),/Franca/);checks++;
 await soccerGroup.locator('.sx-league-head').click(); await waitRows(3);
 await sportNav().getByRole('button',{name:/^Futebol/}).click(); await waitRows(1);
 await query().fill('basquete'); await waitRows(1);
 assert.match(await row.innerText(),/Franca/);checks++;
 await sportNav().getByRole('button',{name:/^Futebol/}).click(); await waitRows(0);
 await page.getByRole('button',{name:'Remover filtro: Futebol',exact:true}).click(); await waitRows(1);
 await page.locator('.sx-build').first().click(); await page.locator('#market-detail-title').waitFor();
 await query().fill('Beatriz'); await waitRows(1);
 assert.equal(new URL(page.url()).searchParams.get('match'),null);checks++;
 assert.match(await row.innerText(),/Beatriz/);checks++;
 await query().fill('verylongsearch'.repeat(20)); await waitRows(0);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));checks++;
 await page.getByRole('button',{name:'Limpar filtros e busca'}).click(); await waitRows(3);
 await sportNav().getByRole('button',{name:'Todos os esportes',exact:true}).click(); await waitRows(3);
 await page.locator('.blue-live-toggle').click(); await waitRows(1);
 await page.getByRole('button',{name:'Limpar tudo',exact:true}).click(); await waitRows(3);
 await page.getByRole('button',{name:'Favoritar: Franca × Bauru',exact:true}).click();
 await page.getByRole('button',{name:'Favoritar: Beatriz × Ana',exact:true}).click();
 await favorites().click(); await waitRows(2);
 await page.screenshot({path:`/tmp/operator-discovery-qa/${width}-light.png`,fullPage:true});
 await page.evaluate(()=>document.documentElement.setAttribute('data-theme','dark'));
 await page.screenshot({path:`/tmp/operator-discovery-qa/${width}-dark.png`,fullPage:true});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));checks++;
 assert.deepEqual(errors,[]);checks++;
 await ctx.close();
}
await browser.close(); console.log(`${checks} controlled discovery browser checks passed at four widths.`);
