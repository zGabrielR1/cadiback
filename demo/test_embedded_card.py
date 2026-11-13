import copy
import json
import os
import threading
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from demo import embedded_card as card
from demo.payments import PaymentError


class Store:
    def __init__(self, value): self.value = copy.deepcopy(value)
    def read_all(self): return copy.deepcopy(self.value)
    def write_all(self, value): self.value = copy.deepcopy(value)


class EmbeddedCardTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, MERCADOPAGO_ACCESS_TOKEN="server-secret", MERCADOPAGO_PUBLIC_KEY="public-key")
        self.env.start()
        self.addCleanup(self.env.stop)
        self.demo = SimpleNamespace(players=Store({'p': {}}), card_charges=Store({}),
            books=SimpleNamespace(lock=threading.RLock()), exclusions=SimpleNamespace(assert_playable=Mock()), limits=Mock(),
            _minor=lambda n: n, _assert_player_limits=Mock(), _deposited_today=lambda p: 0)
        self.payload = dict(player='p', amount_minor=1000, deposit_id='embedded-test')
        card.create(self.demo, self.payload)
        self.identity = 'p:embedded-test'
        self.row = self.demo.card_charges.read_all()[self.identity]
        self.form = dict(token='tokenized-card-value', payment_method_id='visa', installments=1,
                         payment_method_option_id=None, processing_mode='aggregator', issuer_id='',
                         payer={'email':'ana@example.com','identification':{'type':'CPF','number':'52998224725'}},
                         transaction_amount=999)
        self.payment = dict(id=1234, status='approved', transaction_amount=10, currency_id='BRL',
            live_mode=True, external_reference=self.row['reference'],
            metadata={'operator_deposit':self.row['reference']}, payment_type_id='credit_card')

    def submit(self):
        return card.submit(self.demo, {**self.payload, 'form_data':self.form})

    def test_preparation_never_calls_provider_or_exposes_secret(self):
        with patch('demo.card_checkout.request') as request:
            result = card.create(self.demo, self.payload)
        request.assert_not_called()
        self.assertEqual(result['status'], 'prepared')
        self.assertEqual(result['public_key'], 'public-key')
        self.assertNotIn('server-secret', json.dumps(result))
        self.assertNotIn('checkout_url', result)

    def test_server_amount_provider_idempotency_and_single_credit(self):
        with patch('demo.card_checkout.request', side_effect=[
                [{'id':'visa','payment_type_id':'credit_card'}], self.payment]) as request, \
                patch('demo.embedded_card.process_deposit') as credit:
            result = self.submit()
            self.assertEqual(result['status'], 'paid')
            body = request.call_args.args[1]
            self.assertEqual(body['transaction_amount'], 10)
            self.assertEqual(body['three_d_secure_mode'], 'optional')
            self.assertEqual(request.call_args.kwargs['idempotency_key'], self.row['reference'])
            self.assertEqual(self.submit()['status'], 'paid')
            self.assertEqual(credit.call_count, 1)
        stored = json.dumps(self.demo.card_charges.read_all())
        self.assertNotIn(self.form['token'], stored)
        self.assertNotIn('ana@example.com', stored)
        self.assertNotIn('52998224725', stored)

    def test_timeout_exact_retry_keeps_key_and_new_token_is_refused(self):
        with patch('demo.card_checkout.request', side_effect=[
                [{'id':'visa','payment_type_id':'credit_card'}], PaymentError('timeout')]), self.assertRaises(PaymentError):
            self.submit()
        self.assertEqual(self.demo.card_charges.read_all()[self.identity]['status'], 'submitting')
        self.form['token'] = 'another-card-token'
        with patch('demo.card_checkout.request') as request, self.assertRaises(PaymentError):
            self.submit()
        request.assert_not_called()
        self.form['token'] = 'tokenized-card-value'
        with patch('demo.card_checkout.request', side_effect=[
                [{'id':'visa','payment_type_id':'credit_card'}], self.payment]) as request, patch('demo.embedded_card.process_deposit'):
            self.assertEqual(self.submit()['status'], 'paid')
            self.assertEqual(request.call_args.kwargs['idempotency_key'], self.row['reference'])

    def test_raw_fields_noncard_and_multiple_installments_refused(self):
        for changes in ({'card_number':'4111111111111111'}, {'security_code':'123'}, {'installments':2}, {'token':'short'}):
            with self.subTest(changes=changes), self.assertRaises(PaymentError):
                card.payment_body({**self.form,**changes},self.row)
        with patch('demo.card_checkout.request', return_value=[{'id':'visa','payment_type_id':'bank_transfer'}]) as request, self.assertRaises(PaymentError):
            self.submit()
        self.assertEqual(request.call_count,1)

    def test_mismatches_never_credit_or_acknowledge(self):
        for change in ({'transaction_amount':9}, {'transaction_amount':'NaN'}, {'live_mode':False},
                       {'currency_id':'USD'}, {'external_reference':'other'}, {'metadata':{}},
                       {'payment_type_id':'account_money'}, {'id':'../other'}):
            with self.subTest(change=change), patch('demo.embedded_card.process_deposit') as credit, self.assertRaises(PaymentError):
                card.reconcile(self.demo,self.identity,{**self.payment,**change})
            credit.assert_not_called()
            self.assertEqual(self.demo.card_charges.read_all()[self.identity]['status'],'prepared')

    def test_declines_and_three_ds_never_credit(self):
        for state in ('rejected','pending','in_process'):
            payment = {**self.payment,'status':state,'status_detail':'pending_challenge',
                       'three_ds_info':{'external_resource_url':'https://issuer.example/challenge','creq':'challenge-request'}}
            with patch('demo.embedded_card.process_deposit') as credit:
                result = card.reconcile(self.demo,self.identity,payment)
            credit.assert_not_called()
            self.assertEqual('three_ds_info' in result,state == 'pending')

    def test_foreign_player_test_accounts_and_conflicting_amount_refused(self):
        with self.assertRaises(PaymentError): card.status(self.demo,{**self.payload,'player':'other'})
        with self.assertRaises(PaymentError): card.create(self.demo,{**self.payload,'amount_minor':2000})
        self.demo.players.write_all({'p':{'is_test':True}})
        with self.assertRaises(PaymentError): self.submit()

    def test_recovery_search_fetches_and_validates_before_credit(self):
        rows=self.demo.card_charges.read_all();rows[self.identity]['status']='submitting';self.demo.card_charges.write_all(rows)
        with patch('demo.card_checkout.request',side_effect=[{'results':[{'id':1234}]},self.payment]) as request, patch('demo.embedded_card.process_deposit') as credit:
            self.assertEqual(card.status(self.demo,self.payload)['status'],'paid')
        self.assertEqual(request.call_count,2)
        credit.assert_called_once()

    def test_legacy_checkout_can_still_be_confirmed(self):
        rows=self.demo.card_charges.read_all();rows[self.identity].pop('checkout_mode');self.demo.card_charges.write_all(rows)
        with patch('demo.card_checkout.status',return_value={'status':'paid'}) as legacy:
            self.assertEqual(card.status(self.demo,self.payload)['status'],'paid')
        legacy.assert_called_once()


class EmbeddedCardDatabaseTests(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        from demo.db import make_engine, make_session_factory
        from demo.models import Base, IdentityDocument
        from demo.wallet_store import DatabaseBooks
        from demo.identity_store import IdentityStore
        self.env = patch.dict(os.environ, MERCADOPAGO_ACCESS_TOKEN="secret", MERCADOPAGO_PUBLIC_KEY="public")
        self.env.start(); self.addCleanup(self.env.stop)
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        url = getattr(self, 'database_url', '')
        engine = make_engine(url or 'sqlite:///' + str(Path(temp.name, 'wallet.db')))
        self.addCleanup(engine.dispose)
        if url:
            from sqlalchemy.schema import CreateSchema, DropSchema
            import uuid
            schema = 'operator_card_test_' + uuid.uuid4().hex
            with engine.begin() as db: db.execute(CreateSchema(schema))
            def cleanup_schema():
                with engine.begin() as db: db.execute(DropSchema(schema, cascade=True))
            self.addCleanup(cleanup_schema)
            engine = engine.execution_options(schema_translate_map={None:schema})
        Base.metadata.create_all(engine, tables=[IdentityDocument.__table__])
        factory = make_session_factory(engine)
        self.factory = factory
        def worker(name):
            return SimpleNamespace(players=Store({'p':{}}),
                card_charges=IdentityStore(factory,'card_charges',''),
                books=DatabaseBooks(factory,str(Path(temp.name,name,'books.jsonl'))),
                exclusions=SimpleNamespace(assert_playable=Mock()),
                limits=SimpleNamespace(breached=lambda **kw:[]), _minor=lambda n:n,
                _assert_player_limits=Mock(), _deposited_today=lambda p:0)
        self.first,self.second = worker('a'),worker('b')
        self.payload = dict(player='p',amount_minor=1000,deposit_id='sql-card-test')
        card.create(self.first,self.payload)
        row=self.first.card_charges.read_all()['p:sql-card-test']
        self.payment=dict(id=5678,status='approved',transaction_amount=10,currency_id='BRL',live_mode=True,
            external_reference=row['reference'],metadata={'operator_deposit':row['reference']},payment_type_id='debit_card')

    def test_workers_confirm_once_and_keep_shared_receipt(self):
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda worker:card.reconcile(worker,'p:sql-card-test',self.payment),[self.first,self.second]))
        self.assertEqual([r['status'] for r in results],['paid','paid'])
        self.assertEqual(self.second.books.available('p'),1000)
        self.assertEqual(len(self.second.books.postings),1)

    def test_acknowledgement_failure_rolls_back_wallet_and_retry_recovers(self):
        write=self.first.card_charges.write_all
        def fail_after_flush(rows):
            write(rows)
            raise RuntimeError('injected receipt failure')
        with patch.object(self.first.card_charges,'write_all',side_effect=fail_after_flush),self.assertRaises(RuntimeError):
            card.reconcile(self.first,'p:sql-card-test',self.payment)
        self.assertEqual(self.second.books.available('p'),0)
        self.assertEqual(self.second.card_charges.read_all()['p:sql-card-test']['status'],'prepared')
        self.assertEqual(card.reconcile(self.second,'p:sql-card-test',self.payment)['status'],'paid')
        self.assertEqual(self.first.books.available('p'),1000)


@unittest.skipUnless(os.environ.get('OPERATOR_TEST_DATABASE_URL'),'isolated Postgres required')
class EmbeddedCardPostgresTests(EmbeddedCardDatabaseTests):
    database_url = os.environ.get('OPERATOR_TEST_DATABASE_URL','')
