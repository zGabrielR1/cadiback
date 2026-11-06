"""A deploy must never truncate dashboard-only credentials."""
import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts import render_deploy as deploy


class EnvironmentPaginationTest(unittest.TestCase):
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
                patch.object(deploy, "configure", return_value={"id": "s"}), \
                patch.object(deploy, "runtime_env", return_value=[]), \
                patch.object(deploy, "get_env_vars", side_effect=deploy.RenderError("offline")), \
                patch.object(deploy, "set_env_vars") as write:
            with self.assertRaises(deploy.RenderError):
                deploy.run("k", "repo", True)
            write.assert_not_called()
