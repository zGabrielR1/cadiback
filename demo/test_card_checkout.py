import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from demo.card_checkout import status, create
from demo.payments import PaymentError

class Store:
    def __init__(self, value): self.value = value
    def read_all(self): return self.value.copy()
    def write_all(self, value): self.value = value

class CardCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(reference='operator-card-test', amount_minor=1000, player='p', deposit_id='deposit-test', status='pending')
        self.demo = SimpleNamespace(card_charges=Store({'p:deposit-test':self.row}), books=SimpleNamespace(lock=threading.RLock()), exclusions=None, limits=None, _deposited_today=lambda p:0)
        self.payment = dict(id=123, status='approved', external_reference='operator-card-test', currency_id='BRL', live_mode=True, metadata={'operator_deposit':'operator-card-test'}, transaction_amount=10, payment_type_id='credit_card')
    def check(self, payment):
        with patch.dict('os.environ', {'MERCADOPAGO_ACCESS_TOKEN':'test'}), patch('demo.card_checkout.request', side_effect=[{'results':[{'id':123}]},payment]), patch('demo.card_checkout.process_deposit') as credit:
            result=status(self.demo, {'player':'p','deposit_id':'deposit-test'})
            return result,credit.call_count
    def test_verified_payment_credits_once(self):
        result,calls=self.check(self.payment)
        self.assertEqual((result['status'],calls),('paid',1))
        with patch.dict('os.environ', {'MERCADOPAGO_ACCESS_TOKEN':'test'}), patch('demo.card_checkout.request') as request:
            self.assertEqual(status(self.demo,{'player':'p','deposit_id':'deposit-test'})['status'],'paid')
            request.assert_not_called()
    def test_pending_payment_does_not_credit(self):
        result,calls=self.check({**self.payment,'status':'pending'})
        self.assertEqual((result['status'],calls),('pending',0))
    def test_required_account_balance_method_is_verified_and_credited(self):
        result,calls=self.check({**self.payment,'payment_type_id':'account_money'})
        self.assertEqual((result['status'],calls),('paid',1))
    def test_checkout_does_not_exclude_account_balance_and_sets_full_validity_window(self):
        from datetime import datetime, timedelta
        from unittest.mock import Mock
        self.demo.players=Store({'p':{}})
        self.demo.card_charges=Store({})
        self.demo._minor=lambda n:n
        self.demo.exclusions=SimpleNamespace(assert_playable=Mock())
        self.demo._assert_player_limits=Mock()
        with patch('demo.card_checkout.request',return_value={'id':'pref','init_point':'https://www.mercadopago.com.br/checkout/test'}) as provider:
            create(self.demo,{'player':'p','amount_minor':1000,'deposit_id':'new-deposit'})
        body=provider.call_args.args[1]
        self.assertNotIn({'id':'account_money'},body['payment_methods']['excluded_payment_types'])
        self.assertEqual(datetime.fromisoformat(body['expiration_date_to'])-datetime.fromisoformat(body['expiration_date_from']),timedelta(minutes=30))
    def test_mismatch_never_credits(self):
        for changes in ({'transaction_amount':9},{'external_reference':'other-store'},{'live_mode':False},{'currency_id':'USD'},{'payment_type_id':'bank_transfer'},{'metadata':{'operator_deposit':'other-store'}}):
            with self.subTest(changes=changes), patch.dict('os.environ', {'MERCADOPAGO_ACCESS_TOKEN':'test'}), patch('demo.card_checkout.request', side_effect=[{'results':[{'id':123}]},{**self.payment,**changes}]), patch('demo.card_checkout.process_deposit') as credit:
                with self.assertRaises(PaymentError):
                    status(self.demo,{'player':'p','deposit_id':'deposit-test'})
                credit.assert_not_called()
    def test_other_player_cannot_read_charge(self):
        with patch.dict('os.environ', {'MERCADOPAGO_ACCESS_TOKEN':'test'}), self.assertRaises(PaymentError):
            status(self.demo,{'player':'other','deposit_id':'deposit-test'})
