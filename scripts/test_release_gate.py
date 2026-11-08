"""Release approval must describe a complete, successful, unchanged run."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import release_gate as gate


class ReleaseGateTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for name in gate.SOURCE_FILES:
            (self.root / name).write_text('initial')
        self.receipt = self.root / '.release' / 'verified.json'
        for name, value in (('ROOT', self.root), ('RECEIPT', self.receipt)):
            change = patch.object(gate, name, value)
            change.start()
            self.addCleanup(change.stop)

    def command(self, code):
        return [sys.executable, '-c', code]

    def test_failed_rerun_revokes_prior_approval_and_still_runs_later_checks(self):
        gate.run_checks([('pass', self.command('pass'))])
        self.assertTrue(gate.verified())
        report = gate.run_checks([
            ('failure', self.command('raise SystemExit(3)')),
            ('later', self.command("print('later check executed')")),
        ])
        self.assertFalse(report['passed'])
        self.assertFalse(self.receipt.exists())
        self.assertEqual([row['returncode'] for row in report['checks']], [3, 0])
        self.assertIn('later check executed', (self.receipt.parent / 'later.log').read_text())
        self.assertEqual(json.loads((self.receipt.parent / 'report.json').read_text()), report)

    def test_source_change_during_checks_cannot_receive_approval(self):
        report = gate.run_checks([('mutate', self.command(
            "from pathlib import Path; Path('Dockerfile').write_text('changed')"))])
        self.assertFalse(report['source_unchanged'])
        self.assertFalse(report['passed'])
        self.assertFalse(self.receipt.exists())

    def test_missing_executable_is_a_failed_check_with_a_report(self):
        report = gate.run_checks([('missing', [str(self.root / 'missing-executable')])])
        self.assertEqual(report['checks'][0]['returncode'], 127)
        self.assertFalse(report['passed'])

    def test_empty_verification_cannot_approve_a_release(self):
        self.assertFalse(gate.run_checks([])['passed'])
        self.assertFalse(self.receipt.exists())

    def test_changed_build_configuration_or_catalog_revokes_approval(self):
        probes = self.root / 'probes'
        probes.mkdir()
        (probes / 'provider-demos.json').write_text('[]')
        gate.run_checks([('pass', self.command('pass'))])
        self.assertTrue(gate.verified())
        (probes / 'flashscore-cache.json').write_text('runtime data')
        self.assertTrue(gate.verified())
        (probes / 'provider-demos.json').write_text('[{}]')
        self.assertFalse(gate.verified())
        gate.run_checks([('pass', self.command('pass'))])
        (self.root / '.dockerignore').write_text('demo')
        self.assertFalse(gate.verified())

    def test_invalid_receipt_shapes_are_not_approvals(self):
        self.receipt.parent.mkdir()
        for value in ([], None, True, 'invalid', {'passed': True, 'source': 'old'}):
            with self.subTest(value=value):
                self.receipt.write_text(json.dumps(value))
                self.assertFalse(gate.verified())

    def test_postgres_configuration_is_required_without_logging_the_url(self):
        import subprocess
        command = dict(gate.checks())['postgres-config']
        with patch.dict('os.environ', {}, clear=True):
            result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('isolated Postgres', result.stderr)


if __name__ == '__main__':
    unittest.main()
