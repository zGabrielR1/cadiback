import {chromium} from '/home/pwdmcl/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs';
const out='/home/pwdmcl/data/ppp/ppp/pentesting/betting/operator/design/auteur/qa/integration';const base=process.env.OPERATOR_QA_URL||'http://127.0.0.1:8765';
const browser=await chromium.launch({executablePath:'/tmp/operator-browsers/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell',headless:true});
const results=[];function check(name,pass){results.push({name,pass});if(!pass)throw Error(name)}
const market={key:'result',kind:'1x2',pricing:'model',selections:['home','draw','away'],prices:[2.1,3.2,3.6]};
const fixtures=[['a','Flamengo','Palmeiras','Brasileirão','soccer','IN_PROGRESS'],['b','Corinthians','Santos','Brasileirão','soccer','SCHEDULED'],['c','São Paulo','Botafogo','Brasileirão','soccer','SCHEDULED'],['d','Cruzeiro','Grêmio','Brasileirão','soccer','SCHEDULED'],['e','Arsenal','Chelsea','Premier League','soccer','IN_PROGRESS'],['f','Lakers','Celtics','NBA','basketball','SCHEDULED']].map(([key,home,away,competition,sport,status])=>({key,home,away,competition,sport,status,country:competition==='Premier League'?'Inglaterra':'Brasil',kickoff:new Date(Date.now()+3600000).toISOString(),home_score:1,away_score:0,markets:[market,{key:'total',kind:'total',line:2.5,pricing:'model',selections:['over','under'],prices:[1.8,2.2]}]}));
const forbidden=/\b(carteira|minha conta|caixa|boletim|aposta[s]?|cassino|depositar|saldo|promoções)\b/i;
try{for(const width of [1440,768,390,320]){
const page=await browser.newPage({viewport:{width,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));let authed=false;
await page.route('**/api/**',r=>{const path=new URL(r.request().url()).pathname;let body=path==='/api/sports'?{source:'qa-fixtures',fixtures}:path==='/api/config'?{test_accounts_enabled:true}:path.includes('providers')?{providers:[]}:path==='/api/player'?{player_id:'qa',name:'Review',available_minor:100000,bonus_minor:0,is_test:true}:path==='/api/history'?{bets:[],deposits:[],withdrawals:[],rounds:[]}:path==='/api/player/sessions'?{sessions:[]}:path==='/api/deposit/limits'?{minimum_minor:500,maximum_minor:100000}:path==='/api/health'?{status:'ok'}:{};return r.fulfill({json:body})});
await page.goto(base);await page.locator('.sx-row').first().waitFor();await page.evaluate(()=>document.fonts.ready);
check(`${width} Auteur active`,await page.locator('html').getAttribute('data-design')==='auteur');
check(`${width} guest no financial/account text`,!forbidden.test(await page.locator('body').innerText()));
check(`${width} no guest slip or wallet`,await page.locator('.betslip-tray,.auteur-slip-empty,.cashier-modal.open').count()===0);
check(`${width} guest fits`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
await page.screenshot({path:`${out}/${width}-guest-light.png`,fullPage:true});
await page.locator('.sx-teams').nth(1).click();check(`${width} context focus changes`,(await page.locator('.auteur-focus').innerText()).includes('Corinthians'));
await page.locator('.sx-more').first().click();check(`${width} expands markets`,await page.locator('.sx-extra').count()===1);
await page.locator('.sx-build').first().click();await page.locator('.market-detail').waitFor();check(`${width} public detail neutral`,!forbidden.test(await page.locator('body').innerText()));await page.screenshot({path:`${out}/${width}-detail.png`,fullPage:true});await page.getByRole('button',{name:/Voltar aos mercados/}).click();
await page.locator('#search').fill('z'.repeat(110));check(`${width} long query wraps`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.getByRole('button',{name:'Limpar filtros e busca',exact:true}).click();
if(width<=760){await page.getByRole('button',{name:'Mais opções'}).click();check(`${width} guest mobile menu neutral`,!forbidden.test(await page.locator('.bottomnav-overflow').innerText()));await page.getByRole('button',{name:'Mais opções'}).click()}
await page.locator('.header-theme').click();check(`${width} dark theme`,await page.locator('html').getAttribute('data-theme')==='dark');await page.screenshot({path:`${out}/${width}-guest-dark.png`,fullPage:true});
await page.locator('.header-account').click();check(`${width} login opens`,await page.locator('input[type=password]').first().isVisible());await page.screenshot({path:`${out}/${width}-login.png`});await page.keyboard.press('Escape');
await page.evaluate(()=>sessionStorage.setItem('casa-player',JSON.stringify({player_id:'qa',token:'qa-test'})));await page.reload();await page.locator('.header-cash').waitFor();check(`${width} authenticated funds controls`,await page.locator('.header-account').getAttribute('aria-label')==='Minha conta');
await page.locator('.sx-row .sx-odd').first().click();check(`${width} authenticated slip`,await page.locator('.betslip-tray').isVisible());await page.screenshot({path:`${out}/${width}-slip.png`});
await page.locator('.header-cash').click();check(`${width} wallet opens`,await page.getByRole('dialog',{name:/Caixa|Depositar|Carteira/i}).count()>0 || await page.locator('.modal.open').count()>0);await page.screenshot({path:`${out}/${width}-wallet.png`});await page.keyboard.press('Escape');
await page.locator('.header-account').click();await page.locator('.account-view').waitFor();await page.screenshot({path:`${out}/${width}-account.png`,fullPage:true});check(`${width} account fits`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
check(`${width} no page errors`,errors.length===0);await page.close();
}}finally{fs.writeFileSync(`${out}/checks.json`,JSON.stringify(results,null,2));await browser.close();console.log(`${results.filter(x=>x.pass).length}/${results.length} checks passed`)}
