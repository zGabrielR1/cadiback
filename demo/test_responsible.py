"""Responsible-play limits, post-exclusion cooldown and promo opt-out."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from demo.server import Demo


class ResponsiblePlayTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.demo = Demo(data_dir=self.temp.name)
        self.player = self.demo.register_player({
            'name': 'Ana Souza', 'username': 'ana.souza',
            'email': 'ana.souza@example.com', 'cpf': '529.982.247-25',
            'password': 'ana1234', 'pix_key': 'ana.souza@example.com',
            'bank': {'bank_code': '001', 'agency': '1234',
                     'account': '56789-0', 'holder_name': 'Ana Souza'}},
            device=None)['player_id']
        self.demo.deposit({'player': self.player, 'amount_minor': 10000,
                           'method': 'pix', 'deposit_id': 'dep-1'})

    def test_deposit_limit_blocks_next_deposit(self):
        self.demo.set_limits(self.player, {'deposit_daily_minor': 10000})
        with self.assertRaisesRegex(ValueError, 'limite diário de depósito'):
            self.demo.deposit({'player': self.player, 'amount_minor': 1,
                               'method': 'pix', 'deposit_id': 'dep-2'})
        view = self.demo.responsible_view(self.player)
        self.assertEqual(view['limits']['deposit_daily_minor'], 10000)
        self.assertEqual(view['today']['deposited_minor'], 10000)

    def test_bet_limit_blocks_spins_and_view_reports_today(self):
        self.demo.set_limits(self.player, {'bet_daily_minor': 100})
        view = self.demo.responsible_view(self.player)
        self.assertEqual(view['today']['staked_minor'], 0)
        with self.assertRaisesRegex(ValueError, 'limite diário de apostas'):
            self.demo.spin({'player': self.player,
                            'game_id': 'demo:neon-gems',
                            'stake_minor': 200})

    def test_clearing_limits_removes_the_cap(self):
        self.demo.set_limits(self.player, {'deposit_daily_minor': 10000})
        self.demo.set_limits(self.player, {'deposit_daily_minor': None})
        self.assertIsNone(self.demo.responsible_view(self.player)['limits']['deposit_daily_minor'])
        self.demo.deposit({'player': self.player, 'amount_minor': 100,
                           'method': 'pix', 'deposit_id': 'dep-3'})

    def test_post_exclusion_cooldown_blocks_transactions(self):
        self.demo.self_exclude(self.player, '2030-01-01')
        with self.assertRaises(Exception):
            self.demo.deposit({'player': self.player, 'amount_minor': 100,
                               'method': 'pix', 'deposit_id': 'dep-4'})
        self.demo.lift_exclusion(self.player)
        self.assertTrue(self.demo.responsible_view(self.player)['in_cooldown'])
        with self.assertRaises(Exception):
            self.demo.deposit({'player': self.player, 'amount_minor': 100,
                               'method': 'pix', 'deposit_id': 'dep-5'})
        registry = self.demo.exclusions
        # simulate the cooldown expiring
        for player in list(registry.cooldowns):
            registry.cooldowns[player] = (datetime.now(timezone.utc) -
                                          timedelta(hours=25)).isoformat(timespec='seconds')
        self.assertFalse(self.demo.responsible_view(self.player)['in_cooldown'])

    def test_promo_optout_blocks_claims_and_reports_progress(self):
        res = self.demo.claim_bonus({'player': self.player, 'kind': 'welcome'})
        self.assertEqual(res['kind'], 'welcome')
        self.demo.set_promo_optout(self.player, True)
        view = self.demo._bonus_view(self.player)
        self.assertTrue(view['opt_out'])
        self.assertEqual(view['event']['remaining_minor'], view['event']['target_minor'])
        with self.assertRaisesRegex(ValueError, 'promoções desativadas'):
            self.demo.claim_bonus({'player': self.player, 'kind': 'cashback'})


if __name__ == '__main__':
    unittest.main()
