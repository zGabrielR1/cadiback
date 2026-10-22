"""A deploy must never truncate dashboard-only credentials."""
import unittest
from unittest.mock import patch

from scripts import render_deploy as deploy


class EnvironmentPaginationTest(unittest.TestCase):
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
