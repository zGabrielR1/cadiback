"""A deploy must never truncate dashboard-only credentials."""
import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts import render_deploy as deploy


class EnvironmentPaginationTest(unittest.TestCase):
    def setUp(self):
        committed = patch.object(deploy, 'committed_release', return_value='a' * 40)
        committed.start()
        self.addCleanup(committed.stop)

    def test_database_cannot_be_changed_or_removed_by_environment_update(self):
        current = [{'key': 'DATABASE_URL', 'value': 'postgresql://current/test'}]
        for replace in (False, True):
            with self.subTest(replace=replace):
                with self.assertRaisesRegex(deploy.RenderError, 'migration'):
                    deploy.planned_environment(current, [{'key': 'DATABASE_URL', 'value': 'postgresql://other/test'}], replace)
        with self.assertRaisesRegex(deploy.RenderError, 'migration'):
            deploy.planned_environment(current, [], True)
        self.assertEqual(deploy.planned_environment(current, []), current)

    def test_file_to_database_cutover_uses_the_planned_backup_database(self):
        desired = [{'key': 'DATABASE_URL', 'value': 'postgresql://planned/test'}]
        self.assertEqual(deploy.planned_environment([], desired), desired)
        with self.assertRaisesRegex(deploy.RenderError, 'requires DATABASE_URL'):
            deploy.planned_environment([], [])

    def test_backup_failure_prevents_all_service_mutations_in_both_env_modes(self):
        service = {'id': 's', 'serviceDetails': {'url': 'https://example.test'}}
        desired = [{'key': 'DATABASE_URL', 'value': 'postgresql://planned/test'}]
        for replace in (False, True):
            with self.subTest(replace_env=replace), \
                    patch.object(deploy, 'find_service', return_value=service), \
                    patch.object(deploy, 'check_tree', return_value=0), \
                    patch('scripts.release_gate.verified', return_value=True), \
                    patch.object(deploy, 'runtime_env', return_value=desired), \
                    patch.object(deploy, 'get_env_vars', return_value=[]) as read, \
                    patch.object(deploy, 'backup_wallet', side_effect=ValueError('backup failed')) as backup, \
                    patch.object(deploy, 'configure') as configure, \
                    patch.object(deploy, 'set_env_vars') as write:
                with self.assertRaisesRegex(ValueError, 'backup failed'):
                    deploy.run('k', 'repo', True, replace_env=replace)
                read.assert_called_once_with('s', 'k')
                backup.assert_called_once_with(service, desired)
                configure.assert_not_called()
                write.assert_not_called()

    def test_database_change_is_rejected_before_service_configuration(self):
        with patch.object(deploy, 'find_service', return_value={'id': 's'}), \
                patch.object(deploy, 'check_tree', return_value=0), \
                patch('scripts.release_gate.verified', return_value=True), \
                patch.object(deploy, 'runtime_env', return_value=[{'key': 'DATABASE_URL', 'value': 'new'}]), \
                patch.object(deploy, 'get_env_vars', return_value=[{'key': 'DATABASE_URL', 'value': 'old'}]), \
                patch.object(deploy, 'configure') as configure, \
                patch.object(deploy, 'set_env_vars') as write:
            with self.assertRaisesRegex(deploy.RenderError, 'migration'):
                deploy.run('key', 'repo', True)
            configure.assert_not_called()
            write.assert_not_called()

    def test_deploy_pins_verified_commit_and_tracks_returned_id(self):
        sha = 'a' * 40
        response = {'id': 'requested-deploy', 'commit': {'id': sha}, 'status': 'live'}
        with patch.object(deploy, '_call', side_effect=[response, response]) as call, \
                patch.object(deploy.time, 'sleep'):
            self.assertEqual(deploy.deploy('s', 'k', sha), 'live')
        self.assertEqual(call.call_args_list[0].args[2]['commitId'], sha)
        self.assertIn('/deploys/requested-deploy', call.call_args_list[1].args[0])

    def test_wrong_commit_or_missing_deploy_id_cannot_report_success(self):
        sha = 'a' * 40
        for responses in ([{}], [{'id': 'd'}, {'id': 'd', 'commit': {'id': 'b' * 40}, 'status': 'live'}]):
            with self.subTest(responses=responses), \
                    patch.object(deploy, '_call', side_effect=responses), \
                    patch.object(deploy.time, 'sleep'):
                with self.assertRaises(deploy.RenderError):
                    deploy.deploy('s', 'k', sha)

    def test_rejected_deploy_does_not_report_an_older_deploy_as_live(self):
        with patch.object(deploy, '_call', side_effect=deploy.RenderError('rejected')) as call:
            with self.assertRaises(deploy.RenderError):
                deploy.deploy('s', 'k', 'a' * 40)
        self.assertEqual(call.call_count, 1)

    def test_changed_or_unverified_source_cannot_deploy(self):
        with patch.object(deploy, "find_service", return_value={"id":"s"}), \
                patch.object(deploy, "check_tree", return_value=0), \
                patch("scripts.release_gate.verified", return_value=False), \
                patch.object(deploy, "configure") as configure:
            self.assertEqual(deploy.run("k", "repo", True), 1)
            configure.assert_not_called()

    def test_render_key_in_envs_directory_and_export_override(self):
        with tempfile.TemporaryDirectory() as root:
            envs = Path(root, "envs")
            envs.mkdir()
            for content in ("rnd_example", "RENDER_API_KEY=rnd_example\n"):
                (envs / ".env.render").write_text(content)
                with patch.object(deploy, "ROOT", root), \
                        patch.object(deploy, "LOCAL_ENV_FILE", str(Path(root, ".env.local"))), \
                        patch.object(deploy, "ENV_FILE", str(Path(root, ".env.render"))), \
                        patch.object(deploy, "KEY_FILE", str(Path(root, "missing"))), \
                        patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(deploy.read_key(), "rnd_example")
                    with patch.dict(os.environ, {"RENDER_API_KEY": "rnd_exported"}):
                        self.assertEqual(deploy.read_key(), "rnd_exported")

    def test_all_pages_survive_merge(self):
        first = [{"envVar": {"key": f"K{i}", "value": str(i)},
                  "cursor": f"c{i}"} for i in range(100)]
        last = [{"envVar": {"key": "SIGNING_SECRET", "value": "kept"},
                 "cursor": "last"}]
        with patch.object(deploy, "_call", side_effect=[first, last]) as call:
            rows = deploy.get_env_vars("service", "test-key")
        self.assertEqual(len(rows), 101)
        self.assertIn("cursor=c99", call.call_args_list[1].args[0])
        merged = deploy.merge_env_vars(rows, [{"key": "HOST", "value": "0.0.0.0"}])
        self.assertIn({"key": "SIGNING_SECRET", "value": "kept"}, merged)

    def test_envelope_and_bare_rows(self):
        with patch.object(deploy, "_call", return_value={"envVars": [
            {"key": "ONE", "value": "1"},
            {"envVar": {"key": "TWO", "value": "2"}},
        ]}):
            self.assertEqual(deploy.get_env_vars("s", "k"), [
                {"key": "ONE", "value": "1"}, {"key": "TWO", "value": "2"}])

    def test_unreadable_environment_never_replaced(self):
        with patch.object(deploy, "find_service", return_value={"id": "s"}), \
                patch.object(deploy, "check_tree", return_value=0), \
                patch("scripts.release_gate.verified", return_value=True), \
                patch.object(deploy, "configure", return_value={"id": "s"}), \
                patch.object(deploy, "runtime_env", return_value=[]), \
                patch.object(deploy, "get_env_vars", side_effect=deploy.RenderError("offline")), \
                patch.object(deploy, "set_env_vars") as write:
            with self.assertRaises(deploy.RenderError):
                deploy.run("k", "repo", True)
            write.assert_not_called()
