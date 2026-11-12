import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from demo.card_checkout import status
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
    def test_mismatch_never_credits(self):
        for changes in ({'transaction_amount':9},{'external_reference':'other-store'},{'live_mode':False},{'currency_id':'USD'},{'payment_type_id':'account_money'}):
            with self.subTest(changes=changes), self.assertRaises(PaymentError): self.check({**self.payment,**changes})
    def test_other_player_cannot_read_charge(self):
        with patch.dict('os.environ', {'MERCADOPAGO_ACCESS_TOKEN':'test'}), self.assertRaises(PaymentError):
            status(self.demo,{'player':'other','deposit_id':'deposit-test'})
