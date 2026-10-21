"""Host-specific local credential loading; never touches real credentials."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from demo import server


class LocalAuthEnvTest(unittest.TestCase):
    def test_local_overrides_legacy_and_process_overrides_local(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy = Path(directory, ".env.betterauth")
            local = Path(directory, ".env.local")
            legacy.write_text("GOOGLE_CLIENT_ID=legacy\nBETTER_AUTH_SECRET=retained\n")
            local.write_text("GOOGLE_CLIENT_ID=local\nGOOGLE_CLIENT_SECRET=local-secret\n")
            with patch.object(server, "BETTERAUTH_ENV_FILE", str(legacy)), \
                 patch.object(server, "LOCAL_ENV_FILE", str(local)):
                env = server.betterauth_env(str(legacy), {"GOOGLE_CLIENT_SECRET": "exported"})
                self.assertEqual(env["GOOGLE_CLIENT_ID"], "local")
                self.assertEqual(env["GOOGLE_CLIENT_SECRET"], "exported")
                self.assertEqual(env["BETTER_AUTH_SECRET"], "retained")
                self.assertEqual(server.session_env(str(legacy), {}), server.betterauth_env(str(legacy), {}))

    def test_deploy_reads_auth_and_render_credentials_from_local(self):
        path = Path(__file__).resolve().parents[1] / "scripts/render_deploy.py"
        spec = importlib.util.spec_from_file_location("local_env_deploy", path)
        deploy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deploy)
        with tempfile.TemporaryDirectory() as directory:
            legacy = Path(directory, ".env.betterauth")
            local = Path(directory, ".env.local")
            legacy.write_text("GOOGLE_CLIENT_ID=legacy\n")
            local.write_text("GOOGLE_CLIENT_ID=local\nGOOGLE_CLIENT_SECRET=local-secret\nRENDER_API_KEY=local-render\n")
            with patch.object(deploy, "BETTERAUTH_ENV_FILE", str(legacy)), \
                 patch.object(deploy, "LOCAL_ENV_FILE", str(local)), \
                 patch.dict(os.environ, {"GOOGLE_CLIENT_SECRET": "exported"}, clear=True):
                env = {row["key"]: row["value"] for row in deploy.read_betterauth_env()}
                self.assertEqual(env["GOOGLE_CLIENT_ID"], "local")
                self.assertEqual(env["GOOGLE_CLIENT_SECRET"], "exported")
                self.assertNotIn("RENDER_API_KEY", env)
                self.assertEqual(deploy.read_key(), "local-render")
