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
        from demo.models import IdentityDocument
        Base.metadata.create_all(self.engine, tables=[
            IdentityDocument.__table__, PlayerDevice.__table__])
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
