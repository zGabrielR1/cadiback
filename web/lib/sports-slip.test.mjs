import {test} from 'node:test';
import assert from 'node:assert/strict';
import { betIdentity } from './sports.mjs';
import {toggleSelection, toLegs, fromQuote, selectionAvailability, applyPriceChanges} from './sports-slip.mjs';
const bet={fixtureKey:'one',marketKind:'1x2',line:null,selection:'Casa',price:2};
test('one selection per fixture; independent fixtures remain',()=>{
  const other={...bet,fixtureKey:'two'};
  const replacement={...bet,selection:'Fora'};
  assert.deepEqual(toggleSelection([bet,other],replacement),[other,replacement]);
  assert.deepEqual(toggleSelection([bet,other],bet),[other]);
});
test('quotes round trip and changed or missing selections stay explicit',()=>{
  assert.equal(fromQuote({legs:toLegs([bet])})[0].price,2);
  const sports={fixtures:[{key:'one',status:'LIVE',markets:[{kind:'1x2',selections:['Casa'],prices:[2.4]}]}]};
  assert.equal(selectionAvailability([bet],sports).changed[0].price,2.4);
  sports.fixtures[0].status='SUSPENDED';
  assert.equal(selectionAvailability([bet],sports).unavailable.length,1);
  assert.equal(bet.price,2);
});


test('accepting changed prices preserves identities, metadata and unavailable legs',()=>{
  const first={...bet,home:'Home',away:'Away',competition:'League'};
  const second={...bet,fixtureKey:'two',marketKind:'total',line:2.5,price:3};
  const bets=[first,second];
  const sports={fixtures:[{key:'one',status:'LIVE',markets:[{kind:'1x2',selections:['Casa'],prices:[2.4]}]}]};
  const availability=selectionAvailability(bets,sports);
  const accepted=applyPriceChanges(bets,availability.changed);
  assert.equal(accepted[0].price,2.4);
  assert.equal(accepted[0].home,'Home');
  assert.equal(betIdentity(accepted[0]),betIdentity(first));
  assert.equal(accepted[1],second);
  assert.equal(first.price,2);
  assert.equal(selectionAvailability(accepted,sports).changed.length,0);
  assert.deepEqual(selectionAvailability(accepted,sports).unavailable,[betIdentity(second)]);
});

test('price acceptance ignores foreign identities and malformed prices',()=>{
  const result=applyPriceChanges([bet],[
    {id:betIdentity({...bet,line:2.5}),price:7},
    {id:betIdentity({...bet,fixtureKey:'foreign'}),price:9},
    ...[1,0,NaN,Infinity,'2.4'].map(price=>({id:betIdentity(bet),price})),
  ]);
  assert.equal(result[0],bet);
});


test('status transitions pause saved selections without changing their price or identity', () => {
  const fixture = { key: 'one', status: 'LIVE', markets: [{ kind: '1x2', selections: ['Casa'], prices: [2.4] }] };
  for (const status of ['POSTPONED', 'CANCELLED', 'SUSPENDED_LIVE', 'ABANDONED_FINAL', 'FINAL']) {
    fixture.status = status;
    assert.deepEqual(selectionAvailability([bet], { fixtures: [fixture] }), { changed: [], unavailable: [betIdentity(bet)] });
    assert.equal(bet.price, 2);
  }
  fixture.status = 'IN_PROGRESS';
  assert.deepEqual(selectionAvailability([bet], { fixtures: [fixture] }), { changed: [{ id: betIdentity(bet), price: 2.4 }], unavailable: [] });
});
