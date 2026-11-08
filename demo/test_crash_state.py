"""Crash-operation orchestration; database integration lives in test_persistence."""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import Mock

from demo.crash_state import crash_operation


class CrashOperationTest(unittest.TestCase):
    def demo(self, *, commit_fails=False):
        stored = {'token': {'stake_minor': 200}}
        active = []

        @contextmanager
        def transaction():
            active.append(True)
            try:
                yield
                if commit_fails:
                    raise RuntimeError('commit failed')
            finally:
                active.pop()

        def read():
            self.assertTrue(active, 'pending reads must occur under the wallet lock')
            return deepcopy(stored)

        demo = SimpleNamespace(
            _crash_lock=threading.Lock(), books=SimpleNamespace(lock=transaction()),
            crash_store=SimpleNamespace(read_all=Mock(side_effect=read)),
            crash_pending={'stale': {}},
            _save_crash_pending=Mock(side_effect=lambda: self.assertTrue(active)))
        return demo, stored

    def test_refresh_and_save_are_inside_wallet_transaction(self):
        demo, stored = self.demo()
        with crash_operation(demo):
            self.assertEqual(demo.crash_pending, stored)
            demo.crash_pending['new'] = {'stake_minor': 500}
        demo._save_crash_pending.assert_called_once()

    def test_read_only_status_does_not_rewrite_pending_rounds(self):
        demo, _ = self.demo()
        with crash_operation(demo):
            pass
        demo._save_crash_pending.assert_not_called()

    def test_file_mode_saves_changes_and_keeps_read_only_status_read_only(self):
        demo = SimpleNamespace(_crash_lock=threading.Lock(), crash_store=None,
                               crash_pending={}, _save_crash_pending=Mock())
        with crash_operation(demo):
            demo.crash_pending['token'] = {'stake_minor': 200}
        demo._save_crash_pending.assert_called_once()
        demo._save_crash_pending.reset_mock()
        with crash_operation(demo):
            pass
        demo._save_crash_pending.assert_not_called()

    def test_operation_save_and_commit_failures_restore_refreshed_memory(self):
        for failure in ('operation', 'save', 'commit'):
            with self.subTest(failure=failure):
                demo, stored = self.demo(commit_fails=failure == 'commit')
                if failure == 'save':
                    demo._save_crash_pending.side_effect = RuntimeError('save failed')
                with self.assertRaises(RuntimeError):
                    with crash_operation(demo):
                        demo.crash_pending['token']['stake_minor'] = 999
                        if failure == 'operation':
                            raise RuntimeError('operation failed')
                self.assertEqual(demo.crash_pending, stored)


if __name__ == '__main__':
    unittest.main()
