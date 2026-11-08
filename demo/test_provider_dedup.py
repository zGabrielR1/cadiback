"""Provider request de-duplication: idempotency keys survive retries."""
import tempfile
import unittest
from pathlib import Path

from demo.asaas import AsaasClient, AsaasConfig
from demo.server import Demo


class ProviderDedupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        demo = Demo(data_dir=str(self.dir))
        self.demo = demo
        row = self.demo.register_player({'name': 'Ana Souza', 'username': 'ana.souza',
                                         'email': 'ana.souza@example.com',
                                         'cpf': '529.982.247-25', 'password': 'ana1234',
                                         'pix_key': 'ana.souza@example.com',
                                         'bank': {'bank_code': '001', 'agency': '1234',
                                                  'account': '56789-0', 'holder_name': 'Ana Souza'}},
                                        device=None)
        self.player = row['player_id']
        self.calls = []

    def fake(self, method, url, key, payload, idem, timeout):
        self.calls.append((method, url, idem, payload))
        if url.endswith('/payments'):
            return {'id': 'pay_1', 'status': 'PENDING', 'value': payload['value']}
        return {'payload': 'copia-cola', 'encodedImage': 'aW1n'}

    def test_pix_create_retry_with_same_key_returns_same_charge(self):
        cfg = AsaasConfig(api_key='k', customer_id='1', base_url='https://sandbox.asaas.com/api/v3')
        self.demo.asaas = AsaasClient(cfg, transport=self.fake)
        first = self.demo.create_pix_deposit({'player': self.player, 'amount_minor': 1000,
                                               'idempotency_key': 'web-1'})
        second = self.demo.create_pix_deposit({'player': self.player, 'amount_minor': 1000,
                                                'idempotency_key': 'web-1'})
        self.assertEqual(first['provider_ref'], 'pay_1')
        self.assertEqual(second['deposit_id'], first['deposit_id'])
        creates = [c for c in self.calls if c[0] == 'POST']
        self.assertEqual(len(creates), 1)
        self.assertEqual(creates[0][2], 'dep:' + first['deposit_id'])

    def test_same_key_different_payload_is_refused(self):
        cfg = AsaasConfig(api_key='k', customer_id='1', base_url='https://sandbox.asaas.com/api/v3')
        self.demo.asaas = AsaasClient(cfg, transport=self.fake)
        self.demo.create_pix_deposit({'player': self.player, 'amount_minor': 1000,
                                       'idempotency_key': 'web-2'})
        with self.assertRaises(ValueError):
            self.demo.create_pix_deposit({'player': self.player, 'amount_minor': 2000,
                                           'idempotency_key': 'web-2'})


if __name__ == '__main__':
    unittest.main()
