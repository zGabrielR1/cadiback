import { test } from 'node:test';
import assert from 'node:assert/strict';
import { marketCategories, marketLabel, filterMatchMarkets } from './market-discovery.mjs';
const markets = [
  {kind:'moneyline', selections:['Casa','Fora'], prices:[2,3], pricing:'market'},
  {kind:'total',line:2.5,selections:['Mais','Menos'],prices:[1.8,2.1]},
  {kind:'cards',line:4.5,selections:['Mais','Menos'],prices:[1.9,2]},
  {kind:'scorer-h',selections:['Éder'],prices:[3]},
  {kind:'future-kind',selections:['Opção'],prices:[2]},
];
test('categories retain all supplied market kinds, including unknown kinds',()=>{
  const categories=marketCategories(markets);
  assert.equal(categories[0].count,5);
  assert.equal(categories.slice(1).reduce((n,c)=>n+c.count,0),5);
  assert.equal(categories.find(c=>c.id==='other').count,1);
  assert.deepEqual(filterMatchMarkets(markets,{category:'other'}),[markets[4]]);
  assert.equal(markets.length,5);
});
test('market search combines category, accent-insensitive terms, decimal lines and source',()=>{
  assert.deepEqual(filterMatchMarkets(markets,{sport:'soccer',query:'gols 2,5 mais'}),[markets[1]]);
  assert.deepEqual(filterMatchMarkets(markets,{query:'eder'}),[markets[3]]);
  assert.deepEqual(filterMatchMarkets(markets,{query:'cartoes',category:'result'}),[]);
  assert.deepEqual(filterMatchMarkets(markets,{query:'provedor vencedor'}),[markets[0]]);
  assert.deepEqual(filterMatchMarkets(markets,{query:'future-kind'}),[markets[4]]);
});
test('selected markets require the exact fixture, market, line and outcome identity',()=>{
  const selectedBets=[{fixtureKey:'one',marketKind:'total',line:2.5,selection:'Mais',price:1.6}];
  assert.deepEqual(filterMatchMarkets(markets,{fixtureKey:'one',selectedBets,selectedOnly:true}),[markets[1]]);
  assert.deepEqual(filterMatchMarkets(markets,{fixtureKey:'two',selectedBets,selectedOnly:true}),[]);
  assert.deepEqual(filterMatchMarkets(markets,{fixtureKey:'one',selectedBets:[{...selectedBets[0],line:3.5}],selectedOnly:true}),[]);
  assert.deepEqual(filterMatchMarkets(markets,{fixtureKey:'one',selectedBets:[{...selectedBets[0],selection:'Gone'}],selectedOnly:true}),[]);
  assert.equal(selectedBets[0].price,1.6);
});
test('labels follow sport totals without inventing football markets for other sports',()=>{
  assert.equal(marketLabel('total','basketball'),'Total de pontos');
  assert.match(marketLabel('total-h1','basketball'),/pontos.*período/);
  assert.match(marketLabel('total-h1','soccer'),/gols.*tempo/);
  assert.match(marketLabel('total','tennis'),/games/);
});
