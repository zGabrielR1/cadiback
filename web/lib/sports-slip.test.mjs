import {test} from 'node:test';
import assert from 'node:assert/strict';
import {toggleSelection, toLegs, fromQuote, selectionAvailability} from './sports-slip.mjs';
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
