"""Portable backup validation and incomplete-cutover regressions."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
import os
import stat

from frame.wallet.books import Books, BalanceError
from scripts.wallet_backup import digest, load_files, make_backup, validate, write_backup


class BackupValidationTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        books = Books(str(Path(directory.name, 'books.jsonl')))
        books.deposit('deposit', 'p', 1200)
        books.withdraw('withdraw', 'p', 200)
        self.payload = {
            'runtime:books': {'postings': [p.as_dict() for p in books.postings]},
            'runtime:rounds': {'rows': [{'round_id': 'r', 'player': 'p'}]},
            'promos': {'p': {'claimed': True}},
            'crash_pending': {},
        }

    def signed(self, payload):
        return {'format': 1, 'payload': payload, 'sha256': digest(payload)}

    def test_valid_round_trip_preserves_every_document_and_is_detached(self):
        backup = make_backup(self.payload)
        self.assertEqual(validate(json.loads(json.dumps(backup))), self.payload)
        self.payload['promos']['p']['claimed'] = False
        self.assertTrue(backup['payload']['promos']['p']['claimed'])

    def test_empty_backup_requires_explicit_allowance(self):
        with self.assertRaises(ValueError):
            make_backup({})
        self.assertEqual(validate(make_backup({}, allow_empty=True)),
                         {'runtime:books': {'postings': []}})

    def test_partial_cutover_is_never_replaced_with_empty_books(self):
        for name in ('runtime:rounds', 'promos', 'crash_pending', 'crypto_charges', 'asaas_charges', 'publisher_state'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                make_backup({name: self.payload.get(name, {})}, allow_empty=True)

    def test_asaas_charges_validate_and_reject_partial_cutovers(self):
        payload = deepcopy(self.payload)
        payload['asaas_charges'] = {'pix-9': {'deposit_id': 'pix-9', 'player': 'p',
                                               'amount_minor': 200, 'provider_ref': 'pay_9',
                                               'provider_status': 'PENDING', 'posted': False}}
        backup = make_backup(payload)
        self.assertEqual(validate(json.loads(json.dumps(backup)))['asaas_charges']['pix-9']['provider_ref'], 'pay_9')
        with self.assertRaises(ValueError):
            make_backup({'asaas_charges': payload['asaas_charges']}, allow_empty=True)
        broken = deepcopy(payload)
        broken['asaas_charges']['pix-9']['amount_minor'] = -1
        with self.assertRaises(ValueError):
            make_backup(broken)

    def test_crypto_publisher_and_asaas_state_are_preserved_in_private_backup_files(self):
        payload = deepcopy(self.payload)
        payload['crypto_charges'] = {'invoice': {'deposit_id': 'invoice', 'player': 'p',
                                                'amount_minor': 200, 'provider_ref': 'ref', 'posted': False}}
        payload['publisher_state'] = {'tokens': {'bearer-token': {'player': 'p', 'game_id': 'g', 'issued_at': 'timestamp'}}}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory, 'wallet.json')
            write_backup(target, make_backup(payload))
            self.assertEqual(validate(json.loads(target.read_text())), payload)
            if os.name == 'posix':
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                write_backup(target, make_backup(payload))
        payload['crypto_charges']['invoice']['amount_minor'] = True
        with self.assertRaises(ValueError):
            make_backup(payload)

    def test_malformed_envelopes_and_documents_are_rejected(self):
        for envelope in (None, [], {}, {'format': True}, {'format': 2}):
            with self.subTest(envelope=envelope), self.assertRaises(ValueError):
                validate(envelope)
        for name, value in (
                ('runtime:books', None), ('runtime:books', {}),
                ('runtime:rounds', []), ('runtime:rounds', {'rows': [None]}),
                ('promos', []), ('crash_pending', None), ('unknown', {})):
            payload = deepcopy(self.payload)
            payload[name] = value
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                validate(self.signed(payload))

    def test_checksum_and_posting_invariants_are_independent(self):
        backup = make_backup(self.payload)
        backup['payload']['promos']['p']['claimed'] = False
        with self.assertRaisesRegex(ValueError, 'checksum'):
            validate(backup)
        for field, value in (('seq', True), ('seq', 3), ('key', ''), ('metadata', [])):
            payload = deepcopy(self.payload)
            payload['runtime:books']['postings'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(self.signed(payload))
        payload = deepcopy(self.payload)
        payload['runtime:books']['postings'][1]['key'] = 'deposit'
        with self.assertRaises(ValueError):
            validate(self.signed(payload))
        payload = deepcopy(self.payload)
        payload['runtime:books']['postings'][0]['legs'][0]['amount'] += 1
        with self.assertRaises(BalanceError):
            validate(self.signed(payload))

    def test_legacy_file_import_preserves_all_runtime_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'books.jsonl').write_text('\n'.join(
                json.dumps(row) for row in self.payload['runtime:books']['postings']))
            (root / 'rounds.jsonl').write_text(json.dumps(self.payload['runtime:rounds']['rows'][0]))
            for name in ('promos', 'crash_pending'):
                (root / (name + '.json')).write_text(json.dumps(self.payload[name]))
            self.assertEqual(validate(load_files(root)), self.payload)

    def test_legacy_file_import_preserves_asaas_charges(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'books.jsonl').write_text('\n'.join(
                json.dumps(row) for row in self.payload['runtime:books']['postings']))
            (root / 'rounds.jsonl').write_text(json.dumps(self.payload['runtime:rounds']['rows'][0]))
            (root / 'asaas_charges.json').write_text(json.dumps(
                {'pix-9': {'deposit_id': 'pix-9', 'player': 'p', 'amount_minor': 200,
                           'provider_ref': 'pay_9', 'posted': False}}))
            loaded = validate(load_files(root))
            self.assertEqual(loaded['asaas_charges']['pix-9']['provider_ref'], 'pay_9')

    def test_check_command_validates_offline_without_loading_database_libraries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'backup.json')
            path.write_text(json.dumps(make_backup(self.payload)))
            # Running with -S removes installed site packages, proving that
            # offline validation has no SQLAlchemy/driver dependency.
            result = subprocess.run(
                [sys.executable, '-S', '-m', 'scripts.wallet_backup', '--check', str(path)],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('2 balanced postings', result.stdout)
            broken = make_backup(self.payload)
            broken['sha256'] = 'invalid'
            path.write_text(json.dumps(broken))
            result = subprocess.run(
                [sys.executable, '-S', '-m', 'scripts.wallet_backup', '--check', str(path)],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('Backup valid', result.stdout)


if __name__ == '__main__':
    unittest.main()
