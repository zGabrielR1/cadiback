"""Durability, rollback, cross-instance spend and backup/restore regressions."""
import concurrent.futures
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import os
import uuid

from demo.db import make_engine, make_session_factory
from demo.models import Base, IdentityDocument
from demo.wallet_store import DatabaseBooks, DatabaseLog
from frame.wallet.books import WalletError, DuplicatePosting
from scripts.wallet_backup import export_wallet, restore_wallet, validate


class WalletStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = make_engine("sqlite:///" + str(Path(self.temp.name, "wallet.db")))
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine, tables=[IdentityDocument.__table__])
        self.factory = make_session_factory(self.engine)

    def books(self, name="a"):
        return DatabaseBooks(self.factory, str(Path(self.temp.name, name, "books.jsonl")))

    def test_restart_and_balance_checks_share_the_durable_postings(self):
        first, second = self.books(), self.books("b")
        first.deposit("seed", "p", 1000)
        self.assertEqual(second.available("p"), 1000)
        second.withdraw("take", "p", 500)
        self.assertEqual(first.available("p"), 500)
        self.assertEqual(len(self.books("fresh").postings), 2)
        with self.assertRaises(DuplicatePosting):
            second.deposit("seed", "p", 1000)
        first.assert_balanced()

    def test_two_instances_cannot_overspend(self):
        first, second = self.books(), self.books("b")
        first.deposit("seed", "p", 1000)
        def spend(pair):
            book, key = pair
            try:
                book.withdraw(key, "p", 800)
                return True
            except WalletError:
                return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(spend, [(first, "one"), (second, "two")]))
        self.assertEqual(sum(results), 1)
        self.assertEqual(first.available("p"), 200)

    def test_failed_outer_operation_rolls_back_the_posting(self):
        book = self.books()
        with self.assertRaises(RuntimeError):
            with book.lock:
                book.deposit("uncommitted", "p", 1000)
                raise RuntimeError("operation failed")
        self.assertEqual(book.available("p"), 0)
        self.assertEqual(self.books("fresh").postings, [])

    def test_related_document_writes_share_wallet_rollback(self):
        from demo.identity_store import IdentityStore
        book = self.books()
        promos = IdentityStore(self.factory, "promos", "unused")
        with self.assertRaises(RuntimeError):
            with book.lock:
                book.deposit("uncommitted", "p", 1000)
                data = promos.read_all()
                data["p"] = {"claimed": True}
                promos.write_all(data)
                raise RuntimeError("failed after related write")
        self.assertEqual(promos.read_all(), {})
        self.assertEqual(book.available("p"), 0)

    def test_rounds_and_backup_restore_survive_empty_directories(self):
        book = self.books()
        book.deposit("seed", "p", 12345)
        DatabaseLog(self.factory, "rounds").append({"round_id": "r", "player": "p"})
        backup = export_wallet(self.factory)
        restored_engine = make_engine("sqlite:///" + str(Path(self.temp.name, "restored.db")))
        self.addCleanup(restored_engine.dispose)
        Base.metadata.create_all(restored_engine, tables=[IdentityDocument.__table__])
        factory = make_session_factory(restored_engine)
        restore_wallet(factory, backup)
        restored = DatabaseBooks(factory, str(Path(self.temp.name, "absent", "books.jsonl")))
        self.assertEqual(restored.available("p"), 12345)
        self.assertEqual(DatabaseLog(factory, "rounds").read()[0]["round_id"], "r")
        with self.assertRaises(ValueError):
            restore_wallet(factory, backup)
        broken = deepcopy(backup)
        broken["payload"]["runtime:books"]["postings"][0]["legs"][0]["amount"] += 1
        with self.assertRaises(ValueError):
            validate(broken)

    def test_backup_restore_preserves_crypto_invoices_and_publisher_state(self):
        from demo.identity_store import IdentityStore
        book = self.books()
        book.deposit('seed', 'p', 10000)
        documents = {
            'crypto_charges': {'invoice': {'deposit_id': 'invoice', 'player': 'p',
                                            'amount_minor': 200, 'provider_ref': 'ref', 'posted': False}},
            'publisher_state': {'tokens': {'token': {'player': 'p', 'game_id': 'g',
                                                      'issued_at': '2026-11-08T00:00:00+00:00'}}},
        }
        for name, data in documents.items():
            store = IdentityStore(self.factory, name, '')
            snapshot = store.read_all()
            snapshot.update(data)
            store.write_all(snapshot)
        backup = export_wallet(self.factory)
        for name, data in documents.items():
            self.assertEqual(backup['payload'][name], data)
        engine = make_engine('sqlite:///' + str(Path(self.temp.name, 'payment-restored.db')))
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine, tables=[IdentityDocument.__table__])
        factory = make_session_factory(engine)
        restore_wallet(factory, backup)
        for name, data in documents.items():
            self.assertEqual(IdentityStore(factory, name, '').read_all(), data)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(os.environ.get("OPERATOR_TEST_DATABASE_URL"), "isolated Postgres URL not supplied")
class PostgresWalletStoreTest(WalletStoreTest):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        engine = make_engine(os.environ["OPERATOR_TEST_DATABASE_URL"])
        self.addCleanup(engine.dispose)
        from sqlalchemy.schema import CreateSchema, DropSchema
        schema = "operator_wallet_test_" + uuid.uuid4().hex
        with engine.begin() as db:
            db.execute(CreateSchema(schema))
        def drop():
            with engine.begin() as db:
                db.execute(DropSchema(schema, cascade=True))
        self.addCleanup(drop)
        self.engine = engine.execution_options(schema_translate_map={None: schema})
        Base.metadata.create_all(self.engine, tables=[IdentityDocument.__table__])
        self.factory = make_session_factory(self.engine)
