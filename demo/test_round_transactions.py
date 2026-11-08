"""Exercise real round methods and their lock boundaries without SQL mocks."""
import tempfile
import threading
import unittest
from unittest.mock import patch

from demo.server import Demo


class ObservedLock:
    def __init__(self):
        self.lock = threading.RLock()
        self.depth = 0

    def __enter__(self):
        self.lock.acquire()
        self.depth += 1
        return self

    def __exit__(self, *args):
        self.depth -= 1
        self.lock.release()


class RoundBoundaryTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.demo = Demo(directory.name)
        self.demo.players.write_all({'p': {}, 'q': {}})
        for player in ('p', 'q'):
            self.demo.books.deposit('seed-' + player, player, 10000)

    def bet(self, player='p', bet_id='shared-id'):
        return self.demo.bet({'player': player, 'fixture_key': 'synthetic',
                              'selection': 'Home', 'price': 2.0,
                              'stake_minor': 200, 'bet_id': bet_id})

    def test_identical_bet_ids_from_different_players_both_settle(self):
        self.bet('p')
        self.bet('q')
        settled = self.demo.settle_pending(settle_delay_seconds=0)
        self.assertEqual({row['player'] for row in settled}, {'p', 'q'})
        self.assertEqual(len(settled), 2)
        self.assertEqual(self.demo.settle_pending(settle_delay_seconds=0), [])

    def test_previously_settled_player_does_not_hide_another_players_bet(self):
        self.bet('p')
        self.demo.settle_pending(settle_delay_seconds=0)
        self.bet('q')
        settled = self.demo.settle_pending(settle_delay_seconds=0)
        self.assertEqual([row['player'] for row in settled], ['q'])

    def test_stale_pending_snapshot_does_not_post_a_second_settlement(self):
        self.bet()
        pending = self.demo._all_rounds()
        self.demo.settle_pending(settle_delay_seconds=0)
        count = len(self.demo.books.postings)
        with patch.object(self.demo, '_all_rounds', return_value=pending):
            self.assertEqual(self.demo.settle_pending(settle_delay_seconds=0), [])
        self.assertEqual(len(self.demo.books.postings), count)

    def test_durable_round_history_is_written_before_outer_lock_exits(self):
        lock = ObservedLock()
        self.demo.books._lock = lock
        # This sentinel selects the durable wrapper; the real SQL transaction
        # rollback contract is covered separately in test_persistence.
        self.demo.round_log = object()
        def append(row):
            self.assertGreater(lock.depth, 0, 'history escaped wallet transaction')
            return True
        with patch.object(self.demo, '_append_round', side_effect=append) as history:
            self.demo.spin({'player': 'p', 'game_id': 'demo:neon-gems',
                            'stake_minor': 200, 'round_id': 'slot'})
            self.demo.spin({'player': 'p', 'game_id': 'demo:roulette-europeia',
                            'stake_minor': 200, 'round_id': 'roulette', 'selection': 'red'})
            self.demo.spin({'player': 'p', 'game_id': 'demo:plinko-drops',
                            'stake_minor': 200, 'round_id': 'plinko'})
            self.bet()
            self.demo.settle_rgs_round('p', 'provider:test', 'rgs-round', 200, 100)
            self.demo.books.place_bet('demo:wdebit:provider:test:credit-round', 'p', 200, '2.00')
            with patch.object(self.demo, '_wallet_session', return_value={'player': 'p', 'game_id': 'provider:test'}):
                self.demo.wallet_credit({'round_id': 'credit-round', 'payout_minor': 100})
            self.assertEqual(history.call_count, 6)

    def test_sports_settlement_history_is_inside_wallet_lock(self):
        self.bet()
        lock = ObservedLock()
        self.demo.books._lock = lock
        original = self.demo._append_round
        def append(row):
            self.assertGreater(lock.depth, 0)
            return original(row)
        with patch.object(self.demo, '_append_round', side_effect=append):
            self.assertEqual(len(self.demo.settle_pending(settle_delay_seconds=0)), 1)


if __name__ == '__main__':
    unittest.main()
