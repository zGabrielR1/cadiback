import test from 'node:test';
import assert from 'node:assert/strict';
import { cardSnapshot, cardMessage } from './mercadopago.mjs';

test('recovery storage omits payment tokens, payer and challenge data', () => {
  const stored = cardSnapshot({ deposit_id:'deposit-1',amount_minor:500,status:'pending',checkout_mode:'embedded',
    token:'secret',payer:{email:'private'},public_key:'key',payment_id:'123',three_ds_info:{creq:'sensitive'} });
  assert.deepEqual(stored,{deposit_id:'deposit-1',amount_minor:500,status:'pending',checkout_mode:'embedded'});
});

test('only wallet-confirmed state reports success', () => {
  assert.match(cardMessage('paid'),/Saldo atualizado/);
  for (const status of ['pending','submitting','rejected','cancelled','refunded','charged_back']) {
    assert.doesNotMatch(cardMessage(status),/Saldo atualizado/);
  }
  assert.match(cardMessage('rejected'),/recusado/);
  assert.match(cardMessage('submitting'),/antes de iniciar outro/);
});
