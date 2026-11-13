import json
import unittest
from unittest.mock import patch
from decimal import Decimal

from demo.cryptapi import CryptapiClient, CryptapiConfig, CryptoError, verify_signature, webhook


class CryptapiTests(unittest.TestCase):
    def setUp(self):
        self.config = CryptapiConfig({'btc': 'wallet-out'})
        self.client = CryptapiClient(self.config)
        self.row = {'provider_ref': 'deposit1', 'amount_minor': 5000, 'pay_address': 'wallet-in',
                    'pay_currency': 'btc', 'cryptapi': {'callback': 'https://site/callback?nonce=private',
                    'ticker': 'btc', 'destination': 'wallet-out', 'expected_coin': '0.001'}}

    def logs(self, payments):
        return {'address_in': 'wallet-in', 'address_out': 'wallet-out', 'status': 'success',
                'callback_url': self.row['cryptapi']['callback'], 'callbacks': payments}

    def payment(self, txid, value, confirmed=True):
        return {'txid_in': txid, 'txid_out': 'out-' + txid, 'value_coin': value,
                'result': 'sent' if confirmed else 'pending',
                'logs': [{'pending': '0' if confirmed else '1', 'confirmed': 1 if confirmed else 0}]}

    def test_confirmed_distinct_transfers_accumulate_without_replays(self):
        a = self.payment('a', '0.0006')
        with patch.object(self.client, '_call', return_value=self.logs([a, a])):
            self.assertEqual(self.client.get_invoice(self.row).status, 'PENDING')
        with patch.object(self.client, '_call', return_value=self.logs([a, self.payment('b', '0.0004')])):
            self.assertEqual(self.client.get_invoice(self.row).status, 'PAID')

    def test_pending_transfers_never_credit(self):
        with patch.object(self.client, '_call', return_value=self.logs([self.payment('a', '10', False)])):
            self.assertEqual(self.client.get_invoice(self.row).status, 'PENDING')

    def test_address_and_callback_mismatches_refused(self):
        for field in ('address_in', 'address_out', 'callback_url'):
            response = self.logs([self.payment('a', '1')])
            response[field] = 'wrong'
            with self.subTest(field=field), patch.object(self.client, '_call', return_value=response), self.assertRaises(CryptoError):
                self.client.get_invoice(self.row)

    def test_invalid_numeric_values_refused(self):
        for value in ('NaN', 'Infinity', '-1', '0'):
            with self.subTest(value=value), patch.object(self.client, '_call', return_value=self.logs([self.payment('a', value)])), self.assertRaises(CryptoError):
                self.client.get_invoice(self.row)

    def test_only_configured_networks_are_offered(self):
        self.assertEqual([x['code'] for x in self.client.coins()], ['btc'])
        self.assertFalse(CryptapiConfig.from_env({}).configured)

    def test_receiving_addresses_wait_for_domain_verification_configuration(self):
        values = {'CRYPTAPI_WALLET_BTC': 'wallet-out'}
        self.assertFalse(CryptapiConfig.from_env(values).configured)
        values['CRYPTAPI_VERIFICATION_TOKEN'] = 'cryptapi-verification=challenge'
        self.assertTrue(CryptapiConfig.from_env(values).configured)

    def test_browser_view_keeps_exact_amount_and_hides_callback_secrets(self):
        from types import SimpleNamespace
        from demo.server import Demo
        demo = SimpleNamespace(crypto_env_name=lambda: 'production', books=SimpleNamespace(available=lambda player: 0))
        row = {**self.row, 'provider': 'cryptapi', 'player': 'p',
               'cryptapi': {**self.row['cryptapi'], 'expected_coin': '0.123456789012345678',
                            'nonce': 'private-nonce', 'minimum_coin': '0.0001'}}
        result = Demo._crypto_view(demo, 'deposit1', row)
        self.assertEqual(result['pay_amount'], '0.123456789012345678')
        self.assertNotIn('private-nonce', json.dumps(result))
        self.assertNotIn('callback', json.dumps(result))

    def test_minimum_rounds_up_to_whole_centavos(self):
        with patch.object(self.client, '_call', return_value={'minimum_transaction_coin': '0.0001', 'prices': {'BRL': '100001'}}):
            self.assertEqual(self.client.minimum_payment('btc')['min_minor'], 1001)

    def test_creation_keeps_nonce_private_and_rounds_token_units_up(self):
        client = CryptapiClient(CryptapiConfig({'usdttrc20': 'tron-wallet'}))
        def answer(ticker, endpoint, params=None):
            if endpoint == 'info': return {'minimum_transaction_coin':'1', 'prices': {'BRL':'5'}}
            if endpoint == 'convert': return {'value_coin':'1.23456701'}
            return {'address_in':'in', 'address_out':'tron-wallet', 'callback_url':params['callback'], 'minimum_transaction_coin':'1'}
        with patch.object(client, '_call', side_effect=answer):
            charge = client.create_payment(txid='order', amount_cents=1000, pay_currency='usdttrc20')
        self.assertEqual(charge.private['expected_coin'], '1.234568')
        self.assertNotIn(charge.private['nonce'], charge.provider_ref)

    def test_signatures_verify_exact_raw_body(self):
        import base64
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes, serialization
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        signature = base64.b64encode(key.sign(b'body', padding.PKCS1v15(), hashes.SHA256())).decode()
        with patch('demo.cryptapi.PUBLIC_KEY', public):
            self.assertTrue(verify_signature(b'body', signature))
            self.assertFalse(verify_signature(b'other body', signature))
            self.assertFalse(verify_signature(b'body', 'invalid'))

    def test_callback_requires_signature_and_original_nonce(self):
        from unittest.mock import Mock
        demo = Mock()
        demo._get_crypto_charge.return_value = {'player': 'p', 'cryptapi': {'nonce': 'original'}}
        with patch('demo.cryptapi.verify_signature', return_value=False), self.assertRaises(PermissionError):
            webhook(demo, b'body', 'bad', {'deposit_id': 'd', 'nonce': 'original'})
        demo._get_crypto_charge.assert_not_called()
        with patch('demo.cryptapi.verify_signature', return_value=True):
            with self.assertRaises(PermissionError):
                webhook(demo, b'body', 'signature', {'deposit_id': 'd', 'nonce': 'other'})
            demo.crypto_deposit_status.assert_not_called()
            webhook(demo, b'body', 'signature', {'deposit_id': 'd', 'nonce': 'original'})
            demo.crypto_deposit_status.assert_called_once_with({'player': 'p', 'deposit_id': 'd'})
