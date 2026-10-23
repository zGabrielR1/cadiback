import copy
import tempfile
import unittest

from demo.sports_quotes import SportsQuoteError, quote_legs, require_same_prices
from demo.server import Demo


class SportsQuotesTest(unittest.TestCase):
    def setUp(self):
        self.board = {'source': 'test', 'fixtures': [{'key': 'test:1', 'status': 'SCHEDULED', 'home': 'Casa', 'away': 'Fora', 'competition': 'Teste', 'markets': [{'kind': '1x2', 'selections': ['Casa', 'Empate', 'Fora'], 'prices': [2.0, 3.0, 4.0]}]}]}
        self.legs = [{'fixture_key': 'test:1', 'market_kind': '1x2', 'selection': 'Casa', 'price': 2.0}]

    def test_canonical_names_and_prices(self):
        self.legs[0]['home'] = 'untrusted'
        result = quote_legs(self.legs, self.board)
        self.assertEqual(result['legs'][0]['home'], 'Casa')
        self.assertEqual(result['total_price'], 2.0)
        require_same_prices(self.legs, result)

    def test_changed_price_requires_explicit_review(self):
        self.legs[0]['price'] = 100
        with self.assertRaises(SportsQuoteError) as error:
            require_same_prices(self.legs, quote_legs(self.legs, self.board))
        self.assertEqual(error.exception.code, 'odds_changed')
        self.assertEqual(error.exception.details['legs'][0]['price'], 2)

    def test_same_match_and_unavailable_rejected(self):
        with self.assertRaises(SportsQuoteError):
            quote_legs(self.legs * 2, self.board)
        for status in ['FINAL', 'FT', 'SUSPENDED', 'POSTPONED']:
            self.board['fixtures'][0]['status'] = status
            with self.assertRaises(SportsQuoteError):
                quote_legs(self.legs, self.board)

    def test_unknown_selection_line_and_invalid_prices(self):
        for mutation in [{'selection': 'invented'}, {'line': 2.5}, {'fixture_key': 'missing'}]:
            with self.assertRaises(SportsQuoteError):
                quote_legs([{**self.legs[0], **mutation}], self.board)
        for price in [True, float('nan'), 1, 1001, '2.0']:
            board = copy.deepcopy(self.board)
            board['fixtures'][0]['markets'][0]['prices'][0] = price
            with self.assertRaises(SportsQuoteError):
                quote_legs(self.legs, board)

    def test_gateway_checks_before_debit_and_replays_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            demo = Demo(data_dir=directory)
            player = demo.upsert_player({'name': 'Ana Souza', 'cpf': '529.982.247-25', 'pix_key': 'ana@example.com', 'bank': {'bank_code': '001', 'agency': '1234', 'account': '56789-0', 'holder_name': 'Ana Souza'}})['player_id']
            demo.deposit({'player': player, 'amount_minor': 10000, 'method': 'pix', 'deposit_id': 'quote-deposit'})
            demo.sports_showcase = lambda: self.board
            payload = {'player': player, 'legs': self.legs, 'stake_minor': 500, 'bet_id': 'quote-accepted'}
            with self.assertRaises(SportsQuoteError):
                demo.place_sports_bet({**payload, 'legs': [{**self.legs[0], 'price': 9}]})
            self.assertEqual(demo.books.available(player), 10000)
            receipt = demo.place_sports_bet(payload)
            self.assertEqual(demo.books.available(player), 9500)
            self.board['fixtures'] = []
            self.assertEqual(demo.place_sports_bet(payload)['round_id'], receipt['round_id'])
            self.assertEqual(demo.books.available(player), 9500)
            with self.assertRaises(SportsQuoteError):
                demo.place_sports_bet({**payload, 'stake_minor': 600})
