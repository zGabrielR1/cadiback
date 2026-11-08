"""Portable publisher-state and orchestration checks, without a SQL adapter."""
from contextlib import contextmanager
from copy import deepcopy
import json
from types import SimpleNamespace
import threading
import unittest

from demo.publisher_state import (FIELDS, cleanup_state, decode_state, encode_state,
                                 prune_expired, token_expired, publisher_operation)


class PublisherStateTest(unittest.TestCase):
    def demo(self, payload=None, *, fail_save=False, fail_commit=False):
        durable = deepcopy(payload or {})
        active = []
        writes = []
        @contextmanager
        def transaction():
            active.append(True)
            try:
                yield
                if fail_commit:
                    raise RuntimeError('commit failed')
            finally:
                active.pop()
        def read():
            self.assertTrue(active)
            return deepcopy(durable)
        def write(data):
            self.assertTrue(active)
            if fail_save:
                raise RuntimeError('save failed')
            writes.append(deepcopy(data))
        demo = SimpleNamespace(
            books=SimpleNamespace(lock=transaction()), _publisher_lock=threading.RLock(),
            _publisher_depth=0, publisher_store=SimpleNamespace(read_all=read, write_all=write),
            wallet_tokens={}, rgs_sessions={}, rgs_rounds={}, pragmatic_books={})
        return demo, writes

    def test_json_round_trip_preserves_provider_identity_and_balance_baseline(self):
        demo, _ = self.demo()
        demo.wallet_tokens['token'] = {'player': 'p', 'game_id': 'g', 'issued_at': '2026-11-08T00:00:00+00:00'}
        demo.rgs_sessions = {('a:b', 'c'): 'token', ('a', 'b:c'): 'other'}
        demo.rgs_rounds = {('a:b', 'c'): {'stake': 200, 'win': 500}}
        demo.pragmatic_books = {'token': {'last': 10000, 'stake': 200, 'seq': 7}}
        decoded = decode_state(json.loads(json.dumps(encode_state(demo))))
        self.assertEqual(decoded, tuple(getattr(demo, field) for field in FIELDS))
        decoded[0]['token']['player'] = 'changed'
        self.assertEqual(demo.wallet_tokens['token']['player'], 'p')

    def test_nested_operations_refresh_once_and_write_combined_state(self):
        demo, writes = self.demo({'sessions': [{'provider': 'vendor', 'session': 's', 'token': 'saved'}]})
        with publisher_operation(demo):
            self.assertEqual(demo.rgs_sessions[('vendor', 's')], 'saved')
            demo.rgs_rounds[('vendor', 's')] = {'stake': 200, 'win': 0}
            with publisher_operation(demo):
                demo.rgs_rounds[('vendor', 's')]['win'] = 500
            self.assertEqual(writes, [])
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]['rounds'][0]['win'], 500)

    def test_operation_save_and_commit_errors_restore_refreshed_state(self):
        payload = {'rounds': [{'provider': 'vendor', 'session': 's', 'stake': 200, 'win': 0}]}
        for failure in ('operation', 'save', 'commit'):
            with self.subTest(failure=failure):
                demo, _ = self.demo(payload, fail_save=failure == 'save', fail_commit=failure == 'commit')
                with self.assertRaises(RuntimeError):
                    with publisher_operation(demo):
                        demo.rgs_rounds.clear()
                        if failure == 'operation':
                            raise RuntimeError('operation failed')
                self.assertEqual(demo.rgs_rounds, {('vendor', 's'): {'stake': 200, 'win': 0}})
                self.assertEqual(demo._publisher_depth, 0)

    def test_expired_tokens_and_orphans_are_cleaned(self):
        demo, _ = self.demo()
        now = None
        fresh = {'player': 'p', 'game_id': 'g', 'issued_at': '2099-01-01T00:00:00+00:00'}
        old = {'player': 'p', 'game_id': 'g', 'issued_at': '2020-01-01T00:00:00+00:00'}
        demo.wallet_tokens = {'fresh': dict(fresh), 'old': dict(old)}
        demo.rgs_sessions = {('v', 's1'): 'fresh', ('v', 's2'): 'old'}
        demo.rgs_rounds = {('v', 's1'): {'stake': 1, 'win': 0}, ('v', 's2'): {'stake': 1, 'win': 0}}
        self.assertTrue(token_expired(demo.wallet_tokens['old']))
        self.assertFalse(token_expired(demo.wallet_tokens['fresh']))
        pruned = prune_expired(demo)
        self.assertEqual(pruned, 1)
        self.assertEqual(set(demo.wallet_tokens), {'fresh'})
        self.assertEqual(set(demo.rgs_sessions), {('v', 's1')})
        self.assertEqual(set(demo.rgs_rounds), {('v', 's1')})
        self.assertEqual(demo.wallet_tokens['fresh']['game_id'], 'g')

    def test_duplicate_or_malformed_session_rows_are_rejected(self):
        row = {'provider': 'vendor', 'session': 's', 'stake': 200, 'win': 0}
        for payload in ({'rounds': [row, row]}, {'rounds': [{**row, 'stake': True}]},
                        {'rounds': [{**row, 'win': -1}]}, {'sessions': [None]},
                        {'tokens': {'t': {'player': 'p'}}}, {'unknown': {}}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                decode_state(payload)


if __name__ == '__main__':
    unittest.main()
