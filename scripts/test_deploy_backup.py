import io
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from scripts.deploy_backup import before_deploy
from scripts.wallet_backup import make_backup, validate


class CutoverGuardTest(unittest.TestCase):
    def test_validated_backup_is_written_before_return_and_engine_is_disposed(self):
        health = {'storage': {'wallet': 'database'}}
        backup = make_backup({}, allow_empty=True)
        with tempfile.TemporaryDirectory() as root, \
                patch('scripts.deploy_backup.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(health).encode())), \
                patch('scripts.deploy_backup.make_engine') as engine, \
                patch('scripts.deploy_backup.make_session_factory') as factory, \
                patch('scripts.deploy_backup.export_wallet', return_value=backup) as export:
            before_deploy(root, 'https://example.test', {'DATABASE_URL': 'test'})
            export.assert_called_once_with(factory.return_value, allow_empty=True)
            paths = list(Path(root, '.backups').glob('wallet-*.json'))
            self.assertEqual(len(paths), 1)
            self.assertEqual(validate(json.loads(paths[0].read_text())), backup['payload'])
            engine.return_value.dispose.assert_called_once()

    def test_invalid_database_snapshot_cannot_produce_a_backup(self):
        health = {'storage': {'wallet': 'database'}}
        with tempfile.TemporaryDirectory() as root, \
                patch('scripts.deploy_backup.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(health).encode())), \
                patch('scripts.deploy_backup.make_engine') as engine, \
                patch('scripts.deploy_backup.make_session_factory'), \
                patch('scripts.deploy_backup.export_wallet', side_effect=ValueError('partial wallet')):
            with self.assertRaisesRegex(ValueError, 'partial wallet'):
                before_deploy(root, 'https://example.test', {'DATABASE_URL': 'test'})
            self.assertFalse(Path(root, '.backups').exists())
            engine.return_value.dispose.assert_called_once()

    def test_nonempty_live_file_wallet_is_never_discarded(self):
        health = {"storage": {"wallet":"files"}, "checks":[
            {"name":"books", "detail":"1 postings balance to zero"},
            {"name":"ledger", "detail":"0 records, 0 observations, 0 fills"}]}
        with patch('scripts.deploy_backup.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(health).encode())), \
                patch('scripts.deploy_backup.make_engine') as engine:
            with self.assertRaisesRegex(ValueError, 'nonempty'):
                before_deploy('.', 'https://example.test', {'DATABASE_URL':'not-used'})
            engine.assert_not_called()
