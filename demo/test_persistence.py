"""Deployment/revocation regressions on an isolated SQL database."""
import concurrent.futures
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from demo.auth import AuthError
from demo.db import make_engine, make_session_factory
from demo.device_store import DatabaseSessionRegistry
from demo.identity_store import IdentityConflict, IdentityStore
from demo.models import Base, PlayerDevice
from demo.player_session import PlayerSessions
from demo.server import Demo
from scripts.import_identity import import_identity, load_identity


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        url = getattr(self, "database_url", "")
        self.engine = make_engine(url or "sqlite:///" + str(self.root / "identity.db"))
        self.addCleanup(self.engine.dispose)
        if url:
            from sqlalchemy.schema import CreateSchema, DropSchema
            schema = "operator_identity_test_" + uuid.uuid4().hex
            with self.engine.begin() as db:
                db.execute(CreateSchema(schema))
            def drop_schema():
                with self.engine.begin() as db:
                    db.execute(DropSchema(schema, cascade=True))
            self.addCleanup(drop_schema)
            self.engine = self.engine.execution_options(schema_translate_map={None: schema})
        from demo.models import IdentityDocument, AsaasCharge
        Base.metadata.create_all(self.engine, tables=[
            IdentityDocument.__table__, PlayerDevice.__table__, AsaasCharge.__table__])
        self.factory = make_session_factory(self.engine)
        self.registry = DatabaseSessionRegistry(self.factory)
        self.signer = PlayerSessions("stable-test-secret")

    def session(self, player="p1", now=1000):
        return self.signer.verify(self.signer.issue(player, now=now), now=now)

    def demo(self, directory):
        return Demo(str(self.root / directory), db=self.factory,
                    player_secret="stable-test-secret")

    def register(self, demo):
        return demo.register_player({
            "name": "Ana Souza", "username": "ana.souza",
            "email": "ana.souza@example.com", "cpf": "529.982.247-25",
            "password": "ana1234", "pix_key": "ana.souza@example.com"})

    def test_fresh_deployment_keeps_account_login_and_device_token(self):
        first = self.demo("deploy-a")
        profile = self.register(first)
        links = first.oauth_links.read_all()
        links["google:subject-1"] = profile["player_id"]
        first.oauth_links.write_all(links)
        second = self.demo("deploy-b")  # empty directory, same database/secret
        self.assertEqual(second.player_from_token(profile["player_token"]), profile["player_id"])
        self.assertEqual(second.oauth_links.read_all()["google:subject-1"], profile["player_id"])
        logged = second.login_player({"identifier": "ana.souza", "password": "ana1234"})
        self.assertEqual(logged["player_id"], profile["player_id"])
        first.logout_player(first.player_session(profile["player_token"]))
        with self.assertRaises(AuthError):
            second.player_from_token(profile["player_token"])
        self.assertEqual(second.player_from_token(logged["player_token"]), profile["player_id"])

    def test_wallet_and_round_history_survive_new_deployment(self):
        first = self.demo("wallet-a")
        profile = self.register(first)
        player = profile["player_id"]
        first.books.deposit("durable-seed", player, 12345)
        first._append_round({"round_id": "r1", "player": player, "tier": "pendente", "type": "sports"})
        second = self.demo("wallet-b")
        self.assertEqual(second.books.available(player), 12345)
        self.assertEqual(second.history(player)[0]["round_id"], "r1")
        self.assertEqual(second.wallet_activity(player)[0]["cash_minor"], 12345)
        self.assertEqual(second.health_report()["storage"]["wallet"], "database")

    def test_password_reset_token_survives_deployment_and_stays_single_use(self):
        first = self.demo("reset-a")
        profile = self.register(first)
        token = "only-in-test-reset-token"
        rows = first.password_resets.read_all()
        rows[first._reset_digest(token)] = {"player_id": profile["player_id"], "created_at": time.time(), "expires_at": time.time() + 1800}
        first.password_resets.write_all(rows)
        second = self.demo("reset-b")
        second.reset_player_password(token, "newpass123")
        with self.assertRaises(ValueError):
            first.reset_player_password(token, "different123")

    def crash_demo(self):
        demo = self.demo('crash-a')
        player = self.register(demo)['player_id']
        demo.books.deposit('crash-seed', player, 10000)
        return demo, player

    def test_crash_start_failure_rolls_back_stake_and_pending_round(self):
        demo, player = self.crash_demo()
        with patch.object(demo.crash_store, 'write_all', side_effect=RuntimeError('pending write failed')):
            with self.assertRaisesRegex(RuntimeError, 'pending write'):
                demo.crash_start({'player': player, 'stake_minor': 200})
        self.assertEqual(demo.books.available(player), 10000)
        self.assertEqual(demo.crash_pending, {})
        self.assertEqual(demo.crash_store.read_all(), {})
        self.assertEqual(len(demo.books.postings), 1)

    def test_new_worker_preserves_round_and_can_cash_out_once(self):
        first, player = self.crash_demo()
        start = first.crash_start({'player': player, 'stake_minor': 200})
        second = self.demo('crash-b')
        self.assertEqual(second.books.available(player), 9800)
        self.assertIn(start['token'], second.crash_pending)
        # A second worker must see the existing flight before debiting again.
        with self.assertRaisesRegex(ValueError, 'voo em andamento'):
            second.crash_start({'player': player, 'stake_minor': 200})
        second.crash_cashout({'token': start['token']}, player_id=player)
        self.assertEqual(first.crash_status({'token': start['token']}, player_id=player),
                         {'status': 'unknown'})
        self.assertEqual(len(first.history(player)), 1)
        self.assertEqual(sum(p.kind == 'bet_settled_casino' for p in first.books.postings), 1)

    def test_crash_settlement_failures_preserve_retryable_round_and_stake(self):
        demo, player = self.crash_demo()
        start = demo.crash_start({'player': player, 'stake_minor': 200})
        token = start['token']
        pending = dict(demo.crash_store.read_all())
        for target in ('history', 'pending'):
            owner, method = ((demo, '_append_round') if target == 'history'
                             else (demo.crash_store, 'write_all'))
            with self.subTest(target=target), patch.object(owner, method, side_effect=RuntimeError('write failed')):
                with self.assertRaisesRegex(RuntimeError, 'write failed'):
                    demo.crash_cashout({'token': token}, player_id=player)
            self.assertEqual(demo.books.available(player), 9800)
            self.assertEqual(demo.crash_store.read_all(), pending)
            self.assertEqual(demo.crash_pending, pending)
            self.assertEqual(demo._all_rounds(), [])
            self.assertEqual(len(demo.books.postings), 2)
        demo.crash_cashout({'token': token}, player_id=player)
        self.assertEqual(demo.crash_store.read_all(), {})
        self.assertEqual(len(demo._all_rounds()), 1)

    def test_concurrent_workers_cannot_open_two_flights_for_one_player(self):
        first, player = self.crash_demo()
        second = self.demo('crash-b')
        def start(demo):
            try:
                return demo.crash_start({'player': player, 'stake_minor': 200})
            except ValueError:
                return None
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(start, (first, second)))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(first.books.available(player), 9800)
        self.assertEqual(len(first.crash_store.read_all()), 1)

    def test_expired_round_after_restart_settles_once_across_workers(self):
        first, player = self.crash_demo()
        start = first.crash_start({'player': player, 'stake_minor': 200})
        pending = first.crash_store.read_all()
        pending[start['token']]['started_at'] = time.time() - 1000
        first.crash_store.write_all(pending)
        second = self.demo('crash-b')
        self.assertEqual(second.sweep_crash(), 1)
        self.assertEqual(first.sweep_crash(), 0)
        self.assertEqual(first.books.available(player), 9800)
        self.assertEqual(first.crash_store.read_all(), {})
        self.assertEqual(len(first._all_rounds()), 1)

    def test_round_history_failures_roll_back_postings_and_allow_retry(self):
        demo, player = self.crash_demo()
        operations = [
            ('slot', lambda: demo.spin({'player': player, 'game_id': 'demo:neon-gems',
                                       'stake_minor': 200, 'round_id': 'slot-rollback'})),
            ('roulette', lambda: demo.spin({'player': player, 'game_id': 'demo:roulette-europeia',
                                           'stake_minor': 200, 'round_id': 'roulette-rollback', 'selection': 'red'})),
            ('arcade', lambda: demo.spin({'player': player, 'game_id': 'demo:plinko-drops',
                                         'stake_minor': 200, 'round_id': 'arcade-rollback'})),
            ('sports', lambda: demo.bet({'player': player, 'fixture_key': 'synthetic',
                                        'selection': 'Home', 'price': 2.0,
                                        'stake_minor': 200, 'bet_id': 'sports-rollback'})),
            ('publisher', lambda: demo.settle_rgs_round(player, 'provider:test', 'publisher-rollback', 200, 100)),
        ]
        for name, operation in operations:
            with self.subTest(name=name):
                balance = demo.books.available(player)
                postings = len(demo.books.postings)
                rounds = len(demo._all_rounds())
                with patch.object(demo, '_append_round', side_effect=RuntimeError('history failed')):
                    with self.assertRaisesRegex(RuntimeError, 'history failed'):
                        operation()
                self.assertEqual(demo.books.available(player), balance)
                self.assertEqual(len(demo.books.postings), postings)
                self.assertEqual(len(demo._all_rounds()), rounds)
                operation()  # same request remains retryable after rollback
                self.assertEqual(len(demo._all_rounds()), rounds + 1)

    def test_sports_settlement_history_failure_keeps_pending_bet_retryable(self):
        demo, player = self.crash_demo()
        demo.bet({'player': player, 'fixture_key': 'synthetic', 'selection': 'Home',
                  'price': 2.0, 'stake_minor': 200, 'bet_id': 'pending-rollback'})
        with patch.object(demo, '_append_round', side_effect=RuntimeError('history failed')):
            with self.assertRaisesRegex(RuntimeError, 'history failed'):
                demo.settle_pending(settle_delay_seconds=0)
        self.assertEqual(demo.books.available(player), 9800)
        self.assertEqual(len(demo.books.postings), 2)
        self.assertEqual([row['tier'] for row in demo._all_rounds()], ['pendente'])
        self.assertEqual(len(demo.settle_pending(settle_delay_seconds=0)), 1)
        self.assertEqual(demo.settle_pending(settle_delay_seconds=0), [])

    def test_publisher_credit_history_failure_rolls_back_payout(self):
        demo, player = self.crash_demo()
        demo.books.place_bet('demo:wdebit:provider:test:credit-round', player, 200, '2.00')
        with patch.object(demo, '_wallet_session', return_value={'player': player, 'game_id': 'provider:test'}):
            with patch.object(demo, '_append_round', side_effect=RuntimeError('history failed')):
                with self.assertRaisesRegex(RuntimeError, 'history failed'):
                    demo.wallet_credit({'round_id': 'credit-round', 'payout_minor': 100})
            self.assertEqual(demo.books.available(player), 9800)
            self.assertEqual(len(demo.books.postings), 2)
            self.assertEqual(demo._all_rounds(), [])
            demo.wallet_credit({'round_id': 'credit-round', 'payout_minor': 100})
            self.assertEqual(demo.books.available(player), 9900)
            self.assertEqual(len(demo._all_rounds()), 1)

    def test_daily_deposit_limit_is_shared_by_concurrent_workers(self):
        first, player = self.crash_demo()  # 10000 already in the journal
        second = self.demo('deposit-b')
        first.limits.deposit_daily = second.limits.deposit_daily = 15000
        def deposit(item):
            demo, reference = item
            try:
                demo.deposit({'player': player, 'amount_minor': 4000,
                              'method': 'pix', 'deposit_id': reference})
                return True
            except ValueError:
                return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            accepted = list(pool.map(deposit, ((first, 'one'), (second, 'two'))))
        self.assertEqual(sum(accepted), 1)
        self.assertEqual(first._deposited_today(player), 14000)
        self.assertEqual(second._deposited_today(player), 14000)
        self.assertEqual(first.books.available(player), 14000)

    def test_asaas_acknowledgement_failure_rolls_back_charge_and_credit(self):
        demo = self.demo('asaas-atomic')
        player = self.register(demo)['player_id']
        row = {'deposit_id': 'atomic', 'player': player, 'amount_minor': 10000,
               'provider_ref': 'provider-ref', 'provider_status': 'PENDING', 'posted': False}
        demo._put_charge(row)
        save = demo._put_charge
        def fail_after_write(updated):
            save(updated)
            raise RuntimeError('failed after acknowledgement flush')
        with patch.object(demo, '_put_charge', side_effect=fail_after_write):
            with self.assertRaisesRegex(RuntimeError, 'acknowledgement flush'):
                demo._confirm_asaas_charge('atomic', row)
        self.assertFalse(row['posted'])
        self.assertFalse(demo._get_charge('atomic')['posted'])
        self.assertEqual(demo.books.available(player), 0)
        self.assertEqual(demo._deposited_today(player), 0)
        self.assertEqual(demo.books.postings, [])
        demo._confirm_asaas_charge('atomic', row)
        self.assertTrue(demo._get_charge('atomic')['posted'])
        self.assertEqual(demo.books.available(player), 10000)
        self.assertEqual(demo._deposited_today(player), 10000)

    def test_crypto_invoice_and_paid_marker_survive_fresh_worker_directories(self):
        first = self.demo('crypto-a')
        player = self.register(first)['player_id']
        pending = {'deposit_id': 'crypto', 'player': player, 'amount_minor': 10000,
                   'provider_ref': 'provider-ref', 'posted': False, 'provider_status': 'WAITING'}
        first._put_crypto_charge(pending)
        second = self.demo('crypto-b')
        self.assertEqual(second._get_crypto_charge('crypto'), pending)
        received = second._get_crypto_charge('crypto')
        second._confirm_crypto_charge('crypto', received)
        self.assertTrue(first._get_crypto_charge('crypto')['posted'])
        first._put_crypto_charge(pending)  # stale polling result cannot downgrade it
        self.assertTrue(second._get_crypto_charge('crypto')['posted'])
        first._confirm_crypto_charge('crypto', pending)
        self.assertEqual(first.books.available(player), 10000)
        self.assertEqual(len(first.books.postings), 1)

    def test_paid_pix_invoice_cannot_be_downgraded_or_reassigned(self):
        demo = self.demo('pix-monotonic')
        player = self.register(demo)['player_id']
        row = {'deposit_id': 'pix', 'player': player, 'amount_minor': 10000,
               'provider_ref': 'provider-ref', 'posted': False, 'provider_status': 'PENDING'}
        demo._put_charge(row)
        demo._confirm_asaas_charge('pix', dict(row))
        demo._put_charge(row)
        self.assertTrue(demo._get_charge('pix')['posted'])
        with self.assertRaises(ValueError):
            demo._put_charge({**row, 'player': 'other-player'})
        self.assertEqual(demo._get_charge('pix')['player'], player)

    def test_crypto_acknowledgement_failure_rolls_back_credit_and_invoice(self):
        demo = self.demo('crypto-failure')
        player = self.register(demo)['player_id']
        row = {'deposit_id': 'crypto', 'player': player, 'amount_minor': 10000,
               'provider_ref': 'provider-ref', 'posted': False, 'provider_status': 'WAITING'}
        demo._put_crypto_charge(row)
        save = demo.crypto_store.write_all
        def fail_after_write(snapshot):
            save(snapshot)
            raise RuntimeError('failed after invoice write')
        with patch.object(demo.crypto_store, 'write_all', side_effect=fail_after_write):
            with self.assertRaisesRegex(RuntimeError, 'invoice write'):
                demo._confirm_crypto_charge('crypto', row)
        self.assertFalse(row['posted'])
        self.assertFalse(demo._get_crypto_charge('crypto')['posted'])
        self.assertEqual(demo.books.available(player), 0)
        demo._confirm_crypto_charge('crypto', row)
        self.assertEqual(demo.books.available(player), 10000)

    def publisher_demo(self):
        demo, player = self.crash_demo()
        with patch.object(demo, 'provider_demos', return_value={'demos': [{'game_id': 'provider:test'}]}):
            token = demo.wallet_launch({'player': player, 'game_id': 'provider:test'})['token']
        demo.rgs_bind('vendor', 'session', token)
        return demo, player, token

    def test_publisher_tokens_bindings_and_pending_rounds_survive_worker_handoff(self):
        first, player, token = self.publisher_demo()
        first.rgs_open_round('vendor', 'session', 200)
        first.rgs_note_win('vendor', 'session', 100)
        second = self.demo('publisher-b')
        self.assertEqual(second.wallet_owner(token)['player'], player)
        self.assertEqual(second.rgs_token('vendor', 'session'), token)
        from demo.publisher_state import publisher_operation
        with publisher_operation(second):
            pending = second.rgs_close_round('vendor', 'session')
            self.assertEqual(pending, {'stake': 200, 'win': 100})
            second.settle_rgs_round(player, 'provider:test', 'handoff', pending['stake'], pending['win'])
        self.assertEqual(first.books.available(player), 9900)
        self.assertIsNone(first.rgs_close_round('vendor', 'session'))
        self.assertEqual(len(first._all_rounds()), 1)

    def test_failed_publisher_tap_preserves_pending_round_and_wallet(self):
        from demo.server import Handler
        first, player, _ = self.publisher_demo()
        first.rgs_open_round('vendor', 'session', 200)
        first.rgs_note_win('vendor', 'session', 100)
        second = self.demo('publisher-b')
        handler = Handler.__new__(Handler)
        owner = {'player': player, 'game_id': 'provider:test'}
        with patch('demo.server.DEMO', second), \
                patch('demo.server.rgs_proxy.session_uuid', return_value='session'), \
                patch('demo.server.rgs_proxy.bet_total', return_value=0), \
                patch('demo.server.rgs_proxy.round_state', return_value={'id': 'round', 'done': True, 'win': 100}), \
                patch('demo.server.rgs_proxy.replace_balance', side_effect=lambda data, balance: data):
            with patch.object(second.publisher_store, 'write_all', side_effect=RuntimeError('publisher write failed')):
                with self.assertRaisesRegex(RuntimeError, 'publisher write'):
                    handler._tap_rgs('vendor', owner, b'{}', b'{}')
            self.assertEqual(first.books.available(player), 10000)
            self.assertEqual(first._all_rounds(), [])
            self.assertEqual(second.rgs_rounds[('vendor', 'session')]['stake'], 200)
            handler._tap_rgs('vendor', owner, b'{}', b'{}')
        self.assertEqual(first.books.available(player), 9900)
        self.assertEqual(len(first._all_rounds()), 1)
        self.assertIsNone(first.rgs_close_round('vendor', 'session'))

    def test_pragmatic_baseline_and_sequence_survive_worker_handoff(self):
        first, player, token = self.publisher_demo()
        self.assertIsNone(first.pragmatic_note_balance(token, 'provider:test', 100000))
        second = self.demo('publisher-b')
        entry = second.pragmatic_note_balance(token, 'provider:test', 99800)
        self.assertTrue(entry['settled'])
        self.assertEqual(first.books.available(player), 9800)
        self.assertIsNone(first.pragmatic_note_balance(token, 'provider:test', 99800))
        self.assertEqual(first.pragmatic_books[token]['seq'], 1)

    def test_concurrent_publisher_round_accumulation_preserves_both_stakes(self):
        first, _, _ = self.publisher_demo()
        second = self.demo('publisher-b')
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda demo: demo.rgs_open_round('vendor', 'session', 200), (first, second)))
        self.assertEqual(first.rgs_close_round('vendor', 'session'), {'stake': 400, 'win': 0})

    def test_epoch_change_and_account_deletion_survive_deploy(self):
        first = self.demo("a")
        profile = self.register(first)
        players = first.players.read_all()
        players[profile["player_id"]]["session_epoch"] += 1
        first.players.write_all(players)
        second = self.demo("b")
        with self.assertRaises(AuthError):
            second.player_from_token(profile["player_token"])
        token = second.issue_player_token(profile["player_id"])["player_token"]
        players = second.players.read_all()
        del players[profile["player_id"]]
        second.players.write_all(players)
        with self.assertRaises(AuthError):
            first.player_from_token(token)

    def test_stale_writer_cannot_undo_password_change(self):
        store = IdentityStore(self.factory, "players", "unused")
        original = store.read_all()
        original["p1"] = {"session_epoch": 0}
        store.write_all(original)
        stale = store.read_all()
        fresh = store.read_all()
        fresh["p1"]["session_epoch"] = 1
        store.write_all(fresh)
        stale["p2"] = {}
        with self.assertRaises(IdentityConflict):
            store.write_all(stale)
        self.assertEqual(store.read_all(), {"p1": {"session_epoch": 1}})

    def test_two_first_writers_cannot_overwrite_each_other(self):
        store = IdentityStore(self.factory, "players", "unused")
        first, stale = store.read_all(), store.read_all()
        first["p1"] = {}
        store.write_all(first)
        with self.assertRaises(IdentityConflict):
            store.write_all(stale)

    def test_activity_is_throttled_and_never_revives_logout(self):
        session = self.session()
        self.registry.record(session, now=1000)
        self.assertTrue(self.registry.touch(session, now=1060))
        self.assertEqual(self.registry.lookup(session.session_id, now=1060)["seen"], 1000)
        self.assertTrue(self.registry.touch(session, now=1601))
        self.assertEqual(self.registry.lookup(session.session_id, now=1601)["seen"], 1601)
        other = DatabaseSessionRegistry(self.factory)
        self.assertTrue(other.revoke("p1", session.session_id))
        self.assertFalse(self.registry.touch(session, now=2202))
        self.assertIsNone(other.lookup(session.session_id, now=2202))

    def test_row_must_match_token_owner_epoch_and_expiry(self):
        session = self.session()
        self.registry.record(session, now=1000)
        for fake in (replace(session, player_id="stranger"),
                     replace(session, epoch=1),
                     replace(session, expires_at=session.expires_at + 1)):
            self.assertFalse(self.registry.touch(fake, now=1001))
        self.assertFalse(self.registry.revoke("stranger", session.session_id))
        self.assertTrue(self.registry.touch(session, now=1001))

    def test_cap_and_revocations_are_shared_across_instances(self):
        self.registry.max_per_player = 2
        sessions = [self.session(now=1000 + i) for i in range(3)]
        for session in sessions:
            self.registry.record(session, now=session.issued_at)
        other = DatabaseSessionRegistry(self.factory)
        self.assertIsNone(other.lookup(sessions[0].session_id, now=1003))
        self.assertEqual(other.revoke_others("p1", sessions[-1].session_id), 1)
        self.assertEqual([r["id"] for r in self.registry.active("p1", now=1003)],
                         [sessions[-1].session_id])
        self.assertEqual(other.revoke_player("p1"), 1)
        self.assertEqual(self.registry.active("p1", now=1003), [])

    def test_concurrent_logins_keep_the_cap(self):
        self.registry.max_per_player = 3
        sessions = [self.session(now=1000 + i) for i in range(8)]
        def record(session):
            registry = DatabaseSessionRegistry(self.factory, max_per_player=3)
            return registry.record(session, now=1010)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(record, sessions))
        self.assertEqual(len(self.registry.active("p1", now=1011)), 3)

    def test_expiry_is_absolute_and_pruning_is_persistent(self):
        session = self.session()
        self.registry.record(session, now=1000)
        self.assertFalse(self.registry.touch(session, now=session.expires_at))
        self.assertIsNone(self.registry.lookup(session.session_id, now=session.expires_at))
        self.assertEqual(self.registry.prune(now=session.expires_at), 1)
        with self.factory() as db:
            self.assertIsNone(db.get(PlayerDevice, session.session_id))

    def test_atomic_import_is_one_time_and_preserves_revocations(self):
        now = int(time.time())
        source = self.root / "import"
        source.mkdir()
        session = self.session(now=now)
        players = {"p1": {"player_id": "p1", "session_epoch": 0}}
        (source / "players.json").write_text(json.dumps(players))
        (source / "oauth_links.json").write_text('{"google:subject":"p1"}')
        row = {"player": "p1", "epoch": 0, "created": now, "seen": now,
               "expires": session.expires_at, "remember": False, "user_agent": "", "ip": ""}
        (source / "player_sessions.json").write_text(json.dumps({"sessions": {
            session.session_id: row, "expired": {**row, "expires": now - 1},
            "old-epoch": {**row, "epoch": 1}}}))
        data = load_identity(source)
        self.assertEqual(list(data[2]), [session.session_id])
        import_identity(self.factory, *data)
        self.registry.revoke_player("p1")
        with self.assertRaises(ValueError):
            import_identity(self.factory, *data)
        self.assertEqual(self.registry.active("p1"), [])

    def test_failed_import_rolls_back_accounts_too(self):
        from sqlalchemy.exc import StatementError
        with self.assertRaises((KeyError, StatementError)):
            import_identity(self.factory, {"p1": {}}, {}, {"bad": {}})
        self.assertEqual(IdentityStore(self.factory, "players", "unused").read_all(), {})

    def test_configured_database_failure_does_not_fall_back_to_files(self):
        from demo import server
        with patch.object(server, "db_env", return_value={"DATABASE_URL": "postgresql://unused"}), \
             patch.object(server, "make_engine", side_effect=RuntimeError("unavailable")):
            with self.assertRaises(RuntimeError):
                server._ambient_db()

    def test_malformed_unicode_token_is_an_auth_refusal(self):
        from demo.player_session import PlayerSessionError
        for token in ("ps1.é.mac", "ps1.payload.é"):
            with self.assertRaises(PlayerSessionError):
                self.signer.verify(token)


@unittest.skipUnless(os.environ.get("OPERATOR_TEST_DATABASE_URL"),
                     "explicit Postgres integration URL not supplied")
class PostgresPersistenceTest(PersistenceTest):
    """Same regressions in disposable schemas; never reads production rows."""
    database_url = os.environ.get("OPERATOR_TEST_DATABASE_URL", "")
