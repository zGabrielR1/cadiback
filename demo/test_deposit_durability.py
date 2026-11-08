"""Deposit limits and failed acknowledgement retries without live providers."""
from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace

from demo.server import Demo


class DepositDurabilityTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.demo = Demo(self.directory.name)
        self.demo.limits.deposit_daily = 15000

    def deposit(self, demo=None, amount=10000, deposit_id='first', player='p'):
        return (demo or self.demo).deposit({'player': player, 'amount_minor': amount,
                                           'deposit_id': deposit_id, 'method': 'pix'})

    def test_restart_cannot_reset_daily_limit(self):
        self.deposit()
        revived = Demo(self.directory.name)
        revived.limits.deposit_daily = 15000
        self.assertEqual(revived._deposited_today('p'), 10000)
        with self.assertRaises(ValueError):
            self.deposit(revived, amount=5001, deposit_id='over-cap')
        self.deposit(revived, amount=5000, deposit_id='remaining')
        self.assertEqual(revived.books.available('p'), 15000)

    def test_replays_withdrawals_bonuses_and_other_players_do_not_change_deposit_total(self):
        self.deposit()
        self.assertTrue(self.deposit()['replayed'])
        self.demo.books.withdraw('withdraw', 'p', 1000)
        self.demo.books.grant_bonus('bonus', 'p', 500)
        self.deposit(amount=3000, deposit_id='other', player='q')
        self.assertEqual(self.demo._deposited_today('p'), 10000)

    def test_totals_normalize_timezone_offsets_to_utc_day(self):
        today = datetime.now(timezone.utc).replace(hour=0, minute=30, second=0, microsecond=0)
        previous_local_day = today.astimezone(timezone(timedelta(hours=-3)))
        with patch.object(self.demo.books, '_clock', return_value=previous_local_day.isoformat()):
            self.deposit()
        self.assertEqual(self.demo._deposited_today('p'), 10000)

    def test_old_or_invalid_timestamps_do_not_silently_reset_limits(self):
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        with patch.object(self.demo.books, '_clock', return_value=yesterday.isoformat()):
            self.deposit()
        self.assertEqual(self.demo._deposited_today('p'), 0)
        with patch.object(self.demo.books, '_clock', return_value='invalid'):
            self.demo.books.deposit('bad-timestamp', 'p', 100)
        with self.assertRaises(ValueError):
            self.deposit(amount=100, deposit_id='must-not-bypass')

    def test_failed_payment_acknowledgement_can_retry_without_double_credit(self):
        for rail in ('asaas', 'crypto'):
            with self.subTest(rail=rail):
                directory = tempfile.TemporaryDirectory()
                self.addCleanup(directory.cleanup)
                demo = Demo(directory.name)
                row = {'deposit_id': 'paid', 'player': 'p', 'amount_minor': 10000,
                       'provider_ref': 'provider-ref', 'provider_status': 'PENDING', 'posted': False}
                put = demo._put_charge if rail == 'asaas' else demo._put_crypto_charge
                confirm = demo._confirm_asaas_charge if rail == 'asaas' else demo._confirm_crypto_charge
                put(row)
                name = '_save_asaas_charges' if rail == 'asaas' else '_save_crypto_charges'
                with patch.object(demo, name, side_effect=OSError('disk unavailable')):
                    with self.assertRaises(OSError):
                        confirm('paid', row)
                self.assertFalse(row['posted'])
                stored = demo.asaas_charges if rail == 'asaas' else demo.crypto_charges
                self.assertFalse(stored['paid']['posted'])
                self.assertEqual(demo.books.available('p'), 10000)
                self.assertEqual(demo._deposited_today('p'), 10000)
                confirm('paid', row)
                self.assertTrue(row['posted'])
                self.assertEqual(demo.books.available('p'), 10000)
                self.assertEqual(len(demo.books.postings), 1)
                revived = Demo(directory.name)
                stored = revived.asaas_charges if rail == 'asaas' else revived.crypto_charges
                self.assertTrue(stored['paid']['posted'])
                self.assertEqual(revived._deposited_today('p'), 10000)

    def test_conflicting_invoice_reference_is_refused_before_provider_call(self):
        self.demo.players.write_all({'p': {}, 'q': {}})
        row = {'deposit_id': 'same', 'player': 'p', 'amount_minor': 10000,
               'provider_ref': 'reference', 'provider_status': 'PENDING', 'posted': False}
        for rail in ('asaas', 'crypto'):
            client = SimpleNamespace(create_pix_charge=Mock(), create_payment=Mock())
            setattr(self.demo, rail, client)
            put = self.demo._put_charge if rail == 'asaas' else self.demo._put_crypto_charge
            create = self.demo.create_pix_deposit if rail == 'asaas' else self.demo.create_crypto_deposit
            put(row)
            for player, amount in (('q', 10000), ('p', 20000)):
                with self.subTest(rail=rail, player=player, amount=amount), self.assertRaises(ValueError):
                    create({'player': player, 'amount_minor': amount, 'deposit_id': 'same',
                            'method': 'pix' if rail == 'asaas' else 'crypto', 'pay_currency': 'btc'})
            client.create_pix_charge.assert_not_called()
            client.create_payment.assert_not_called()


if __name__ == '__main__':
    unittest.main()
