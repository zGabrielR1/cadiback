import base64
import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from fractions import Fraction
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from urllib.parse import quote

from demo import game_proxy, pg_proxy, provider_demos
from demo.arcade import (ARCADE_GAME_IDS, KENO_DRAWN, KENO_MAX_SPOTS,
                         KENO_MIN_SPOTS, KENO_POOL, KENO_GAME_ID,
                         keno_draw, keno_multiplier, keno_paytable,
                         keno_hit_probability, keno_payout,
                         keno_realised_rtp, keno_rtp,
                         keno_round, parse_keno_selection)
from demo.arcade import theoretical_rtp as arcade_theoretical_rtp
from demo.server import DEMO_CATEGORY
from demo.auth import AuthError
from demo.payments import (
    PaymentError,
    check_deposit_method,
    classify_pix_key,
    mask_pix_key,
    process_deposit,
    process_withdrawal,
    validate_bank_account,
    validate_cpf,
    validate_email,
    validate_player_password,
)
from demo.server import (
    DEMO,
    Demo,
    Handler,
    external_demo_url,
    fixture_catalog,
    static_file,
)
from demo.risk import (
    RiskPolicy,
    check_duplicate_round,
    check_loss_chase,
    check_rtp_deviation,
    check_stake_spike,
    check_velocity,
    evaluate_player,
)
from demo.slot import DEMO_RTP, spin, theoretical_rtp
from demo.vendor import AggregatorError, VendorAggregator, VendorConfig
from frame.compliance.sigap import ExclusionError, ExclusionRegistry, Limits
from frame.wallet.books import Books, DuplicatePosting, WalletError


class CpfTest(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_cpf("529.982.247-25"), "52998224725")

    def test_invalid(self):
        with self.assertRaises(PaymentError):
            validate_cpf("111.111.111-11")
        with self.assertRaises(PaymentError):
            validate_cpf("123")


class PixTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(classify_pix_key("529.982.247-25").kind, "cpf")
        self.assertEqual(classify_pix_key("ana.souza@example.com").kind, "email")
        self.assertEqual(classify_pix_key("+5511999998888").kind, "phone")
        self.assertEqual(
            classify_pix_key("123e4567-e89b-12d3-a456-426614174000").kind, "evp")

    def test_garbage_rejected(self):
        with self.assertRaises(PaymentError):
            classify_pix_key("not-a-key")
        with self.assertRaises(PaymentError):
            classify_pix_key("")

    def test_masking_hides_personal_data(self):
        self.assertNotIn("52998224725", mask_pix_key("52998224725"))
        self.assertIn("***", mask_pix_key("ana.souza@example.com"))


class BankTest(unittest.TestCase):
    def test_own_name_rule(self):
        validate_bank_account("001", "1234", "56789-0", "Ana Souza", "Ana Souza")
        with self.assertRaises(PaymentError):
            validate_bank_account("001", "1234", "56789-0", "Bob Silva", "Ana Souza")
        with self.assertRaises(PaymentError):
            validate_bank_account("01", "1234", "56789-0", "Ana Souza", "Ana Souza")

    def test_prohibited_methods_rejected_by_name(self):
        for method in ("credit", "crypto", "pix_credito", "boleto"):
            with self.assertRaises(PaymentError):
                check_deposit_method(method)
        self.assertEqual(check_deposit_method("pix"), "pix")


class SlotTest(unittest.TestCase):
    def test_probabilities_sum_to_one_and_rtp(self):
        from demo.slot import TIERS
        self.assertAlmostEqual(sum(t.probability for t in TIERS), 1.0, places=9)
        self.assertAlmostEqual(theoretical_rtp(), DEMO_RTP, places=9)
        self.assertAlmostEqual(DEMO_RTP, 0.959, places=3)

    def test_deterministic(self):
        first = spin("demo:neon-gems", "round:abc")
        second = spin("demo:neon-gems", "round:abc")
        self.assertEqual(first, second)
        other = spin("demo:neon-gems", "round:abd")
        self.assertIsNotNone(other.tier)


class DemoE2ETest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)

    def _register(self, name="Ana Souza", cpf="529.982.247-25",
                  pix="ana.souza@example.com", account="56789-0"):
        return self.demo.upsert_player({
            "name": name, "cpf": cpf, "pix_key": pix,
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": account, "holder_name": name},
        })["player_id"]

    def test_full_path_deposit_spin_withdraw_balanced(self):
        player = self._register()
        self.demo.deposit({"player": player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "e2e-dep"})
        self.assertEqual(self.demo.books.available(player), 10000)
        row = self.demo.spin({"player": player, "game_id": "demo:neon-gems",
                              "stake_minor": 500, "round_id": "e2e0001"})
        self.assertIn("tier", row)
        receipt = self.demo.withdraw({
            "player": player, "amount_minor": 200, "payout_id": "e2e-wd-1"})
        self.assertEqual(receipt["status"][:4], "paid")
        self.demo.books.assert_balanced()

    def test_sports_bet_settles_through_books_and_history(self):
        player = self._register()
        self.demo.deposit({"player": player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "bet-dep"})
        row = self.demo.bet({
            "player": player, "fixture_key": "demo:fl-1",
            "home": "Anjos", "away": "Tubarões", "competition": "Liga Demo",
            "market_kind": "1X2", "selection": "Anjos", "price": 2.0,
            "stake_minor": 500, "bet_id": "bet-001",
        })
        self.assertEqual(row["tier"], "pendente")
        self.assertEqual(row["type"], "sports")
        self.assertEqual(row["payout_minor"], 0)
        settled = self.demo.settle_pending(settle_delay_seconds=0)
        self.assertEqual(len(settled), 1)
        final = settled[0]
        self.assertIn(final["tier"], ("vitoria", "derrota"))
        self.assertEqual(final["payout_minor"], 1000 if final["tier"] == "vitoria" else 0)
        self.assertEqual(final["available_minor"], self.demo.books.available(player))
        with open(self.demo.rounds_path, encoding="utf-8") as f:
            rows = [l for l in f.read().splitlines() if l.strip()]
        self.assertTrue(any('"bet-001"' in l for l in rows))
        hist = self.demo.history(player)
        self.assertEqual(len([r for r in hist if r["round_id"] == "bet-001"]), 1)
        self.assertEqual(hist[0]["tier"], final["tier"])
        again = self.demo.settle_pending(settle_delay_seconds=0)
        self.assertEqual(again, [])
        with self.assertRaises(ValueError):
            self.demo.bet({"player": player, "fixture_key": "demo:fl-1",
                           "selection": "Anjos", "price": 2.0,
                           "stake_minor": 500, "bet_id": "bet-001"})
        with self.assertRaises(ValueError):
            self.demo.bet({"player": player, "fixture_key": "demo:fl-1",
                           "selection": "Anjos", "price": 1.0,
                           "stake_minor": 500, "bet_id": "bet-002"})
        self.demo.books.assert_balanced()

    def test_express_bet_multiplies_legs(self):
        player = self._register()
        self.demo.deposit({"player": player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "acc-dep"})
        row = self.demo.bet({
            "player": player, "stake_minor": 500, "bet_id": "acc-1",
            "legs": [
                {"fixture_key": "f1", "selection": "Casa", "price": 2.0,
                 "home": "Anjos", "away": "Tubarões", "market_kind": "1x2"},
                {"fixture_key": "f2", "selection": "Empate", "price": 3.0,
                 "home": "Lobos", "away": "Falcões", "market_kind": "1x2"},
            ],
        })
        self.assertEqual(float(row["multiplier"]), 6.0)
        self.assertEqual(row["type"], "sports")
        self.assertEqual(row["tier"], "pendente")
        with self.assertRaises(ValueError):
            self.demo.bet({"player": player, "stake_minor": 500, "bet_id": "acc-2",
                           "legs": [{"fixture_key": "f1", "selection": "X", "price": 0.5}]})
        self.demo.books.assert_balanced()

    def test_deposit_replay_does_not_double_credit(self):
        player = self._register()
        first = self.demo.deposit({"player": player, "amount_minor": 10000,
                                   "method": "pix", "deposit_id": "same"})
        second = self.demo.deposit({"player": player, "amount_minor": 10000,
                                    "method": "pix", "deposit_id": "same"})
        self.assertFalse(first["replayed"])
        self.assertTrue(second["replayed"])
        self.assertEqual(self.demo.books.available(player), 10000)

    def test_payout_refuses_foreign_pix_key(self):
        player = self._register()
        self.demo.deposit({"player": player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "d"})
        with self.assertRaises(ValueError):
            self.demo.withdraw({
                "player": player, "amount_minor": 1000,
                "pix_key": "attacker@evil.example", "payout_id": "w"})
        self.assertEqual(self.demo.books.available(player), 10000)
        self.demo.books.assert_balanced()

    def test_daily_cap_rolls_over(self):
        player = self._register()
        self.demo.limits.deposit_daily = 15000
        self.demo.deposit({"player": player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "a"})
        self.demo.deposit({"player": player, "amount_minor": 5000,
                           "method": "pix", "deposit_id": "b"})
        with self.assertRaises(ValueError):
            self.demo.deposit({"player": player, "amount_minor": 1,
                               "method": "pix", "deposit_id": "c"})
        self.demo.deposit_days[player] = {"day": "2020-01-01", "total": 999}
        self.demo.deposit({"player": player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "d"})

    def test_one_wallet_per_cpf(self):
        first = self._register(name="Ana Souza")
        second = self._register(name="ana souza")
        self.assertEqual(first, second)

    def test_exclusion_survives_restart_and_expires(self):
        from datetime import date
        player = self._register()
        self.demo.self_exclude(player, "2030-01-01")
        revived = Demo(data_dir=self.demo.players.path.rsplit(os.sep, 1)[0])
        self.assertTrue(revived.exclusions.active(player))
        with self.assertRaises(Exception):
            revived.deposit({"player": player, "amount_minor": 100,
                             "method": "pix", "deposit_id": "x"})
        revived.exclusions.self_declared[player] = "2020-01-01"
        self.assertFalse(revived.exclusions.active(player, today=date.today()))
        revived.deposit({"player": player, "amount_minor": 100,
                         "method": "pix", "deposit_id": "y"})

    def test_torn_round_line_does_not_break_history(self):
        player = self._register()
        self.demo.deposit({"player": player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "d"})
        self.demo.spin({"player": player, "game_id": "demo:neon-gems",
                        "stake_minor": 500, "round_id": "r1"})
        with open(self.demo.rounds_path, "a", encoding="utf-8") as handle:
            handle.write('{"round_id": "half-writ')
        self.assertEqual(len(self.demo.history(player)), 1)
        self.assertEqual(self.demo.risk(player)["stats"]["rounds"], 1.0)

    def test_uncertified_game_blocked(self):
        self.demo.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })
        player = "ana-souza"
        self.demo.deposit({"player": player, "amount_minor": 10000, "method": "pix"})
        with self.assertRaises(Exception):
            self.demo.spin({"player": player, "game_id": "demo:royale-roulette",
                            "stake_minor": 500, "round_id": "blocked1"})

    def test_excluded_player_blocked_everywhere(self):
        self.demo.upsert_player({
            "name": "Bruno Lima", "cpf": "529.982.247-25",
            "pix_key": "bruno@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "11111-1", "holder_name": "Bruno Lima"},
        })
        player = "bruno-lima"
        self.demo.exclusions.self_exclude(player, "2027-01-01")
        with self.assertRaises(Exception):
            self.demo.deposit({"player": player, "amount_minor": 1000, "method": "pix"})
        with self.assertRaises(Exception):
            self.demo.withdraw({"player": player, "amount_minor": 100,
                                "pix_key": "bruno@example.com",
                                "holder_name": "Bruno Lima", "payout_id": "x1"})

    def test_withdrawal_uses_registered_key_only(self):
        books = Books(os.path.join(self.tmp, "b2.jsonl"))
        books.deposit("dep:1", "ana", 5000)
        # funds only leave to the key on file; there is no caller-supplied
        # destination to argue with
        receipt = process_withdrawal(
            books, ExclusionRegistry(), "ana", 100, "ana@example.com", "p1")
        self.assertEqual(receipt["pix_kind"], "email")
        self.assertEqual(books.available("ana"), 4900)
        with self.assertRaises(PaymentError):
            process_withdrawal(books, ExclusionRegistry(), "ana", 100, "", "p2")

    def test_withdrawal_replay_is_idempotent(self):
        books = Books(os.path.join(self.tmp, "b3.jsonl"))
        books.deposit("dep:1", "ana", 5000)
        first = process_withdrawal(
            books, ExclusionRegistry(), "ana", 100, "ana@example.com", "same")
        self.assertIsNotNone(first)
        again = process_withdrawal(
            books, ExclusionRegistry(), "ana", 100, "ana@example.com", "same")
        self.assertIsNone(again)
        self.assertEqual(books.available("ana"), 4900)
        books.assert_balanced()


def fake_transport_factory(routes):
    def fake(url, api_key, payload, timeout):
        assert api_key == "k-test", api_key
        for suffix, response in routes.items():
            if url.endswith(suffix):
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"unexpected vendor call: {url}")
    return fake


class VendorTest(unittest.TestCase):
    def _config(self):
        return VendorConfig(vendor="everymatrix", base_url="https://sandbox.example",
                            api_key="k-test")

    def test_from_env_requires_all_three(self):
        with self.assertRaises(AggregatorError):
            VendorConfig.from_env({})
        config = VendorConfig.from_env({"DEMO_AGGREGATOR": "softswiss",
                                        "DEMO_API_URL": "https://x.example/",
                                        "DEMO_API_KEY": "k"})
        self.assertEqual(config.vendor, "softswiss")
        self.assertEqual(config.base_url, "https://x.example")

    def test_catalogue_lists_but_server_keeps_titles_gated(self):
        agg = VendorAggregator(
            self._config(),
            transport=fake_transport_factory({
                "/catalogue": {"games": [
                    {"game_id": "pp:real-game", "provider": "pragmatic_play",
                     "title": "Real Game", "rtp": "96.50"}]}}))
        games = agg.catalogue()
        self.assertEqual(games[0]["game_id"], "pp:real-game")
        demo = Demo(data_dir=tempfile.mkdtemp())
        demo.vendor = agg
        merged = demo.vendor_catalog()
        self.assertTrue(merged["status"].startswith("ok"))
        self.assertFalse(merged["games"][0]["launchable"])
        with self.assertRaises(Exception):  # no BR cert registered: no launch
            demo.spin({"player": "ana", "game_id": "pp:real-game",
                       "stake_minor": 500, "round_id": "v1"})

    def test_catalog_rows_carry_a_merchandising_category(self):
        """The lobby sidebar filters on `category`. It shipped filtering on a
        field the API never sent, so every category returned the same list.
        Enforced by execution so it cannot rot back into a no-op."""
        demo = Demo(data_dir=tempfile.mkdtemp())
        games = demo.catalog()
        self.assertTrue(games)
        for game in games:
            self.assertTrue(game.get("category"), game["game_id"])

    def test_fixture_rows_leave_forced_non_launchable(self):
        """No file on disk can launch a title. A fixture that claims
        launchable=true and a fantasy RTP must still come out gated."""
        import json
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "evil.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"titles": [
                {"game_id": "pp:evil", "provider": "pragmatic_play",
                 "title": "Evil", "rtp": "99.99", "launchable": True}]},
                      handle)
        merged = fixture_catalog(path)
        self.assertEqual(len(merged["games"]), 1)
        self.assertFalse(merged["games"][0]["launchable"])
        self.assertIn("BR", merged["games"][0]["note"])

    def test_fixture_errors_degrade_not_crash(self):
        missing = fixture_catalog("/nonexistent/vendor.json")
        self.assertEqual(missing["games"], [])
        self.assertTrue(missing["status"].startswith("fixture error"))
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "bad.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        bad = fixture_catalog(path)
        self.assertEqual(bad["games"], [])
        self.assertTrue(bad["status"].startswith("fixture error"))

    def test_credit_idempotent_and_errors_surfaced(self):
        agg = VendorAggregator(
            self._config(),
            transport=fake_transport_factory({"/wallet/credit": {"ok": True}}))
        self.assertTrue(agg.wallet_credit("round:9", 100))
        self.assertFalse(agg.wallet_credit("round:9", 100))
        down = VendorAggregator(
            self._config(),
            transport=fake_transport_factory(
                {"/catalogue": AggregatorError("boom")}))
        with self.assertRaises(AggregatorError):
            down.catalogue()


class ProviderDemoTest(unittest.TestCase):
    """The real vendor-content lane: publisher-hosted demos, their bytes."""

    def _write(self, rows):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "demos.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"demos": rows}, handle)
        return path

    def test_shipped_catalog_is_all_https_and_wallet_isolated(self):
        block = provider_demos.load()
        self.assertTrue(block["demos"], block["status"])
        for row in block["demos"]:
            self.assertTrue(row["demo_url"].startswith("https://"))
            self.assertIn(row["host"], provider_demos.DEMO_HOSTS)
            self.assertTrue(row["wallet_isolated"])
            self.assertFalse(row["launchable"])

    def test_http_and_unknown_host_rows_are_dropped(self):
        """A cleartext URL or a re-upload can never enter the lobby."""
        path = self._write([
            {"game_id": "a", "provider": "p", "title": "T",
             "demo_url": "http://demogamesfree.pragmaticplay.net/x"},
            {"game_id": "b", "provider": "p", "title": "T",
             "demo_url": "https://evil.example/game"},
            {"game_id": "c", "provider": "p", "title": "T",
             "demo_url": "https://static-live.hacksawgaming.com/1/1/index.html"},
        ])
        block = provider_demos.load(path)
        self.assertEqual([d["game_id"] for d in block["demos"]], ["c"])
        self.assertIn("dropped", block["status"])

    def test_missing_file_degrades_not_crash(self):
        block = provider_demos.load("/nonexistent/demos.json")
        self.assertEqual(block["demos"], [])
        self.assertIn("no provider-demo catalog", block["status"])

    def test_server_exposes_provider_demos_in_catalog(self):
        demo = Demo(data_dir=tempfile.mkdtemp())
        block = demo.provider_demos()
        self.assertTrue(block["demos"])
        self.assertTrue(block["status"])


def _round(player, rid, minute, stake=500, payout=0):
    return {"player": player, "round_id": rid, "game_id": "demo:neon-gems",
            "stake_minor": stake, "payout_minor": payout,
            "ts": f"2026-10-01T12:{minute:02d}:00+00:00"}


class RiskTest(unittest.TestCase):
    def test_clean_player_no_flags(self):
        policy = RiskPolicy(min_handle_for_rtp_minor=10 ** 12)
        rows = [_round("ana", f"r{i}", i, stake=500,
                       payout=500 if i % 2 else 0) for i in range(6)]
        report = evaluate_player("ana", rows, 0.959, policy)
        self.assertFalse(report.flagged)
        self.assertEqual(report.stats["rounds"], 6.0)

    def test_velocity_trips(self):
        policy = RiskPolicy(max_rounds_per_10min=3)
        rows = [_round("ana", f"r{i}", i) for i in range(5)]
        self.assertTrue(check_velocity(rows, policy))

    def test_stake_spike_trips(self):
        policy = RiskPolicy()
        rows = [_round("ana", f"r{i}", i, stake=500) for i in range(5)]
        rows.append(_round("ana", "r9", 9, stake=5000))
        self.assertTrue(check_stake_spike(rows, policy))

    def test_loss_chase_trips(self):
        policy = RiskPolicy(loss_chase_streak=3)
        rows = [_round("ana", f"r{i}", i, stake=500 + i * 100) for i in range(4)]
        self.assertTrue(check_loss_chase(rows, policy))

    def test_rtp_deviation_catches_payout_bug(self):
        policy = RiskPolicy(min_handle_for_rtp_minor=1000, rtp_tolerance=0.08)
        rows = [_round("ana", f"r{i}", i, stake=1000, payout=1000)
                for i in range(10)]  # realized 1.00 vs 0.959? no trip
        self.assertFalse(check_rtp_deviation(rows, 0.959, policy))
        rows = [_round("ana", f"r{i}", i, stake=1000, payout=2000)
                for i in range(10)]  # realized 2.00: double-credit class
        self.assertTrue(check_rtp_deviation(rows, 0.959, policy))

    def test_duplicate_round_trips(self):
        self.assertEqual(check_duplicate_round(["a", "b"]), [])
        self.assertTrue(check_duplicate_round(["a", "b", "a"]))

    def test_other_players_ignored(self):
        policy = RiskPolicy(max_rounds_per_10min=2)
        rows = [_round("bob", f"r{i}", i) for i in range(6)]
        self.assertFalse(evaluate_player("ana", rows, 0.959, policy).flagged)


class ExternalDemoTest(unittest.TestCase):
    def test_url_plumbing(self):
        self.assertIsNone(external_demo_url({}))
        self.assertIsNone(external_demo_url({"DEMO_IFRAME_URL": "http://x"}))
        self.assertEqual(
            external_demo_url({"DEMO_IFRAME_URL": "https://demo.provider.example/g"}),
            "https://demo.provider.example/g")



class ConcurrencyTest(unittest.TestCase):
    def test_concurrent_deposits_all_land(self):
        books = Books(os.path.join(tempfile.mkdtemp(), "b.jsonl"))
        books.deposit("dep:seed", "ana", 1000)
        errors: list[str] = []

        def work(index: int) -> None:
            try:
                books.deposit(f"dep:{index}", "ana", 1000)
            except DuplicatePosting:
                pass  # a duplicate key is a correct refusal, not a failure
            except Exception as exc:
                errors.append(type(exc).__name__)

        threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(books.available("ana"), 9000)
        replay = Books(books.path)
        self.assertEqual(replay.available("ana"), 9000)

    def test_concurrent_withdrawals_never_go_negative(self):
        books = Books(os.path.join(tempfile.mkdtemp(), "b.jsonl"))
        books.deposit("dep:seed", "ana", 1000)
        approved: list[int] = []

        def work(index: int) -> None:
            try:
                books.withdraw(f"wd:{index}", "ana", 400)
                approved.append(index)
            except WalletError:
                pass

        threads = [threading.Thread(target=work, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(approved), 2)
        self.assertGreaterEqual(books.available("ana"), 0)
        books.assert_balanced()


class StaticServeTest(unittest.TestCase):
    def test_drive_absolute_paths_refused(self):
        for attack in ("/C:/Windows/win.ini", "/c:\\\\Windows\\\\win.ini",
                       "//host/share/x", "/../../secrets.txt"):
            self.assertIsNone(static_file(attack), attack)

    def test_legitimate_page_served(self):
        asset = static_file("/")
        self.assertIsNotNone(asset)
        self.assertEqual(asset[1], "text/html")
        with open(asset[0], "r", encoding="utf-8") as handle:
            self.assertIn("Casa", handle.read())

    def test_next_export_preferred_when_built(self):
        with open(static_file("/index.html")[0], "r", encoding="utf-8") as handle:
            body = handle.read()
        self.assertTrue(body.count("_next/") > 0 or 'id="lobby"' in body,
                        "expected the Next export or the zero-build page")


class VendorUrlTest(unittest.TestCase):
    def test_base_url_must_be_https(self):
        cfg = {"DEMO_AGGREGATOR": "everymatrix", "DEMO_API_KEY": "k",
               "DEMO_API_URL": "http://sandbox.vendor.example"}
        with self.assertRaises(AggregatorError):
            VendorConfig.from_env(cfg)

    def test_credit_reserved_before_network_call(self):
        calls: list[str] = []

        def failing(url, api_key, payload, timeout):
            calls.append(url)
            raise OSError("network down")

        agg = VendorAggregator(
            VendorConfig(vendor="v", base_url="https://x.example", api_key="k"),
            transport=failing)
        with self.assertRaises(AggregatorError):
            agg.wallet_credit("round:1", 100)
        self.assertEqual(agg.credits, {}, "credit must not be recorded on failure")


class SportsShowcaseTest(unittest.TestCase):
    def test_read_only_fixtures(self):
        demo = Demo(data_dir=tempfile.mkdtemp())
        show = demo.sports_showcase()
        self.assertIn(show["source"], ("espn", "superbet", "inhouse"))
        self.assertGreaterEqual(len(show["fixtures"]), 1)
        for fix in show["fixtures"]:
            self.assertTrue(fix["home"] and fix["away"], fix)
        self.assertIn("note", show)

    def test_live_payload_shape(self):
        demo = Demo(data_dir=tempfile.mkdtemp())
        show = demo.sports_showcase()
        self.assertFalse(show["licensed_feed"],
                         "in-house pricing is not official data rights")
        priced = [f for f in show["fixtures"] if f["markets"]]
        self.assertGreaterEqual(len(priced), 1)
        for fix in priced:
            for market in fix["markets"]:
                self.assertEqual(len(market["selections"]),
                                 len(market["prices"]), market)
                for price in market["prices"]:
                    self.assertGreater(price, 1.0, price)

    def test_espn_engine_contract_with_canned_feed(self):
        import tempfile, os
        from frame.verticals.sports.espn_engine import EspnSportsEngine

        def fake(url):
            return {"events": [{
                "id": "123", "date": "2026-10-10T19:00Z",
                "status": {"type": {"name": "STATUS_SCHEDULED"}},
                "competitions": [{"competitors": [
                    {"homeAway": "home", "team": {"displayName": "Flamengo"}},
                    {"homeAway": "away", "team": {"displayName": "Santos"}},
                ]}],
            }]}

        cache = os.path.join(tempfile.mkdtemp(), "cache.json")
        engine = EspnSportsEngine(cache_path=cache, fetcher=fake)
        fixtures = engine.fixtures()
        self.assertTrue(fixtures)
        fixture_key = fixtures[0].key
        markets = engine.markets(fixture_key)
        kinds = {m.kind for m in markets}
        self.assertIn("1x2", kinds)
        for m in markets:
            self.assertEqual(len(m.selections), len(m.prices))
            for p in m.prices:
                self.assertGreater(p, 1.0)
        quote = engine.quote(f"{fixture_key}:1x2")
        self.assertIsNotNone(quote)
        receipt = engine.accept("b1", f"{fixture_key}:1x2", 1000)
        self.assertEqual(receipt.market_key, f"{fixture_key}:1x2")
        self.assertIn(engine.settle("b1", {"selection": "home"}), ("won", "lost"))

    def test_superbet_engine_contract_with_canned_feed(self):
        import tempfile, os
        from frame.verticals.sports.superbet_engine import SuperbetSportsEngine

        def fake(url):
            return {"events": [{
                "event_id": 999,
                "fixture": {
                    "sport_id": 5,
                    "event_name": "Flamengo × Santos",
                    "tournament_id": 77,
                    "utc_date": "2026-10-10T19:00:00Z",
                    "status": "Scheduled",
                },
            }]}

        cache = os.path.join(tempfile.mkdtemp(), "sb.json")
        engine = SuperbetSportsEngine(cache_path=cache, fetcher=fake)
        fixtures = engine.fixtures()
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0].home, "Flamengo")
        markets = engine.markets(fixtures[0].key)
        self.assertIn("1x2", {m.kind for m in markets})
        receipt = engine.accept("b2", f"{fixtures[0].key}:1x2", 500)
        self.assertEqual(receipt.stake_minor, 500)

    def test_odds_engine_deterministic_per_bucket(self):
        from demo import odds_engine
        at = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
        a = odds_engine.build(at)
        b = odds_engine.build(at)
        self.assertEqual(a["fixtures"], b["fixtures"])
        later = at + timedelta(seconds=31)
        c = odds_engine.build(later)
        self.assertEqual(a["source"], c["source"])
        prices_a = [p for f in a["fixtures"] for m in f["markets"] for p in m["prices"]]
        prices_c = [p for f in c["fixtures"] for m in f["markets"] for p in m["prices"]]
        self.assertNotEqual(prices_a, prices_c)

    def test_american_to_decimal_conversion(self):
        from scripts.fetch_live_fixtures import _decimal
        self.assertAlmostEqual(_decimal(235), 3.35, places=2)
        self.assertAlmostEqual(_decimal(-140), 1.7143, places=3)


def _forced_bet_id(prefix: str, fixture: str, selection: str, price: float,
                   win: bool) -> str:
    """A bet_id whose stored unit settles the way the test needs: the
    server derives the draw from sha256(fixture|selection|bet_id), so a
    test that needs a loss can search for one deterministically instead
    of hoping."""
    for i in range(200):
        bet_id = f"{prefix}-{i}"
        digest = hashlib.sha256(
            f"{fixture}|{selection}|{bet_id}".encode("utf-8")).hexdigest()
        unit = int(digest[:8], 16) / 0xFFFFFFFF
        if (unit < 1.0 / price) == win:
            return bet_id
    raise AssertionError(f"no bet_id settles win={win} at price {price}")


def _losing_slot_round(prefix: str) -> str:
    for i in range(500):
        round_id = f"{prefix}-{i}"
        if not spin("demo:neon-gems", round_id).is_win:
            return round_id
    raise AssertionError("no losing slot round found")


class PromoTest(unittest.TestCase):
    """Functional promotions: real claims through the double-entry wallet,
    cash-first stakes, and bonus released only by wagering."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)

    def _register(self, name="Ana Souza", cpf="529.982.247-25",
                  pix="ana.souza@example.com", account="56789-0"):
        return self.demo.upsert_player({
            "name": name, "cpf": cpf, "pix_key": pix,
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": account, "holder_name": name},
        })["player_id"]

    def _deposit(self, player, amount, deposit_id):
        return self.demo.deposit({
            "player": player, "amount_minor": amount,
            "method": "pix", "deposit_id": deposit_id})

    def test_welcome_bonus_needs_deposit_and_pays_once(self):
        player = self._register()
        with self.assertRaises(ValueError):  # nothing to match yet
            self.demo.claim_bonus({"player": player, "kind": "welcome"})
        self._deposit(player, 10000, "wb-1")
        receipt = self.demo.claim_bonus({"player": player, "kind": "welcome"})
        self.assertEqual(receipt["granted_minor"], 10000)   # 100% of R$100
        self.assertEqual(receipt["target_minor"], 200000)   # 20x turnover
        self.assertEqual(self.demo.books.bonus_available(player), 10000)
        self.assertEqual(self.demo.books.available(player), 10000)  # not cash
        self.demo.books.assert_balanced()
        view = self.demo.profile(player)["bonus"]
        self.assertTrue(view["welcome_claimed"])
        self.assertTrue(view["active"])
        self.assertEqual(view["event"]["kind"], "welcome")
        self.assertEqual(view["event"]["percent"], 0)
        self.assertFalse(view["can_claim_cashback"])  # no losses yet
        with self.assertRaises(ValueError):  # once per wallet
            self.demo.claim_bonus({"player": player, "kind": "welcome"})
        with self.assertRaises(ValueError):  # unknown kind
            self.demo.claim_bonus({"player": player, "kind": "nope"})
        with self.assertRaises(KeyError):  # unknown wallet
            self.demo.claim_bonus({"player": "player-nope", "kind": "welcome"})
        self.demo.self_exclude(player, "2030-01-01")
        with self.assertRaises(ExclusionError):
            self.demo.claim_bonus({"player": player, "kind": "cashback"})

    def test_welcome_bonus_small_first_deposit_refused(self):
        player = self._register()
        self._deposit(player, 1000, "small-1")  # R$10 < R$20 minimum
        with self.assertRaises(ValueError):
            self.demo.claim_bonus({"player": player, "kind": "welcome"})
        view = self.demo.profile(player)["bonus"]
        self.assertFalse(view["welcome_claimed"])
        self.assertFalse(view["can_claim_welcome"])
        self.assertEqual(self.demo.books.bonus_available(player), 0)
        self.demo.books.assert_balanced()

    def test_bonus_is_withheld_until_wagering_target_met(self):
        player = self._register()
        self._deposit(player, 1000000, "hold-1")
        self.demo.claim_bonus({"player": player, "kind": "welcome"})
        # capped at R$500 regardless of the R$10.000 first deposit
        self.assertEqual(self.demo.books.bonus_available(player), 50000)
        self.assertEqual(self.demo.books.available(player), 1000000)
        # a second promo cannot stack while the first is unconverted
        with self.assertRaises(ValueError):
            self.demo.claim_bonus({"player": player, "kind": "cashback"})
        # one bet of R$1.000 is 10% of the 20x target
        self.demo.bet({
            "player": player, "fixture_key": "demo:fl-hold",
            "home": "Anjos", "away": "Tubarões", "competition": "Liga Demo",
            "market_kind": "1X2", "selection": "Anjos", "price": 2.0,
            "stake_minor": 100000, "bet_id": "hold-1",
        })
        view = self.demo.profile(player)["bonus"]
        self.assertEqual(view["event"]["wagered_minor"], 100000)
        self.assertEqual(view["event"]["percent"], 10)
        self.assertFalse(view["event"]["converted"])
        # withdrawals only ever touch player:balance — the bonus stays
        self.demo.withdraw({"player": player, "amount_minor": 900000,
                            "payout_id": "hold-wd"})
        self.assertEqual(self.demo.books.available(player), 0)
        self.assertEqual(self.demo.books.bonus_available(player), 50000)
        self.demo.books.assert_balanced()

    def test_bonus_staked_when_cash_runs_out(self):
        player = self._register()
        self._deposit(player, 2000, "bs-1")
        self.demo.claim_bonus({"player": player, "kind": "welcome"})
        self.assertEqual(self.demo.books.bonus_available(player), 2000)
        self.demo.withdraw({"player": player, "amount_minor": 2000,
                            "payout_id": "bs-drain"})
        self.assertEqual(self.demo.books.available(player), 0)
        row = self.demo.spin({
            "player": player, "game_id": "demo:neon-gems",
            "stake_minor": 500, "round_id": _losing_slot_round("bsplit"),
        })
        self.assertEqual(row["payout_minor"], 0)
        # cash-first split: the stake came out of bonus, not cash
        self.assertEqual(self.demo.books.available(player), 0)
        self.assertEqual(self.demo.books.bonus_available(player), 1500)
        view = self.demo.profile(player)["bonus"]
        self.assertEqual(view["event"]["wagered_minor"], 500)
        # stake larger than everything left must fail cleanly (400, not 500)
        with self.assertRaises(ValueError):
            self.demo.spin({"player": player, "game_id": "demo:neon-gems",
                            "stake_minor": 2500,
                            "round_id": _losing_slot_round("bsplit-poor")})
        self.demo.books.assert_balanced()

    def test_cashback_is_daily_capped_and_paid_by_the_books(self):
        player = self._register()
        self._deposit(player, 10000, "cb-1")
        bet_id = _forced_bet_id("cb-loss", "demo:fl-cb", "Fora", 2.0, win=False)
        self.demo.bet({
            "player": player, "fixture_key": "demo:fl-cb",
            "home": "Anjos", "away": "Tubarões", "competition": "Liga Demo",
            "market_kind": "1X2", "selection": "Fora", "price": 2.0,
            "stake_minor": 1500, "bet_id": bet_id,
        })
        self.demo.settle_pending(settle_delay_seconds=0)
        settled = [r for r in self.demo.history(player)
                   if r["round_id"] == bet_id]
        self.assertEqual(settled[0]["tier"], "derrota")
        # 10% of R$15 net loss
        self.assertEqual(
            self.demo.profile(player)["bonus"]["cashback_available_minor"], 150)
        receipt = self.demo.claim_bonus({"player": player, "kind": "cashback"})
        self.assertEqual(receipt["granted_minor"], 150)
        self.assertEqual(receipt["target_minor"], 150)  # 1x turnover
        self.assertEqual(self.demo.books.bonus_available(player), 150)
        self.assertTrue(
            self.demo.profile(player)["bonus"]["cashback_claimed_today"])
        with self.assertRaises(ValueError):  # once per day
            self.demo.claim_bonus({"player": player, "kind": "cashback"})
        # cap: 10% of a R$40.000 loss day is still R$200
        big = self._register(name="Bruno Costa", cpf="111.444.777-35",
                             pix="bruno.costa@example.com", account="22222-2")
        self._deposit(big, 4000000, "cb-cap")
        cap_id = _forced_bet_id("cb-cap", "demo:fl-cap", "Casa", 2.0, win=False)
        self.demo.bet({
            "player": big, "fixture_key": "demo:fl-cap",
            "home": "Lobos", "away": "Falcões", "competition": "Liga Demo",
            "market_kind": "1X2", "selection": "Casa", "price": 2.0,
            "stake_minor": 4000000, "bet_id": cap_id,
        })
        self.demo.settle_pending(settle_delay_seconds=0)
        cap = self.demo.claim_bonus({"player": big, "kind": "cashback"})
        self.assertEqual(cap["granted_minor"], 20000)
        self.demo.books.assert_balanced()

    def test_settlement_releases_bonus_credit_after_conversion(self):
        player = self._register()
        self._deposit(player, 1000000, "orph-1")
        self.demo.claim_bonus({"player": player, "kind": "welcome"})
        # cash out everything: only bonus remains to bet with
        self.demo.withdraw({"player": player, "amount_minor": 1000000,
                            "payout_id": "orph-drain"})
        self.assertEqual(self.demo.books.available(player), 0)
        win_id = _forced_bet_id("orph-w", "demo:fl-ow", "Casa", 1.01, win=True)
        self.demo.bet({
            "player": player, "fixture_key": "demo:fl-ow",
            "home": "Anjos", "away": "Tubarões", "competition": "Liga Demo",
            "market_kind": "1X2", "selection": "Casa", "price": 1.01,
            "stake_minor": 50000, "bet_id": win_id,
        })
        self.assertEqual(self.demo.books.bonus_available(player), 0)
        # refill cash and finish the target with cash-first stakes
        self._deposit(player, 1000000, "orph-2")
        loss_id = _forced_bet_id("orph-l", "demo:fl-ol", "Fora", 2.0, win=False)
        self.demo.bet({
            "player": player, "fixture_key": "demo:fl-ol",
            "home": "Lobos", "away": "Falcões", "competition": "Liga Demo",
            "market_kind": "1X2", "selection": "Fora", "price": 2.0,
            "stake_minor": 950000, "bet_id": loss_id,
        })
        # 50.000 + 950.000 of turnover: target met with the bonus fully
        # staked, so the event closes even though nothing is left to move
        view = self.demo.profile(player)["bonus"]
        self.assertTrue(view["event"]["converted"])
        self.assertFalse(view["active"])
        self.assertEqual(self.demo.books.bonus_available(player), 0)
        settled = self.demo.settle_pending(settle_delay_seconds=0)
        self.assertEqual(len(settled), 2)
        # the bonus-staked win paid 1.01x back into player:bonus; with no
        # requirement on file it converts straight to withdrawable cash
        self.assertEqual(self.demo.books.bonus_available(player), 0)
        self.assertEqual(self.demo.books.available(player), 100500)
        self.demo.books.assert_balanced()


class TrendingTest(unittest.TestCase):
    """Hot/cold activity board: opens + settled rounds over the last 24h."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)

    def _register(self, name="Ana Souza", cpf="529.982.247-25",
                  pix="ana.souza@example.com", account="56789-0"):
        return self.demo.upsert_player({
            "name": name, "cpf": cpf, "pix_key": pix,
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": account, "holder_name": name},
        })["player_id"]

    def test_open_counts_as_activity_and_cold_shows_the_rest(self):
        self.demo.record_play({"player": "p1", "game_id": "demo:neon-gems"})
        self.demo.record_play({"player": "p2", "game_id": "demo:neon-gems"})
        board = self.demo.trending()
        self.assertEqual(board["window_hours"], 24)
        self.assertEqual(board["hot"][0]["game_id"], "demo:neon-gems")
        self.assertEqual(board["hot"][0]["opens"], 2)
        self.assertEqual(board["hot"][0]["rounds"], 0)
        self.assertNotIn("demo:neon-gems", board["cold"])

    def test_rounds_participate_and_bad_rows_never_leak(self):
        player = self._register()
        self.demo.deposit({"player": player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "tr-dep"})
        self.demo.spin({"player": player, "game_id": "demo:neon-gems",
                        "stake_minor": 500, "round_id": "trending-1"})
        with open(self.demo.plays_path, "a", encoding="utf-8") as fh:
            fh.write("not json\n")  # torn line is skipped, never counted
            fh.write(json.dumps({"game_id": "not:a:real:game",
                                 "ts": "2026-10-06T00:00:00+00:00"}) + "\n")
        board = self.demo.trending()
        entry = next(h for h in board["hot"] if h["game_id"] == "demo:neon-gems")
        self.assertEqual(entry["rounds"], 1)
        hot_ids = [h["game_id"] for h in board["hot"]]
        self.assertNotIn("not:a:real:game", hot_ids)
        self.assertNotIn("not:a:real:game", board["cold"])

    def test_old_activity_falls_out_of_the_window(self):
        with open(self.demo.plays_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"game_id": "demo:neon-gems",
                                 "ts": "2020-01-01T00:00:00+00:00"}) + "\n")
        board = self.demo.trending()
        self.assertEqual(board["hot"], [])
        self.assertIn("demo:neon-gems", board["cold"])

    def test_missing_game_id_refused(self):
        with self.assertRaises(ValueError):
            self.demo.record_play({"player": "p1"})


class TournamentTest(unittest.TestCase):
    """Leaderboard over today's real rounds; honest about scope."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)

    def _register(self, name, cpf, pix, account):
        return self.demo.upsert_player({
            "name": name, "cpf": cpf, "pix_key": pix,
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": account, "holder_name": name},
        })["player_id"]

    def _row(self, player, ts, payout=0):
        return {"round_id": f"tr-{player}-{ts}-{payout}", "player": player,
                "game_id": "demo:neon-gems", "stake_minor": 500,
                "payout_minor": payout, "tier": "pago", "type": "casino", "ts": ts}

    def test_boards_count_only_todays_real_rows(self):
        ana = self._register("Ana Souza", "529.982.247-25",
                             "ana.souza@example.com", "56789-0")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(self.demo.rounds_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(self._row(ana, now, payout=25000)) + "\n")
            fh.write(json.dumps(self._row(ana, now)) + "\n")
            fh.write(json.dumps(self._row(ana, "2020-01-01T00:00:00+00:00")) + "\n")
        board = self.demo.tournaments()
        self.assertIn("Torneios organizados", board["note"])
        self.assertEqual(board["day"], datetime.now(timezone.utc).date().isoformat())
        active = next(b for b in board["boards"] if b["key"] == "most_active")
        self.assertEqual(active["rows"][0], {"label": "Ana Souza", "value": 2})
        wins = next(b for b in board["boards"] if b["key"] == "biggest_win")
        self.assertEqual(wins["rows"][0], {"label": "Ana Souza", "value_minor": 25000})

    def test_empty_day_says_nothing_scheduled(self):
        board = self.demo.tournaments()
        for b in board["boards"]:
            self.assertEqual(b["rows"], [])


class NewsTest(unittest.TestCase):
    """The news panel is derived from real facts, never hard-coded."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)

    def test_always_carries_catalog_promo_and_fixture_facts(self):
        items = self.demo.news()["items"]
        tags = {i["tag"] for i in items}
        self.assertIn("CASSINO", tags)
        self.assertIn("PROMOÇÕES", tags)
        self.assertIn("ESPORTE", tags)  # this repo ships live capture+

    def test_activity_and_daily_win_surface(self):
        self.demo.record_play({"player": "p1", "game_id": "pp:gates-of-olympus"})
        self.demo.record_play({"player": "p2", "game_id": "pp:gates-of-olympus"})
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(self.demo.rounds_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"round_id": "news-1", "player": "ghost",
                                 "game_id": "pp:gates-of-olympus",
                                 "stake_minor": 500, "payout_minor": 123456,
                                 "tier": "pago", "type": "casino", "ts": now}) + "\n")
        by_tag = {i["tag"]: i["title"] for i in self.demo.news()["items"]}
        self.assertIn("ALTA", by_tag)
        self.assertIn("Gates of Olympus", by_tag["ALTA"])
        self.assertIn("PRÊMIO", by_tag)
        self.assertIn("1.234,56", by_tag["PRÊMIO"])


class JackpotChatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)

    def test_jackpot_pool_grows_with_real_turnover(self):
        base = self.demo.jackpot()["pool_minor"]
        self.assertEqual(base, 284719450)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(self.demo.rounds_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"round_id": "j1", "player": "p", "game_id": "demo:neon-gems",
                                 "stake_minor": 10000, "ts": now, "type": "casino"}) + "\n")
            fh.write(json.dumps({"round_id": "j2", "player": "p", "game_id": "demo:neon-gems",
                                 "stake_minor": 5000, "ts": now, "type": "casino"}) + "\n")
            fh.write(json.dumps({"round_id": "j3", "player": "p", "game_id": "demo:neon-gems",
                                 "stake_minor": 999999, "ts": "2020-01-01T00:00:00+00:00", "type": "casino"}) + "\n")
        after = self.demo.jackpot()
        self.assertEqual(after["volume_today_minor"], 15000)
        self.assertEqual(after["pool_minor"], 284719450 + 150)

    def test_chat_triage_answers_real_intents_and_falls_back(self):
        self.assertIn("PIX", self.demo.chat({"message": "como faco um saque?"})["reply"])
        self.assertIn("bônus", self.demo.chat({"message": "quais bonus ativos?"})["reply"])
        self.assertIn("Catálogo", self.demo.chat({"message": "quantos jogos oficiais?"})["reply"])
        self.assertIn("Posso ajudar", self.demo.chat({"message": "xyzzy"})["reply"])


class AuthTest(unittest.TestCase):
    """Painel credentials: default admin/admin seeded, hashed at rest,
    bearer sessions with a TTL, role gates, and password changes that
    revoke every session for the user."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)

    def _login(self, username="admin", password="admin"):
        return self.demo.auth_login({"username": username,
                                     "password": password})

    def test_default_admin_seeded_and_stored_hashed(self):
        self.assertEqual(self.demo.users.authenticate("admin", "admin"),
                         "admin")
        with open(self.demo.users.path, "r", encoding="utf-8") as fh:
            raw = fh.read()
        record = json.loads(raw)["admin"]
        self.assertEqual(len(record["hash"]), 64)   # sha256 hexdigest
        self.assertNotEqual(record["hash"], "admin")
        self.assertNotIn("password", record)        # plaintext never stored
        with self.assertRaises(AuthError):
            self.demo.users.authenticate("admin", "wrong-password")
        with self.assertRaises(AuthError):
            self.demo.users.authenticate("ghost", "admin")

    def test_login_session_lifecycle(self):
        out = self._login()
        self.assertEqual(out["role"], "admin")
        self.assertEqual(self.demo.auth_me(out["token"])["username"],
                         "admin")
        self.demo.auth_logout(out["token"])
        with self.assertRaises(AuthError):
            self.demo.auth_me(out["token"])
        with self.assertRaises(AuthError):
            self._login(password="wrong-password")
        with self.assertRaises(AuthError):
            self.demo.auth_me("not-a-token")

    def test_dashboard_needs_a_session(self):
        with self.assertRaises(AuthError):
            self.demo.admin_dashboard("")
        self.assertIn("totals",
                      self.demo.admin_dashboard(self._login()["token"]))

    def test_viewer_watches_but_cannot_manage(self):
        admin = self._login()["token"]
        self.demo.admin_create_user(admin, {"username": "ana",
                                            "password": "segura42",
                                            "role": "viewer"})
        viewer = self._login("ana", "segura42")["token"]
        self.assertIn("totals", self.demo.admin_dashboard(viewer))
        with self.assertRaises(AuthError):
            self.demo.admin_users(viewer)
        with self.assertRaises(AuthError):
            self.demo.admin_create_user(viewer, {"username": "x",
                                                 "password": "segura42",
                                                 "role": "viewer"})
        listing = self.demo.admin_users(admin)["users"]
        self.assertEqual(listing[0]["username"], "admin")
        self.assertTrue(all("hash" not in u and "salt" not in u
                            for u in listing))

    def test_change_own_password_requires_current_and_revokes(self):
        token = self._login()["token"]
        with self.assertRaises(AuthError):
            self.demo.auth_change_password(
                token, {"current": "wrong", "new": "nova-senha"})
        out = self.demo.auth_change_password(
            token, {"current": "admin", "new": "nova-senha"})
        with self.assertRaises(AuthError):
            self.demo.auth_me(token)          # old session died with it
        self.assertEqual(self.demo.auth_me(out["token"])["username"],
                         "admin")             # reissued token still live
        self._login(password="nova-senha")    # new password works
        with self.assertRaises(AuthError):
            self._login(password="admin")     # old password is dead

    def test_admin_reset_delete_and_guards(self):
        admin = self._login()["token"]
        self.demo.admin_create_user(admin, {"username": "bob",
                                            "password": "segura42",
                                            "role": "viewer"})
        bob = self._login("bob", "segura42")["token"]
        self.demo.admin_reset_password(admin, {"username": "bob",
                                               "new": "outra-senha"})
        with self.assertRaises(AuthError):
            self.demo.auth_me(bob)            # reset revoked his sessions
        self._login("bob", "outra-senha")
        with self.assertRaises(AuthError):
            self.demo.admin_delete_user(admin, {"username": "admin"})
        with self.assertRaises(AuthError):
            self.demo.users.delete("admin", by="someone-else")  # last admin
        self.demo.admin_delete_user(admin, {"username": "bob"})
        with self.assertRaises(AuthError):
            self._login("bob", "outra-senha")

    def test_weak_passwords_refused(self):
        with self.assertRaises(AuthError):
            self.demo.users.set_password("admin", "ab")
        with self.assertRaises(AuthError):
            self.demo.users.create("short", "ab", "viewer")


class PlayerAuthTest(unittest.TestCase):
    """Player accounts: strict register (name + email + CPF + password +
    payout details, every field validated) and email-or-CPF login.
    Credential material never leaves the store through profile()."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)

    def _payload(self, **over):
        body = {
            "name": "Ana Souza",
            "email": "ana.souza@example.com",
            "cpf": "529.982.247-25",
            "password": "ana1234",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        }
        body.update(over)
        return body

    def test_email_and_password_policy(self):
        self.assertEqual(validate_email("Ana@Example.COM"),
                         "ana@example.com")
        for bad in ("", "sem-arroba", "a@b", "a@b.c", "x" * 250 + "@a.com"):
            with self.assertRaises(PaymentError):
                validate_email(bad)
        self.assertEqual(validate_player_password("ana1234"), "ana1234")
        for bad in ("", "ab", "abcde", "abcdef", "123456", "a1"):
            with self.assertRaises(PaymentError):
                validate_player_password(bad)

    def test_register_validates_every_field(self):
        for bad in ("not-an-email", "", "a@b.c"):
            with self.assertRaises((ValueError, PaymentError)):
                self.demo.register_player(self._payload(email=bad))
        for bad in ("123", "111.111.111-11", "529.982.247-26"):
            with self.assertRaises((ValueError, PaymentError)):
                self.demo.register_player(self._payload(cpf=bad))
        for bad in ("abc", "abcdef", "123456"):
            with self.assertRaises((ValueError, PaymentError)):
                self.demo.register_player(self._payload(password=bad))
        with self.assertRaises((ValueError, PaymentError)):
            self.demo.register_player(self._payload(name="A"))

    def test_register_stores_email_and_hashed_password(self):
        row = self.demo.register_player(self._payload())
        self.assertEqual(row["email"], "ana.souza@example.com")
        with open(self.demo.players.path, "r", encoding="utf-8") as fh:
            stored = json.load(fh)[row["player_id"]]
        self.assertEqual(len(stored["pw_hash"]), 64)
        self.assertNotEqual(stored["pw_hash"], "ana1234")
        self.assertNotIn("password", stored)
        self.assertNotIn("pw_hash", row)
        self.assertNotIn("pw_salt", row)

    def test_register_rejects_second_account_per_cpf_or_email(self):
        self.demo.register_player(self._payload())
        with self.assertRaises(ValueError):
            self.demo.register_player(self._payload())
        with self.assertRaises(ValueError):
            self.demo.register_player(self._payload(cpf="111.444.777-35"))

    def test_login_accepts_email_or_cpf(self):
        player_id = self.demo.register_player(self._payload())["player_id"]
        out = self.demo.login_player({"identifier": "ana.souza@example.com",
                                      "password": "ana1234"})
        self.assertEqual(out["player_id"], player_id)
        out = self.demo.login_player({"identifier": "529.982.247-25",
                                      "password": "ana1234"})
        self.assertEqual(out["player_id"], player_id)
        self.assertNotIn("pw_hash", out)

    def test_login_refuses_unknown_or_wrong(self):
        self.demo.register_player(self._payload())
        with self.assertRaises(ValueError):
            self.demo.login_player({"identifier": "ana.souza@example.com",
                                    "password": "errada42"})
        with self.assertRaises(ValueError):
            self.demo.login_player({"identifier": "ghost@example.com",
                                    "password": "ana1234"})
        with self.assertRaises(ValueError):
            self.demo.login_player({"identifier": "123", "password": "ana1234"})

    def test_legacy_rows_without_credentials_cannot_login(self):
        row = self.demo.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })
        with self.assertRaises(ValueError):
            self.demo.login_player({"identifier": "529.982.247-25",
                                    "password": "qualquer1"})


class AdminDashboardTest(unittest.TestCase):
    """Painel administrativo: every figure must derive from the stores —
    books for money, round ledger for RTP/leaderboards/series, players
    file for labels. Nothing fabricated, nothing double-counted."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)

    def _register(self, name, cpf, pix, account):
        return self.demo.upsert_player({
            "name": name, "cpf": cpf, "pix_key": pix,
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": account, "holder_name": name},
        })["player_id"]

    def _row(self, player, ts, stake=500, payout=0, tier="pago",
             type_="casino", round_id=None):
        return {"round_id": round_id or f"ad-{player}-{ts}-{stake}-{payout}",
                "player": player, "game_id": "demo:neon-gems",
                "stake_minor": stake, "payout_minor": payout,
                "tier": tier, "type": type_, "ts": ts}

    def _write(self, rows):
        with open(self.demo.rounds_path, "a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")

    def _token(self):
        # admin_dashboard is gated: the panel hides from anonymous callers
        return self.demo.auth_login({"username": "admin",
                                     "password": "admin"})["token"]

    def test_money_block_matches_the_books(self):
        ana = self._register("Ana Souza", "529.982.247-25",
                             "ana.souza@example.com", "56789-0")
        self.demo.deposit({"player": ana, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "ad-dep"})
        self.demo.spin({"player": ana, "game_id": "demo:neon-gems",
                        "stake_minor": 500, "round_id": "ad-spin"})
        dash = self.demo.admin_dashboard(self._token())
        t = dash["totals"]
        self.assertEqual(t["players"], 1)
        self.assertEqual(t["deposits_minor"], 10000)
        self.assertEqual(t["withdrawals_minor"], 0)
        self.assertEqual(t["withdrawals_pending_minor"], 0)
        self.assertEqual(t["ggr_minor"], self.demo.books.ggr())
        self.assertEqual(t["rounds"], 1)
        self.assertEqual(dash["health"], self.demo.health_report()["status"])
        self.assertEqual(dash["jackpot"]["pool_minor"],
                         self.demo.jackpot()["pool_minor"])
        self.assertIsInstance(dash["risk"]["flagged_players"], int)
        self.assertGreaterEqual(dash["risk"]["flagged_players"], 0)
        today = dash["day_series"][-1]
        self.assertEqual(today["day"], dash["day"])
        self.assertEqual(today["stake_minor"], 500)

    def test_rtp_excludes_pending_and_sports(self):
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._write([
            self._row("p1", now, stake=1000, payout=950),
            self._row("p2", now, stake=9999, payout=0, tier="pendente"),
            self._row("p3", now, stake=400, payout=800, type_="sports"),
            self._row("p4", now, stake=500, type_="sports",
                      tier="pendente"),
        ])
        r = self.demo.admin_dashboard(self._token())["returns"]
        self.assertEqual(r["rtp_percent"], 95.0)
        self.assertEqual(r["rtp_today_percent"], 95.0)
        self.assertEqual(r["model_rtp_percent"], round(DEMO_RTP * 100, 2))
        dash = self.demo.admin_dashboard(self._token())
        self.assertEqual(dash["pending_sports"], 1)

    def test_leaderboards_rank_real_rows(self):
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        ana = self._register("Ana Souza", "529.982.247-25",
                             "ana.souza@example.com", "56789-0")
        bruno = self._register("Bruno Lima", "111.444.777-35",
                               "bruno.lima@example.com", "56789-0")
        self._write([
            self._row(ana, now, stake=500, payout=25000),
            self._row(bruno, now, stake=500, payout=0),
            self._row(bruno, now, stake=700, payout=0, tier="pendente",
                      round_id="ad-pending"),
        ])
        dash = self.demo.admin_dashboard(self._token())
        top = dash["top_winners"]
        self.assertEqual(top[0]["label"], "Ana Souza")
        self.assertEqual(top[0]["net_minor"], 24500)
        self.assertEqual(top[0]["rounds"], 1)
        self.assertEqual(top[1]["label"], "Bruno Lima")
        self.assertEqual(top[1]["net_minor"], -500)
        self.assertEqual(top[1]["rounds"], 1)  # pending stake not a loss
        wins = dash["biggest_wins"]
        self.assertEqual(wins[0]["label"], "Ana Souza")
        self.assertEqual(wins[0]["payout_minor"], 25000)
        self.assertEqual(wins[0]["day"], now[:10])

    def test_empty_demo_is_honest(self):
        dash = self.demo.admin_dashboard(self._token())
        self.assertEqual(dash["top_winners"], [])
        self.assertEqual(dash["biggest_wins"], [])
        self.assertIsNone(dash["returns"]["rtp_percent"])
        self.assertIsNone(dash["returns"]["rtp_today_percent"])
        self.assertEqual(len(dash["day_series"]), 7)
        for day in dash["day_series"]:
            self.assertEqual(day["stake_minor"], 0)
            self.assertEqual(day["rounds"], 0)
        self.assertEqual(dash["totals"]["players"], 0)
        self.assertEqual(dash["totals"]["deposits_minor"], 0)
        self.assertEqual(dash["pending_sports"], 0)

class LiveTest(unittest.TestCase):
    """Real-time pulse: 15-minute opens window, newest wins
    first, names masked. Everything from files, nothing
    fabricated — an empty lobby reports zero."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)

    def _register(self, name="Ana Souza", cpf="529.982.247-25",
                  pix="ana.souza@example.com", account="56789-0"):
        return self.demo.upsert_player({
            "name": name, "cpf": cpf, "pix_key": pix,
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": account, "holder_name": name},
        })["player_id"]

    def _play(self, game_id, player, ts):
        with open(self.demo.plays_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"game_id": game_id,
                                  "player": player,
                                  "ts": ts}) + "\n")

    def test_active_now_counts_recent_opens_and_players(self):
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._play("demo:neon-gems", "p1", now)
        self._play("demo:neon-gems", "p2", now)
        self._play("pp:gates-of-olympus", "p1", now)
        self._play("demo:neon-gems", "p1",
                    "2020-01-01T00:00:00+00:00")  # outside the window
        with open(self.demo.plays_path, "a", encoding="utf-8") as fh:
            fh.write("not json\n")  # torn line never crashes the pulse
        out = self.demo.live()
        self.assertEqual(out["window_minutes"], 15)
        self.assertEqual(out["active_players"], 2)
        games = {g["game_id"]: g["opens"] for g in out["active_games"]}
        self.assertEqual(games["demo:neon-gems"], 2)
        self.assertEqual(games["pp:gates-of-olympus"], 1)
        self.assertEqual(out["active_games"][0]["game_id"],
                         "demo:neon-gems")  # ranked by opens

    def test_latest_wins_are_newest_first_and_masked(self):
        pid = self._register("Ana Souza")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rows = [
            {"round_id": "w-old", "player": pid,
             "game_id": "demo:neon-gems", "stake_minor": 500,
             "payout_minor": 1000, "tier": "big", "type": "casino",
             "ts": "2026-10-01T10:00:00+00:00"},
            {"round_id": "w-loss", "player": pid,
             "game_id": "demo:neon-gems", "stake_minor": 500,
             "payout_minor": 0, "tier": "loss", "type": "casino",
             "ts": now},
            {"round_id": "w-new", "player": pid,
             "game_id": "demo:gold-vault", "stake_minor": 500,
             "payout_minor": 3000, "tier": "epic", "type": "casino",
             "ts": now},
        ]
        with open(self.demo.rounds_path, "a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        out = self.demo.live()
        self.assertEqual(out["latest_wins"][0]["payout_minor"], 3000)
        self.assertEqual(out["latest_wins"][0]["label"], "Ana S.")
        self.assertEqual(out["latest_wins"][0]["title"],
                         "Gold Vault")
        self.assertEqual(out["latest_wins"][1]["payout_minor"], 1000)
        self.assertEqual(len(out["latest_wins"]), 2)  # losses never listed

    def test_empty_lobby_reports_zero(self):
        out = self.demo.live()
        self.assertEqual(out["active_players"], 0)
        self.assertEqual(out["active_games"], [])
        self.assertEqual(out["latest_wins"], [])
        self.assertEqual(out["jackpot_pool_minor"],
                         self.demo.jackpot()["pool_minor"])


class CasinoTest(unittest.TestCase):
    """In-house table game (decision 0021): European
    single-zero roulette. Deterministic ball, real payouts
    (35:1 straight, 1:1 even-money), zero loses everything
    but a straight-up 0 — RTP 36/37 on every market."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)

    def _register(self, name="Ana Souza", cpf="529.982.247-25",
                  pix="ana.souza@example.com", account="56789-0"):
        return self.demo.upsert_player({
            "name": name, "cpf": cpf, "pix_key": pix,
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": account, "holder_name": name},
        })["player_id"]

    def test_ball_is_deterministic_per_round(self):
        from demo import casino
        a = casino.roulette_spin(casino.ROULETTE_GAME_ID, "r1", "red")
        b = casino.roulette_spin(casino.ROULETTE_GAME_ID, "r1", "red")
        self.assertEqual(a.ball, b.ball)
        self.assertEqual(a.unit, b.unit)
        self.assertEqual(a.selection, "red")

    def test_every_pocket_is_reachable(self):
        from demo import casino
        seen = {casino.ball_from_unit(
            casino.draw_unit(casino.ROULETTE_GAME_ID, f"cov-{i}"))
            for i in range(3700)}
        self.assertEqual(seen, set(range(37)))

    def test_straight_up_pays_36x(self):
        from demo import casino
        rid = "su-fixed"
        ball = casino.ball_from_unit(
            casino.draw_unit(casino.ROULETTE_GAME_ID, rid))
        result = casino.roulette_spin(
            casino.ROULETTE_GAME_ID, rid, str(ball))
        self.assertEqual(result.tier, "straight")
        self.assertEqual(result.multiplier, "36.00")
        self.assertTrue(result.is_win)

    def test_even_money_pays_2x(self):
        from demo import casino
        for i in range(3700):
            rid = f"em-{i}"
            ball = casino.ball_from_unit(
                casino.draw_unit(casino.ROULETTE_GAME_ID, rid))
            if ball == 0:
                continue
            selection = "red" if ball in casino.RED else "black"
            result = casino.roulette_spin(
                casino.ROULETTE_GAME_ID, rid, selection)
            self.assertEqual(result.tier, "even-money")
            self.assertEqual(result.multiplier, "2.00")
            break
        else:
            self.fail("no non-zero ball in 3700 draws")

    def test_zero_loses_every_even_money_bet_but_straight(self):
        from demo import casino
        for i in range(3700):
            rid = f"z-{i}"
            ball = casino.ball_from_unit(
                casino.draw_unit(casino.ROULETTE_GAME_ID, rid))
            if ball != 0:
                continue
            for selection in ("red", "black", "even", "odd",
                              "low", "high"):
                result = casino.roulette_spin(
                    casino.ROULETTE_GAME_ID, rid, selection)
                self.assertEqual(result.tier, "loss")
                self.assertFalse(result.is_win)
            zero = casino.roulette_spin(
                casino.ROULETTE_GAME_ID, rid, "0")
            self.assertEqual(zero.tier, "straight")
            self.assertTrue(zero.is_win)
            break
        else:
            self.fail("no zero ball in 3700 draws")

    def test_european_rtp_is_36_over_37(self):
        from demo import casino
        self.assertAlmostEqual(casino.theoretical_rtp(), 36 / 37,
                               places=9)

    def test_selection_is_required(self):
        from demo import casino
        with self.assertRaises(ValueError):
            casino.roulette_spin(casino.ROULETTE_GAME_ID, "r", None)
        with self.assertRaises(ValueError):
            casino.roulette_spin(casino.ROULETTE_GAME_ID, "r", "purple")

    def test_roulette_is_a_launchable_mesa_game(self):
        demo = Demo(data_dir=tempfile.mkdtemp())
        rows = {g["game_id"]: g for g in demo.catalog()}
        row = rows["demo:roulette-europeia"]
        self.assertTrue(row["launchable"])
        self.assertEqual(row["category"], "Mesa")
        self.assertEqual(row["rtp"], "97.30")

    def test_roulette_win_settles_through_the_books(self):
        player = self._register()
        self.demo.deposit({"player": player, "amount_minor": 10000,
                            "method": "pix", "deposit_id": "rl-dep"})
        from demo import casino
        round_id = "rl-e2e-1"
        ball = casino.ball_from_unit(
            casino.draw_unit(casino.ROULETTE_GAME_ID, round_id))
        row = self.demo.spin({
            "player": player, "game_id": casino.ROULETTE_GAME_ID,
            "stake_minor": 500, "round_id": round_id,
            "selection": str(ball),
        })
        self.assertEqual(row["tier"], "straight")
        self.assertEqual(row["payout_minor"], 500 * 36)
        self.assertEqual(row["symbols"][0], str(ball))
        self.assertEqual(
            self.demo.books.available(player), 10000 - 500 + 500 * 36)
        hist = self.demo.history(player)
        self.assertEqual(hist[0]["payout_minor"], 500 * 36)
        self.assertEqual(hist[0]["game_id"], casino.ROULETTE_GAME_ID)
        self.demo.books.assert_balanced()

    def test_roulette_loss_settles_through_the_books(self):
        player = self._register()
        self.demo.deposit({"player": player, "amount_minor": 10000,
                            "method": "pix", "deposit_id": "rl-dep"})
        from demo import casino
        for i in range(3700):
            round_id = f"rl-loss-{i}"
            ball = casino.ball_from_unit(
                casino.draw_unit(casino.ROULETTE_GAME_ID, round_id))
            if ball != 0:
                continue
            row = self.demo.spin({
                "player": player, "game_id": casino.ROULETTE_GAME_ID,
                "stake_minor": 500, "round_id": round_id,
                "selection": "red",
            })
            self.assertEqual(row["tier"], "loss")
            self.assertEqual(row["payout_minor"], 0)
            self.assertEqual(self.demo.books.available(player), 9500)
            self.demo.books.assert_balanced()
            return
        self.fail("no zero ball in 3700 draws")

    def test_roulette_spin_without_selection_is_refused(self):
        player = self._register()
        self.demo.deposit({"player": player, "amount_minor": 10000,
                            "method": "pix", "deposit_id": "rl-dep"})
        with self.assertRaises(ValueError):
            self.demo.spin({
                "player": player, "game_id": "demo:roulette-europeia",
                "stake_minor": 500, "round_id": "rl-nosel",
            })
        self.assertEqual(self.demo.books.available(player), 10000)

    def test_new_originals_spin_and_settle(self):
        player = self._register()
        self.demo.deposit({"player": player, "amount_minor": 10000,
                            "method": "pix", "deposit_id": "orig-dep"})
        from demo import casino, slot
        row = self.demo.spin({
            "player": player, "game_id": "demo:crimson-dragons",
            "stake_minor": 500, "round_id": "cd-1",
        })
        crimson_symbols = {tuple(t.symbols) for t in slot.CRIMSON_TIERS}
        self.assertIn(tuple(row["symbols"]), crimson_symbols)
        row = self.demo.spin({
            "player": player, "game_id": "demo:gold-vault",
            "stake_minor": 500, "round_id": "gv-1",
        })
        gold_symbols = {tuple(t.symbols) for t in slot.GOLD_TIERS}
        self.assertIn(tuple(row["symbols"]), gold_symbols)
        self.demo.books.assert_balanced()
        self.assertNotEqual(casino.ROULETTE_GAME_ID, "demo:crimson-dragons")


class SlotPaytableTest(unittest.TestCase):
    """The originals are different games: one paytable per
    title, each summing to 1 with its own RTP."""

    def test_each_table_sums_to_one(self):
        from demo import slot
        for tiers in (slot.TIERS, slot.CRIMSON_TIERS, slot.GOLD_TIERS):
            self.assertAlmostEqual(
                sum(t.probability for t in tiers), 1.0, places=9)

    def test_distinct_rtps(self):
        from demo import slot
        self.assertAlmostEqual(slot.rtp_of("demo:neon-gems"),
                               0.959, places=3)
        self.assertAlmostEqual(slot.rtp_of("demo:fortune-ledger"),
                               0.959, places=3)
        self.assertAlmostEqual(slot.rtp_of("demo:crimson-dragons"),
                               0.9495, places=4)
        self.assertAlmostEqual(slot.rtp_of("demo:gold-vault"),
                               0.966, places=3)

    def test_paytables_are_distinct_games(self):
        from demo import slot
        self.assertNotEqual(slot.tiers_for("demo:crimson-dragons"),
                            slot.TIERS)
        self.assertNotEqual(slot.tiers_for("demo:gold-vault"),
                            slot.TIERS)
        self.assertEqual(slot.tiers_for("demo:neon-gems"), slot.TIERS)

    def test_unknown_game_falls_back_to_the_original_table(self):
        from demo import slot
        self.assertEqual(slot.tiers_for("demo:whatever"), slot.TIERS)

    def test_catalog_carries_real_paytables(self):
        from demo import slot
        demo = Demo(data_dir=tempfile.mkdtemp())
        rows = {g["game_id"]: g for g in demo.catalog()}
        for gid in ("demo:neon-gems", "demo:crimson-dragons",
                    "demo:gold-vault"):
            self.assertTrue(rows[gid]["paytable"], gid)
            self.assertTrue(all(float(t["multiplier"]) > 0
                                for t in rows[gid]["paytable"]))
        self.assertEqual(rows["demo:neon-gems"]["paytable"][0]["name"],
                         "jackpot")  # richest tier first
        self.assertEqual(
            {t["name"] for t in rows["demo:crimson-dragons"]["paytable"]},
            {t.name for t in slot.CRIMSON_TIERS if t.multiplier != "0"})

    def test_spin_draws_against_the_game_own_table(self):
        from demo import slot
        for i in range(200):
            rid = f"pp-{i}"
            neon = slot.spin("demo:neon-gems", rid)
            crimson = slot.spin("demo:crimson-dragons", rid)
            if (neon.tier, neon.symbols) != (crimson.tier,
                                             crimson.symbols):
                break
        else:
            self.fail("paytables never disagree in 200 draws")


class ArcadeTest(unittest.TestCase):
    """In-house arcade originals (decision 0030): crash, plinko and mines.

    Same sha256 draw discipline as the slots and roulette; settlement goes
    through place_bet + settle_casino so partial returns below the stake
    pay exactly. RTPs: crash 97.00% every target, plinko 97.16%,
    mines 97% minus flooring dust."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)
        self.player = self.demo.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })["player_id"]
        self.demo.deposit({"player": self.player, "amount_minor": 100000,
                           "method": "pix", "deposit_id": "arc-dep"})

    def test_crash_is_deterministic_and_names_both_sides(self):
        from demo import arcade
        a = arcade.crash_round(arcade.CRASH_GAME_ID, "c1", "2.00", 200)
        b = arcade.crash_round(arcade.CRASH_GAME_ID, "c1", "2.00", 200)
        self.assertEqual(a, b)
        # one round that busts before 2x and one that clears it exist
        bust = next(arcade.crash_round(arcade.CRASH_GAME_ID, f"cb-{i}",
                                       "2.00", 200)
                    for i in range(300)
                    if arcade.crash_point_from_unit(
                        arcade.draw_unit(arcade.CRASH_GAME_ID, f"cb-{i}"))
                    < 2.0)
        self.assertFalse(bust.is_win)
        self.assertEqual(bust.payout_minor, 0)
        self.assertTrue(bust.tier.startswith("crash "))
        win = next(arcade.crash_round(arcade.CRASH_GAME_ID, f"cw-{i}",
                                      "2.00", 200)
                   for i in range(300)
                   if arcade.crash_point_from_unit(
                       arcade.draw_unit(arcade.CRASH_GAME_ID, f"cw-{i}"))
                   >= 2.0)
        self.assertTrue(win.is_win)
        self.assertEqual(win.payout_minor, 400)

    def test_crash_target_is_required_and_bounded(self):
        from demo import arcade
        for bad in (None, "", "x", "0.5", "1.00", "1000.01", "abc"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                arcade.crash_round(arcade.CRASH_GAME_ID, "cx", bad, 200)
        self.assertEqual(
            arcade.parse_crash_target("2x"), 2.0)
        self.assertEqual(
            arcade.parse_crash_target("1.01"), 1.01)

    def test_crash_rtp_is_97_percent_on_every_target(self):
        from demo import arcade
        for target in (1.5, 2.0, 5.0, 10.0):
            self.assertAlmostEqual(arcade.crash_rtp(target), 0.97,
                                   places=3, msg=f"target {target}")

    def test_crash_settles_exactly_through_the_books(self):
        before = self.demo.books.available(self.player)
        row = self.demo.spin({"player": self.player,
                              "game_id": "demo:crash-nitro",
                              "stake_minor": 200, "selection": "2.00",
                              "round_id": "arc-c1"})
        after = self.demo.books.available(self.player)
        self.assertEqual(after - before, row["payout_minor"] - 200)
        if row["payout_minor"]:
            self.assertEqual(row["payout_minor"], 400)
        self.demo.books.assert_balanced()

    # -- crash: live (manual cash-out) ---------------------------------

    @staticmethod
    def _round_id_with_bust(floor: float) -> str:
        from demo import arcade
        for i in range(2000):
            rid = f"live-{i}"
            if arcade.crash_bust_multiplier(arcade.CRASH_GAME_ID, rid) >= floor:
                return rid
        raise AssertionError(f"no round id with bust >= {floor}")

    def test_crash_live_curve_is_monotonic_and_invertible(self):
        from demo import arcade
        self.assertEqual(arcade.crash_multiplier_at(0.0), 1.0)
        self.assertLess(arcade.crash_multiplier_at(1.0),
                        arcade.crash_multiplier_at(2.0))
        for m in (1.01, 2.0, 5.0, 100.0):
            self.assertAlmostEqual(
                arcade.crash_multiplier_at(arcade.crash_elapsed_for(m)), m,
                places=6, msg=f"multiplier {m}")
        self.assertEqual(arcade.crash_elapsed_for(1.0), 0.0)
        self.assertEqual(arcade.crash_elapsed_for(0.5), 0.0)

    def test_crash_live_engine_cashes_before_bust_and_loses_after(self):
        from demo import arcade
        rid = self._round_id_with_bust(2.0)
        point = arcade.crash_bust_multiplier(arcade.CRASH_GAME_ID, rid)
        t_bust = arcade.crash_elapsed_for(point)
        won = arcade.crash_live_round(arcade.CRASH_GAME_ID, rid,
                                      t_bust - 0.05, 200)
        self.assertTrue(won.is_win)
        self.assertEqual(won.payout_minor,
                         int(round(200 * arcade.crash_multiplier_at(
                             t_bust - 0.05))))
        self.assertEqual(won, arcade.crash_live_round(
            arcade.CRASH_GAME_ID, rid, t_bust - 0.05, 200))  # deterministic
        lost = arcade.crash_live_round(arcade.CRASH_GAME_ID, rid,
                                       t_bust + 0.01, 200)
        self.assertFalse(lost.is_win)
        self.assertEqual(lost.payout_minor, 0)
        self.assertEqual(lost.symbols[1], "sem saque")

    def test_crash_live_rtp_is_97_percent_at_any_cashout(self):
        from demo import arcade
        for cash in (1.5, 2.0, 5.0, 10.0):
            self.assertAlmostEqual(arcade.crash_live_rtp(cash), 0.97,
                                   places=3, msg=f"cash {cash}")

    def test_crash_live_start_hides_bust_and_debits_once(self):
        before = self.demo.books.available(self.player)
        start = self.demo.crash_start({"player": self.player,
                                       "game_id": "demo:crash-nitro",
                                       "stake_minor": 200})
        self.assertIn("token", start)
        self.assertNotIn("bust", start)  # the draw stays server-side
        self.assertEqual(self.demo.books.available(self.player), before - 200)
        # a player flies one round at a time
        with self.assertRaises(ValueError):
            self.demo.crash_start({"player": self.player,
                                   "game_id": "demo:crash-nitro",
                                   "stake_minor": 200})
        # force a generous bust so the outcome is deterministic
        self.demo.crash_pending[start["token"]]["round_id"] = \
            self._round_id_with_bust(3.0)
        flying = self.demo.crash_status({"token": start["token"]})
        self.assertEqual(flying["status"], "flying")
        self.assertNotIn("bust", flying)
        self.assertGreaterEqual(flying["multiplier"], 1.0)
        out = self.demo.crash_cashout({"player": self.player,
                                       "token": start["token"]})
        self.assertEqual(out["status"], "cashed")
        self.assertTrue(out["win"])
        self.assertGreaterEqual(out["payout_minor"], 200)
        self.assertGreaterEqual(out["bust"], 1.0)  # revealed on settle
        self.demo.books.assert_balanced()
        # the token is spent
        self.assertEqual(
            self.demo.crash_status({"token": start["token"]})["status"],
            "unknown")

    def test_crash_live_bust_settles_loss_through_the_books(self):
        before = self.demo.books.available(self.player)
        start = self.demo.crash_start({"player": self.player,
                                       "game_id": "demo:crash-nitro",
                                       "stake_minor": 200})
        self.demo.crash_pending[start["token"]]["round_id"] = \
            self._round_id_with_bust(2.0)
        self.demo.crash_pending[start["token"]]["started_at"] = time.time() - 60
        out = self.demo.crash_cashout({"player": self.player,
                                       "token": start["token"]})
        self.assertEqual(out["status"], "busted")
        self.assertFalse(out["win"])
        self.assertEqual(out["payout_minor"], 0)
        self.assertEqual(self.demo.books.available(self.player), before - 200)
        self.demo.books.assert_balanced()

    def test_crash_live_sweep_drains_an_abandoned_round(self):
        start = self.demo.crash_start({"player": self.player,
                                       "game_id": "demo:crash-nitro",
                                       "stake_minor": 200})
        self.demo.crash_pending[start["token"]]["started_at"] = time.time() - 60
        self.assertEqual(self.demo.sweep_crash(), 1)
        self.assertEqual(
            self.demo.crash_status({"token": start["token"]})["status"],
            "unknown")
        self.demo.books.assert_balanced()

    def test_crash_live_rounds_land_in_history(self):
        start = self.demo.crash_start({"player": self.player,
                                       "game_id": "demo:crash-nitro",
                                       "stake_minor": 200})
        token = start["token"]
        round_id = self.demo.crash_pending[token]["round_id"]
        self.demo.crash_cashout({"player": self.player, "token": token})
        rows = [r for r in self.demo.history(self.player)
                if r["round_id"] == round_id]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["game_id"], "demo:crash-nitro")
        self.assertIn("unit", rows[0])

    def test_crash_live_boot_voids_a_debited_round(self):
        # a round debited but never settled must be refunded at boot
        before = self.demo.books.available(self.player)
        self.demo.crash_start({"player": self.player,
                               "game_id": "demo:crash-nitro",
                               "stake_minor": 200})
        self.assertEqual(self.demo.books.available(self.player), before - 200)
        revived = Demo(data_dir=self.tmp)  # simulates a restart
        self.assertEqual(revived.books.available(self.player), before)
        self.assertEqual(revived.crash_pending, {})
        revived.books.assert_balanced()

    def test_plinko_path_is_12_bits_and_edge_pays_130x(self):
        from demo import arcade
        path = arcade.plinko_path(arcade.PLINKO_GAME_ID, "p1")
        self.assertEqual(len(path), 12)
        self.assertTrue(all(b in (0, 1) for b in path))
        res = arcade.plinko_round(arcade.PLINKO_GAME_ID, "p1", 200)
        self.assertEqual(res.symbols[1], f"slot {sum(path)}")
        edge = next(arcade.plinko_round(arcade.PLINKO_GAME_ID, f"pe-{i}",
                                        200)
                    for i in range(20000)
                    if sum(arcade.plinko_path(arcade.PLINKO_GAME_ID,
                                              f"pe-{i}")) in (0, 12))
        self.assertEqual(edge.multiplier, "130")
        self.assertEqual(edge.payout_minor, 26000)

    def test_plinko_rtp_is_97_16_percent(self):
        from demo import arcade
        self.assertAlmostEqual(arcade.plinko_theoretical_rtp(),
                               0.971631, places=6)

    def test_plinko_partial_return_settles_below_stake(self):
        from demo import arcade
        low = next(arcade.plinko_round(arcade.PLINKO_GAME_ID, f"pl-{i}",
                                       200)
                   for i in range(3000)
                   if arcade.PLINKO_MULTIPLIERS[sum(
                       arcade.plinko_path(arcade.PLINKO_GAME_ID,
                                          f"pl-{i}"))] == 0.2)
        self.assertEqual(low.payout_minor, 40)
        before = self.demo.books.available(self.player)
        row = self.demo.spin({"player": self.player,
                              "game_id": "demo:plinko-drops",
                              "stake_minor": 200,
                              "round_id": low.round_id})
        # same round id as the probe: the books mirror the engine exactly
        self.assertEqual(row["payout_minor"], low.payout_minor)
        self.assertEqual(self.demo.books.available(self.player),
                         before - 200 + low.payout_minor)
        self.demo.books.assert_balanced()

    def test_mines_hit_loses_and_clean_pays_the_formula(self):
        from demo import arcade
        field = arcade.mines_field(arcade.MINES_GAME_ID, "m1", 3)
        self.assertEqual(len(field), 3)
        self.assertEqual(field, arcade.mines_field(
            arcade.MINES_GAME_ID, "m1", 3))
        hit_cell = field[0]
        lost = arcade.mines_round(arcade.MINES_GAME_ID, "m1",
                                  f"m=3:cells={hit_cell}", 200)
        self.assertFalse(lost.is_win)
        self.assertEqual(lost.payout_minor, 0)
        safe = [c for c in range(1, 26) if c not in set(field)][:3]
        won = arcade.mines_round(
            arcade.MINES_GAME_ID, "m1",
            f"m=3:cells={','.join(map(str, safe))}", 200)
        self.assertTrue(won.is_win)
        import math
        expected = (200 * 97 * math.comb(25, 3)) // (100 * math.comb(22, 3))
        self.assertEqual(won.payout_minor, expected)

    def test_mines_selection_is_validated(self):
        from demo import arcade
        for bad in (None, "", "3", "m=0:cells=1", "m=25:cells=1",
                    "m=3:cells=1,1", "m=3:cells=0", "m=3:cells=26",
                    "m=24:cells=1,2"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                arcade.mines_round(arcade.MINES_GAME_ID, "mx", bad, 200)

    def test_mines_rtp_is_97_percent_minus_dust(self):
        from demo import arcade
        staked = paid = 0
        for i in range(4000):
            r = arcade.mines_round(arcade.MINES_GAME_ID, f"mr-{i}",
                                   "m=3:cells=1,7,25", 200)
            staked += 200
            paid += r.payout_minor
        self.assertGreater(paid / staked, 0.93)
        self.assertLess(paid / staked, 1.0)

    def test_arcade_titles_are_certified_and_categorized(self):
        rows = {g["game_id"]: g for g in self.demo.catalog()}
        for gid, rtp in (("demo:crash-nitro", "97.00"),
                         ("demo:plinko-drops", "97.16"),
                         ("demo:minas", "97.00")):
            self.assertEqual(rows[gid]["category"], "Crash", gid)
            self.assertEqual(rows[gid]["rtp"], rtp, gid)
            cert = self.demo.registry.assert_launchable(gid)
            self.assertTrue(cert.certificate_id.startswith("BR-DEMO-000"))

    def test_arcade_rounds_land_in_history(self):
        self.demo.spin({"player": self.player, "game_id": "demo:minas",
                        "stake_minor": 200, "selection": "m=3:cells=1,7,25",
                        "round_id": "arc-h1"})
        rows = [r for r in self.demo.history(self.player)
                if r["round_id"] == "arc-h1"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["game_id"], "demo:minas")
        self.assertIn("unit", rows[0])


class DiceTest(unittest.TestCase):
    """In-house dice original (decision 0034): one sha256 draw on a 0.01
    roll grid; under/over a target. A win pays 0.97 / P(win), which can be
    below the stake on a high-probability bet (settles through
    settle_casino). RTP 97% on every selection, minus rounding dust."""

    GAME = "demo:dados"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)
        self.player = self.demo.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })["player_id"]
        self.demo.deposit({"player": self.player, "amount_minor": 100000,
                           "method": "pix", "deposit_id": "dice-dep"})

    @staticmethod
    def _round_with_roll(pred, limit=5000):
        from demo import arcade
        for i in range(limit):
            rid = f"dice-{i}"
            if pred(arcade.dice_roll(arcade.DICE_GAME_ID, rid)):
                return rid
        raise AssertionError("no round id matched the roll predicate")

    def test_dice_selection_is_validated(self):
        from demo import arcade
        for bad in (None, "", "50", "under", "under:", "over:abc",
                    "under:0.5", "over:99.5", "high:50", "under:100"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                arcade.parse_dice_selection(bad)
        self.assertEqual(arcade.parse_dice_selection("under:50.00"),
                         ("under", 50.0))
        self.assertEqual(arcade.parse_dice_selection("OVER:2,5"),
                         ("over", 2.5))

    def test_dice_win_chance_and_multiplier(self):
        from demo import arcade
        self.assertAlmostEqual(arcade.dice_win_chance("under", 50.0), 0.5)
        self.assertAlmostEqual(arcade.dice_win_chance("under", 25.0), 0.25)
        self.assertAlmostEqual(arcade.dice_win_chance("over", 99.0), 0.0099)
        self.assertAlmostEqual(arcade.dice_multiplier("under", 50.0),
                               1.94, places=4)
        self.assertAlmostEqual(arcade.dice_multiplier("under", 2.0),
                               48.5, places=4)

    def test_dice_rtp_is_97_percent(self):
        from demo import arcade
        for direction, target in (("under", 2.0), ("under", 50.0),
                                  ("under", 75.0), ("over", 25.0),
                                  ("over", 50.0), ("over", 98.0)):
            rtp = arcade.dice_rtp(direction, target)
            self.assertAlmostEqual(rtp, 0.97, delta=0.005,
                                   msg=f"{direction} {target}: {rtp}")

    def test_dice_is_deterministic(self):
        from demo import arcade
        a = arcade.dice_round(self.GAME, "dx", "under:50.00", 200)
        b = arcade.dice_round(self.GAME, "dx", "under:50.00", 200)
        self.assertEqual(a, b)

    def test_dice_normal_win_settles_through_the_books(self):
        rid = self._round_with_roll(lambda r: r < 50.0)
        before = self.demo.books.available(self.player)
        row = self.demo.spin({"player": self.player, "game_id": self.GAME,
                              "stake_minor": 200, "selection": "under:50.00",
                              "round_id": rid})
        self.assertEqual(row["payout_minor"], 388)  # 200 x 1.94
        self.assertEqual(self.demo.books.available(self.player),
                         before - 200 + 388)
        self.demo.books.assert_balanced()

    def test_dice_high_chance_win_can_pay_below_the_stake(self):
        rid = self._round_with_roll(lambda r: r < 99.0)
        before = self.demo.books.available(self.player)
        row = self.demo.spin({"player": self.player, "game_id": self.GAME,
                              "stake_minor": 200, "selection": "under:99.00",
                              "round_id": rid})
        self.assertGreater(row["payout_minor"], 0)     # it did win
        self.assertLess(row["payout_minor"], 200)      # ...but paid under
        self.assertEqual(self.demo.books.available(self.player),
                         before - 200 + row["payout_minor"])
        self.demo.books.assert_balanced()

    def test_dice_loss_pays_nothing(self):
        rid = self._round_with_roll(lambda r: r > 98.0)
        before = self.demo.books.available(self.player)
        row = self.demo.spin({"player": self.player, "game_id": self.GAME,
                              "stake_minor": 200, "selection": "under:50.00",
                              "round_id": rid})
        self.assertEqual(row["payout_minor"], 0)
        self.assertEqual(self.demo.books.available(self.player), before - 200)
        self.demo.books.assert_balanced()

    def test_dice_requires_a_selection(self):
        with self.assertRaises(ValueError):
            self.demo.spin({"player": self.player, "game_id": self.GAME,
                            "stake_minor": 200, "round_id": "dx-req"})

    def test_dice_is_certified_and_categorized(self):
        rows = {g["game_id"]: g for g in self.demo.catalog()}
        self.assertEqual(rows[self.GAME]["category"], "Originais")
        self.assertEqual(rows[self.GAME]["rtp"], "97.00")
        cert = self.demo.registry.assert_launchable(self.GAME)
        self.assertEqual(cert.certificate_id, "BR-DEMO-0009")

    def test_dice_round_lands_in_history(self):
        rid = self._round_with_roll(lambda r: r < 50.0)
        self.demo.spin({"player": self.player, "game_id": self.GAME,
                        "stake_minor": 200, "selection": "under:50.00",
                        "round_id": rid})
        rows = [r for r in self.demo.history(self.player)
                if r["round_id"] == rid]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["game_id"], self.GAME)
        self.assertIn("unit", rows[0])


class SpribeTheaterTest(unittest.TestCase):
    """Spribe wallet mirror (decision 0031): the theater bridges the game's
    operator channel (`ifc.make.bet` / `ifc.win.info` / `ifc.end.round`) to
    `POST /api/wallet/round` and pushes our saldo back (`ifc.set.balance`).
    Settlement itself is the covered wallet_round path; this guards the
    wiring markers in the shipped component."""

    COMPONENT = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "web", "app", "components",
        "GameTheater.jsx")

    def test_theater_bridges_the_operator_channel(self):
        with open(self.COMPONENT, encoding="utf-8") as handle:
            src = handle.read()
        for marker in ("ifc.make.bet", "ifc.win.info", "ifc.end.round",
                       "ifc.set.balance", "ifc.cancel.bet",
                       "/api/wallet/round", "spribe:"):
            self.assertIn(marker, src)

    def test_reported_spribe_rounds_settle_like_socket_rounds(self):
        demo = Demo(data_dir=tempfile.mkdtemp())
        player = demo.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })["player_id"]
        demo.deposit({"player": player, "amount_minor": 10000,
                      "method": "pix", "deposit_id": "sp-dep"})
        token = demo.wallet_launch(
            {"player": player, "game_id": "spribe:aviator"})["token"]
        # cashout at 1.28x on a R$1 stake, as the theater reports it
        demo.wallet_round({"token": token, "round_id": "spribe-1-7",
                           "stake_minor": 100, "payout_minor": 128})
        self.assertEqual(demo.books.available(player), 10028)
        # a bust settles the stake as a loss
        demo.wallet_round({"token": token, "round_id": "spribe-1-8",
                           "stake_minor": 100, "payout_minor": 0})
        self.assertEqual(demo.books.available(player), 9928)
        demo.books.assert_balanced()


class WalletSyncTest(unittest.TestCase):
    """Publisher-game wallet (operator side): a launch token binds a session
    to one player, a reported stake and win settle through the books, and an
    empty saldo blocks the spin with a deposit message."""

    GAME = "pp:gates-of-olympus"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)
        self.player = self.demo.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })["player_id"]

    def _launch(self):
        return self.demo.wallet_launch(
            {"player": self.player, "game_id": self.GAME})

    def test_empty_wallet_cannot_play_and_says_deposit(self):
        start = self._launch()
        self.assertFalse(start["can_play"])
        self.assertIn("deposite", start["message"])
        self.assertEqual(start["balance_minor"], 0)
        with self.assertRaises(ValueError):
            self.demo.wallet_debit(
                {"token": start["token"], "round_id": "r0", "stake_minor": 200})
        self.demo.books.assert_balanced()

    def test_funded_wallet_can_play(self):
        self.demo.deposit({"player": self.player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "ws-dep"})
        start = self._launch()
        self.assertTrue(start["can_play"])
        self.assertEqual(start["balance_minor"], 10000)

    def test_debit_then_credit_settles_an_arbitrary_payout(self):
        self.demo.deposit({"player": self.player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "ws-dep"})
        start = self._launch()
        token = start["token"]
        debit = self.demo.wallet_debit(
            {"token": token, "round_id": "r1", "stake_minor": 200})
        self.assertTrue(debit["accepted"])
        self.assertEqual(self.demo.books.available(self.player), 9800)
        # a publisher win smaller than the stake is still a win
        credit = self.demo.wallet_credit(
            {"token": token, "round_id": "r1", "payout_minor": 84})
        self.assertTrue(credit["settled"])
        self.assertEqual(self.demo.books.available(self.player), 9800 + 84)
        self.assertEqual(self.demo.history(self.player)[0]["type"],
                         "publisher")
        self.demo.books.assert_balanced()

    def test_credit_can_exceed_the_stake(self):
        self.demo.deposit({"player": self.player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "ws-dep"})
        token = self._launch()["token"]
        self.demo.wallet_debit(
            {"token": token, "round_id": "r2", "stake_minor": 500})
        self.demo.wallet_credit(
            {"token": token, "round_id": "r2", "payout_minor": 1750})
        self.assertEqual(self.demo.books.available(self.player),
                         10000 - 500 + 1750)
        self.demo.books.assert_balanced()

    def test_unknown_game_is_refused(self):
        with self.assertRaises(ValueError):
            self.demo.wallet_launch(
                {"player": self.player, "game_id": "demo:not-a-publisher"})

    def test_bad_token_is_refused(self):
        with self.assertRaises(KeyError):
            self.demo.wallet_debit(
                {"token": "nope", "round_id": "r", "stake_minor": 200})

    def test_replayed_round_is_refused(self):
        self.demo.deposit({"player": self.player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "ws-dep"})
        token = self._launch()["token"]
        self.demo.wallet_debit(
            {"token": token, "round_id": "dup", "stake_minor": 200})
        with self.assertRaises(ValueError):
            self.demo.wallet_debit(
                {"token": token, "round_id": "dup", "stake_minor": 200})
        self.demo.books.assert_balanced()


class SocketRoundTest(unittest.TestCase):
    """Rounds a publisher drives over the page's own socket (Play'n GO's
    SignalR hub), reported by the injected bridge: the net settles on our
    books, once per round."""

    GAME = "pgo:book-of-dead"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.demo = Demo(data_dir=self.tmp)
        self.player = self.demo.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })["player_id"]
        self.demo.deposit({"player": self.player, "amount_minor": 10000,
                           "method": "pix", "deposit_id": "sr-dep"})
        self.token = self.demo.wallet_launch(
            {"player": self.player, "game_id": self.GAME})["token"]

    def test_a_reported_round_settles_the_net(self):
        self.demo.wallet_round({"token": self.token, "round_id": "ws-1",
                                "stake_minor": 100, "payout_minor": 0})
        self.assertEqual(self.demo.books.available(self.player), 9900)
        self.demo.wallet_round({"token": self.token, "round_id": "ws-2",
                                "stake_minor": 100, "payout_minor": 250})
        self.assertEqual(self.demo.books.available(self.player),
                         9900 - 100 + 250)
        self.demo.books.assert_balanced()
        rounds = [r for r in self.demo.history(self.player)
                  if r.get("type") == "publisher"]
        self.assertEqual(rounds[0]["game_id"], self.GAME)

    def test_a_replayed_round_is_not_charged_twice(self):
        self.demo.wallet_round({"token": self.token, "round_id": "dup",
                                "stake_minor": 100, "payout_minor": 0})
        again = self.demo.wallet_round({"token": self.token, "round_id": "dup",
                                        "stake_minor": 100, "payout_minor": 0})
        self.assertTrue(again.get("replayed"))
        self.assertEqual(self.demo.books.available(self.player), 9900)
        self.demo.books.assert_balanced()

    def test_a_bad_token_or_amount_is_refused(self):
        with self.assertRaises(KeyError):
            self.demo.wallet_round({"token": "nope", "round_id": "x",
                                    "stake_minor": 100})
        with self.assertRaises(ValueError):
            self.demo.wallet_round({"token": self.token, "round_id": "",
                                    "stake_minor": 100})
        with self.assertRaises(ValueError):
            self.demo.wallet_round({"token": self.token, "round_id": "x",
                                    "stake_minor": 100, "payout_minor": -5})

    def test_the_bridge_taps_the_publisher_socket(self):
        from demo import game_proxy
        js = game_proxy.bridge_script().decode("utf-8")
        self.assertIn("gamehub", js)          # only the game hub is tapped
        self.assertIn("wallet/round", js)     # settlement goes to the wallet
        self.assertIn("Saldo insuficiente", js)


class GameProxyTest(unittest.TestCase):
    """Publisher game proxy (decision 0022): a same-origin front so the game's
    own calls reach our wallet, and the balance it shows is ours."""

    GAME = "pp:gates-of-olympus"
    HOST = "demogamesfree.pragmaticplay.net"

    def test_launcher_maps_to_the_demo_url(self):
        from demo import game_proxy
        game = game_proxy.game_for(self.GAME)
        self.assertIsNotNone(game)
        self.assertEqual(game_proxy.target_url(game, "", ""),
                         game["demo_url"])

    def test_encoded_game_id_path_is_decoded(self):
        """The browser sends the id url-encoded (":" is "%3A"); the
        encoded id is longer, so it must be decoded before use."""
        from demo import game_proxy
        parts = game_proxy.split_game_path(f"/g/{quote(self.GAME)}")
        self.assertEqual(parts, (self.GAME, ""))
        parts = game_proxy.split_game_path(
            f"/g/{quote(self.GAME)}/_abs/{self.HOST}/gs2c/play.do")
        self.assertEqual(parts, (self.GAME, f"_abs/{self.HOST}/gs2c/play.do"))
        self.assertIsNone(game_proxy.split_game_path("/api/wallet/status"))

    def test_absolute_and_relative_targets(self):
        from demo import game_proxy
        game = game_proxy.game_for(self.GAME)
        absolute = game_proxy.target_url(
            game, f"_abs/{self.HOST}/gs2c/play.do", "a=1")
        self.assertEqual(absolute, f"https://{self.HOST}/gs2c/play.do?a=1")
        relative = game_proxy.target_url(
            game, "gs2c/common/js/x.js", "")
        self.assertTrue(relative.startswith(f"https://{self.HOST}/"))

    def test_unknown_host_is_refused(self):
        from demo import game_proxy
        game = game_proxy.game_for(self.GAME)
        with self.assertRaises(game_proxy.ProxyError):
            game_proxy.target_url(
                game, "_abs/evil.example/x.js", "")

    def test_only_money_urls_move_to_our_origin(self):
        """Only the RGS/wallet endpoints are rewritten; the game client
        and its data keep pointing at the publisher's CDN. Proxying the
        assets is what deserialized an empty game root (decision 0025)."""
        from demo import game_proxy
        money = game_proxy.MONEY_PATHS["pragmatic_play"]
        html = (
            '{"gameService":"https://demogamesfree.pragmaticplay.net'
            '/gs2c/ge/v3/gameService","datapath":"https://demogamesfree'
            '.pragmaticplay.net/gs2c/common/v3/games-html5/games/vs/'
            'vs20olympgate/"}'
        ).encode()
        out = game_proxy.rewrite_urls(
            html, "application/json", self.GAME,
            "http://127.0.0.1:8765", money).decode("utf-8")
        # the RGS service is ours...
        self.assertIn(
            "http://127.0.0.1:8765/g/pp:gates-of-olympus"
            "/_abs/demogamesfree.pragmaticplay.net/gs2c/ge/v3/gameService",
            out)
        # ...while the asset base is still the publisher's
        self.assertIn(
            "https://demogamesfree.pragmaticplay.net/gs2c/common"
            "/v3/games-html5/games/vs/vs20olympgate/", out)

    def test_assets_stay_on_the_publisher(self):
        from demo import game_proxy
        money = game_proxy.MONEY_PATHS["pragmatic_play"]
        js = (
            'load("https://demogamesfree.pragmaticplay.net/gs2c/common'
            '/v3/games-html5/games/vs/vs20olympgate/desktop/build.js")'
        ).encode()
        out = game_proxy.rewrite_urls(
            js, "text/javascript", self.GAME,
            "http://127.0.0.1:8765", money)
        self.assertEqual(js, out)

    def test_publisher_subdomains_are_allowed_lookalikes_are_not(self):
        """A publisher serves each game from its own subdomain (Spribe uses
        `<game>-demo.spribegaming.com`), so a publisher's domain is allowed by
        suffix — but the leading dot still refuses a lookalike."""
        from demo import game_proxy
        self.assertTrue(game_proxy.allowed_host("aviator-demo.spribegaming.com"))
        self.assertTrue(game_proxy.allowed_host("app-config.spribegaming.com"))
        self.assertFalse(game_proxy.allowed_host("evil-spribegaming.com"))
        self.assertFalse(game_proxy.allowed_host("spribegaming.com.evil.example"))

    def test_a_service_host_is_routed_through_us(self):
        """Spribe's config host answers 403 to browser-like requests and sends
        no CORS, so the game cannot read it directly; its URL is rewritten
        onto our origin and fetched server-side (decision 0027)."""
        from demo import game_proxy
        js = b'appConfigPath:"https://app-config.spribegaming.com/aviator/"'
        out = game_proxy.rewrite_urls(
            js, "text/javascript", "spribe:aviator",
            "http://127.0.0.1:8765").decode("utf-8")
        self.assertIn("http://127.0.0.1:8765/g/spribe:aviator/_abs/"
                      "app-config.spribegaming.com/aviator/", out)
        self.assertNotIn("https://app-config.spribegaming.com", out)

    def test_spribe_mirroring_is_switched_off(self):
        """Spribe rewrites the vendor's hosts onto the site's own domain
        (app-demo2.spribegaming.com -> app-demo2.<ours>), which a personal
        deploy cannot resolve; the served bundle must keep the real hosts, or
        the game sits on its connection screen forever (decision 0027)."""
        from demo import game_proxy
        js = ('mirrorURL(t){return this.mirrorHostname(i.hostname)}'
              'mirrorHostname(t){if(!f_.isDomainMirroringEnabled)return t;'
              'return t.replace(".a.b",".c.d)")}')
        out = game_proxy.patch_spribe_client(js)
        self.assertIn("mirrorHostname(t){return t;if(!f_", out)
        # a call site (no body brace) is left alone
        self.assertIn("this.mirrorHostname(i.hostname)", out)

    def test_a_redirect_target_maps_back_through_us(self):
        """A launcher redirect is handed to the browser rewritten onto our
        origin, so the session it minted stays in the browser's URL."""
        from demo import game_proxy
        game = game_proxy.game_for("spribe:aviator")
        url = game_proxy.target_url(
            game, "_abs/aviator-demo.spribegaming.com/",
            "operator=demo&user=1&token=x")
        self.assertEqual(
            url,
            "https://aviator-demo.spribegaming.com/?operator=demo&user=1&token=x")

    def test_rewrite_without_origin_is_a_noop(self):
        from demo import game_proxy
        js = b'load("https://demogamesfree.pragmaticplay.net/x.js")'
        self.assertEqual(
            js, game_proxy.rewrite_urls(js, "text/javascript",
                                        self.GAME, ""))

    def test_balance_is_replaced_with_ours(self):
        from demo import game_proxy
        body = (b"action=doInit&balance=100,000.00&balance_cash=100,000.00"
                b"&balance_bonus=0.00&rt=d")
        out = game_proxy.rewrite_balance(body, 2000).decode("utf-8")
        self.assertIn("balance=20.00", out)
        self.assertIn("balance_cash=20.00", out)
        self.assertIn("balance_bonus=0.00", out)
        # thousands separators survive
        self.assertIn("1,234.56",
                      game_proxy.rewrite_balance(
                          b"balance=0.00", 123456).decode("utf-8"))
        # a body without balance fields is untouched
        self.assertEqual(b"action=doInit", game_proxy.rewrite_balance(
            b"action=doInit", 2000))

    def test_inject_bridge_adds_config_and_loads_first(self):
        from demo import game_proxy
        html = b"<html><head><title>x</title></head><body></body></html>"
        out = game_proxy.inject_bridge(
            html, self.GAME, "tok123",
            {"balance_minor": 2000, "bonus_minor": 0, "min_stake_minor": 200,
             "can_play": True})
        self.assertIn(b"window.__WALLET__", out)
        self.assertIn(b'"token": "tok123"', out)
        self.assertIn(b"/g/bridge.js", out)
        self.assertLess(out.index(b"window.__WALLET__"), out.index(b"<title>"))

    def test_bridge_blocks_and_names_the_wallet(self):
        from demo import game_proxy
        js = game_proxy.bridge_script().decode("utf-8")
        self.assertIn("Saldo insuficiente", js)
        self.assertIn("wallet/status", js)

    def test_bridge_only_injected_for_a_valid_token(self):
        demo = Demo(data_dir=tempfile.mkdtemp())
        self.assertIsNone(demo.wallet_view_for("nope"))
        player = demo.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })["player_id"]
        start = demo.wallet_launch({"player": player, "game_id": self.GAME})
        view = demo.wallet_view_for(start["token"])
        self.assertIsNotNone(view)
        self.assertFalse(view["can_play"])


class RgsProxyTest(unittest.TestCase):
    """Hacksaw is interposed at the RGS, not through the page proxy."""

    PROVIDER = "hacksaw_gaming"
    GAME = "hs:rip-city-dice"

    def test_paths_are_split_and_unknown_providers_refused(self):
        from demo import rgs_proxy
        self.assertEqual(
            rgs_proxy.split_path("/rgs/hacksaw_gaming/api/play/authenticate"),
            ("hacksaw_gaming", "api/play/authenticate"))
        self.assertIsNone(rgs_proxy.split_path("/api/catalog"))
        self.assertIsNone(rgs_proxy.split_path("/rgs/nope/api/play"))
        self.assertIsNone(rgs_proxy.split_path("/rgs/hacksaw_gaming"))

    def test_upstream_url_maps_the_api_segment(self):
        from demo import rgs_proxy
        self.assertEqual(
            rgs_proxy.upstream_url(self.PROVIDER, "api/play/authenticate"),
            "https://rgs-demo.hacksawgaming.com/api/play/authenticate")

    def test_env_points_at_our_interposition(self):
        from demo import rgs_proxy
        self.assertEqual(
            rgs_proxy.env_url("http://127.0.0.1:8765", self.PROVIDER),
            "http://127.0.0.1:8765/rgs/hacksaw_gaming/api")

    def test_launch_url_swaps_env_and_token_only(self):
        """The launcher keeps its parameters; its RGS base and
        session token are pointed at us, and it is served from our
        own origin so the money calls are same-origin."""
        demo = Demo(data_dir=tempfile.mkdtemp())
        url = demo.interposed_launch(self.GAME, "tok123",
                                     "http://127.0.0.1:8765")
        from urllib.parse import parse_qs, urlparse
        parts = urlparse(url)
        query = parse_qs(parts.query)
        self.assertEqual(parts.netloc, "127.0.0.1:8765")
        self.assertEqual(parts.path, f"/g/{self.GAME}/")
        self.assertEqual(query["env"][0],
                         "http://127.0.0.1:8765/rgs/hacksaw_gaming/api")
        self.assertEqual(query["token"][0], "tok123")
        # everything else the launcher needs survives
        self.assertEqual(query["gameid"][0], "2725")
        self.assertEqual(query["channel"][0], "desktop")

    def test_page_proxy_providers_have_no_interposed_url(self):
        demo = Demo(data_dir=tempfile.mkdtemp())
        self.assertEqual(
            demo.interposed_launch("pp:gates-of-olympus", "tok",
                                   "http://127.0.0.1:8765"), "")

    def test_the_publishers_token_is_swapped_back_in(self):
        from demo import rgs_proxy
        self.assertEqual(rgs_proxy.demo_token(self.PROVIDER), "demo")
        body = b'{"seq":1,"gameId":2725,"token":"ours123"}'
        forwarded = rgs_proxy.swap_token(body, "demo")
        self.assertEqual(rgs_proxy.session_token(body), "ours123")
        self.assertEqual(json.loads(forwarded.decode())["token"], "demo")

    def test_balance_is_swapped_in_every_shape(self):
        """The RGS states money as cents in plain integers and with
        a decimal only when there is a fraction; our saldo goes
        back in the same shape it found."""
        from demo import rgs_proxy
        body = (b'{"accountBalance":{"balance":"500000",'
                b'"realBalance":10000.0},'
                b'"other":{"cash":"1,234.56"}}')
        import json as _json
        payload = _json.loads(rgs_proxy.replace_balance(body, 2000).decode())
        self.assertEqual(payload["accountBalance"]["balance"], "2000")
        self.assertEqual(payload["accountBalance"]["realBalance"], 2000.0)
        self.assertEqual(payload["other"]["cash"], "2000")

    def test_a_session_is_followed_by_its_uuid(self):
        """Only the first call carries our token; the rest name the
        session, and the money still has to reach the wallet."""
        from demo import rgs_proxy
        self.assertEqual(
            rgs_proxy.session_uuid(b'{"sessionUuid":"abc","seq":2}'), "abc")
        self.assertEqual(rgs_proxy.session_token(b'{"seq":2}'), "")
        demo = Demo(data_dir=tempfile.mkdtemp())
        demo.rgs_bind("hacksaw_gaming", "abc", "tok123")
        self.assertEqual(
            demo.rgs_token("hacksaw_gaming", "abc"), "tok123")
        self.assertEqual(demo.rgs_token("hacksaw_gaming", "zzz"), "")

    def test_the_stake_comes_from_the_call(self):
        """The game stakes in the call; a continuation carries none."""
        from demo import rgs_proxy
        body = b'{"seq":2,"sessionUuid":"s1","bets":[{"betAmount":"200"}]}'
        self.assertEqual(rgs_proxy.bet_total(body), 200)
        self.assertEqual(
            rgs_proxy.bet_total(b'{"seq":3,"sessionUuid":"s1"}'), 0)

    def test_the_win_accrues_until_the_round_finishes(self):
        from demo import rgs_proxy
        playing = (b'{"round":{"roundId":"9","status":"wfwpc","events":'
                   b'[{"awa":"0"},{"awa":"400"}]}}')
        state = rgs_proxy.round_state(playing)
        self.assertEqual(state["win"], 400)
        self.assertFalse(state["done"])
        done = (b'{"round":{"roundId":"9","status":"completed","events":[]},'
                b'"accountBalance":{"balance":"500000"}}')
        state = rgs_proxy.round_state(done)
        self.assertEqual(state["id"], "9")
        self.assertTrue(state["done"])

    def test_cors_allows_the_publisher_origin(self):
        from demo import rgs_proxy
        headers = rgs_proxy.cors_headers("https://static-live.hacksawgaming.com")
        self.assertEqual(
            headers["Access-Control-Allow-Origin"],
            "https://static-live.hacksawgaming.com")
        self.assertIn("POST", headers["Access-Control-Allow-Methods"])

    def test_a_reported_round_settles_once(self):
        demo = Demo(data_dir=tempfile.mkdtemp())
        player = demo.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })["player_id"]
        demo.deposit({"player": player, "amount_minor": 2000})
        demo.settle_rgs_round(player, self.GAME, "hs:1", 200, 5000)
        after_win = demo.wallet_view_for(
            demo.wallet_launch({"player": player, "game_id": self.GAME}
                               )["token"])["balance_minor"]
        self.assertEqual(after_win, 2000 - 200 + 5000)
        # the same round cannot be charged twice
        demo.settle_rgs_round(player, self.GAME, "hs:1", 200, 5000)
        replay = demo.wallet_view_for(
            demo.wallet_launch({"player": player, "game_id": self.GAME}
                               )["token"])["balance_minor"]
        self.assertEqual(replay, after_win)


class _Upstream:
    """A publisher answer, handed back by a stubbed opener."""

    def __init__(self, body: bytes = b"", status: int = 200,
                 headers: dict | None = None):
        self.status = status
        self.headers = dict(headers or {})
        self._body = body

    def read(self, amount=None):
        return self._body if amount is None else self._body[:amount]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Opener:
    """Stands in for a urllib opener: records the request, replays an answer."""

    def __init__(self, answer):
        self.answer = answer
        self.seen: list = []

    def open(self, req, timeout=None):
        self.seen.append(req)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


class ProxyFetchTest(unittest.TestCase):
    """What the proxy does with a publisher answer, upstream stubbed."""

    HOST = f"https://{GameProxyTest.HOST}/asset.js"

    def _fetch(self, answer, **kwargs):
        from demo import game_proxy
        opener = _Opener(answer)
        keep = game_proxy._FOLLOW_OPENER
        game_proxy._FOLLOW_OPENER = opener
        try:
            return game_proxy.fetch(self.HOST, **kwargs), opener
        finally:
            game_proxy._FOLLOW_OPENER = keep

    def test_an_upstream_error_is_read_and_closed_not_left_open(self):
        """A publisher 404 is a real answer; leaving its file object open holds
        the connection for the life of the process (one per broken asset)."""
        (status, headers, body), _ = self._fetch(
            urllib.error.HTTPError(self.HOST, 404, "Not Found", {}, None))
        self.assertEqual(status, 404)
        self.assertEqual(body, b"")

    def test_an_oversized_answer_is_refused_not_truncated(self):
        """Half a bundle is the one answer that cannot be served: the client
        deserializes it and dies on its loader with nothing to go on."""
        from demo import game_proxy
        keep = game_proxy.MAX_BODY
        game_proxy.MAX_BODY = 16
        try:
            with self.assertRaises(game_proxy.ProxyError):
                self._fetch(_Upstream(b"x" * 64))
        finally:
            game_proxy.MAX_BODY = keep

    def test_only_the_negotiation_headers_reach_the_publisher(self):
        """The browser's cookies and sec-ch-* must not ride along: they are the
        client's, not the game's, and the RGS keys off the token we swap."""
        (status, _headers, _body), opener = self._fetch(
            _Upstream(b"ok"), headers={"Cookie": "wallet_token=secret",
                                      "Content-Type": "application/json",
                                      "If-None-Match": '"v1"',
                                      "X-Secret": "no"})
        sent = {k.lower() for k in opener.seen[0].headers}
        self.assertIn("if-none-match", sent)
        self.assertNotIn("cookie", sent)
        self.assertNotIn("x-secret", sent)

    def test_a_url_that_leaves_the_publisher_is_refused(self):
        """Userinfo and network-path spellings move a URL off the publisher;
        the mapping refuses them itself, not only the fetch."""
        from demo import game_proxy
        host = GameProxyTest.HOST
        for url in (f"http://{host}/x.js", f"https://{host}@evil.example/x.js",
                    "https://evil.example/x.js", "//evil.example/x.js",
                    f"https://{host}.evil.example/x.js"):
            with self.assertRaises(game_proxy.ProxyError, msg=url):
                game_proxy.checked_url(url)
        game = game_proxy.game_for(GameProxyTest.GAME)
        with self.assertRaises(game_proxy.ProxyError):
            game_proxy.target_url(game, "_abs/@evil.example/x.js", "")

    def test_our_own_query_parameter_never_reaches_the_publisher(self):
        from demo import game_proxy
        self.assertEqual(
            game_proxy.publisher_query("a=1&wallet_token=secret&b=2"), "a=1&b=2")
        self.assertEqual(game_proxy.publisher_query("wallet_token=secret"), "")
        # `token` is ours on a direct launch, and the game's own plumbing when
        # it is reading its session off the launcher to hand back to us
        self.assertEqual(game_proxy.publisher_query("token=secret"), "")
        self.assertEqual(game_proxy.publisher_query("token=secret", ("token",)),
                         "token=secret")

    def test_a_client_bundle_is_patched_only_as_script(self):
        """The same bytes as a document must not be rewritten: the
        substitution would land inside markup the publisher wrote."""
        from demo import game_proxy
        js = ('mirrorHostname(t){if(!f_.isDomainMirroringEnabled)return t;}'
              'return t.replace(".a.b",".c.d")}')
        as_js = game_proxy.rewrite_urls(
            js.encode(), "text/javascript", "spribe:aviator",
            "http://127.0.0.1:8765")
        self.assertIn(b"mirrorHostname(t){return t;", as_js)
        for ctype in ("text/html", "application/json"):
            self.assertEqual(
                js.encode(),
                game_proxy.rewrite_urls(js.encode(), ctype, "spribe:aviator",
                                        "http://127.0.0.1:8765"), ctype)

    def test_a_base_tag_is_matched_whatever_it_is_written_like(self):
        """`<base href='/'>` and a base with no href get the same repair; the
        silent miss is a game that loads nothing and says nothing."""
        from demo import game_proxy
        base = "/g/spribe:aviator/_abs/aviator-demo.spribegaming.com/"
        for html in (b"<head><base href=\"/\"><title>x</title>",
                     b"<head><base href='/' >",
                     b'<head><BASE HREF="https://x.y/">',
                     b"<head><base target=_top>"):
            self.assertIn(base, game_proxy.rebase(html, base).decode(), html)
        # nothing to point at: the document is untouched
        self.assertEqual(b"<head><title>x</title>",
                         game_proxy.rebase(b"<head><title>x</title>", base))

    def test_the_bridge_config_cannot_close_its_own_script(self):
        """The launch symbol is third-party text landing in a `<script>`; JSON
        escapes quotes but not `<`, which is all `</script>` needs."""
        keep = game_proxy.game_for

        def hostile(game_id):
            game = dict(keep(game_id) or {})
            game["demo_url"] = ("https://x.example/?lang=pt&"
                                "gameSymbol=</script><script>alert(1)")
            return game

        game_proxy.game_for = hostile
        try:
            body = game_proxy.inject_bridge(
                b"<html><head></head></html>", GameProxyTest.GAME, "tok",
                {"balance_minor": 0}).decode("utf-8")
        finally:
            game_proxy.game_for = keep
        self.assertIn("\\u003c/script\\u003e", body)
        self.assertEqual(body.count("</script>"), 2)

    def test_the_bridge_survives_a_document_with_no_body(self):
        """The bridge is injected in `<head>`; appending to a body that does
        not exist yet would throw inside the money path."""
        js = game_proxy.bridge_script()
        self.assertNotIn(b"document.body.appendChild", js)
        self.assertIn(b"document.body || document.documentElement", js)

    def test_a_money_answer_is_never_cached_and_a_bundle_revalidates(self):
        from demo import game_proxy
        up = {"Cache-Control": "public, max-age=31536000, immutable",
              "ETag": '"v1"'}
        self.assertEqual(game_proxy.cache_policy(up, money=True), "no-store")
        self.assertEqual(game_proxy.cache_policy(up, document=True), "no-cache")
        self.assertEqual(game_proxy.cache_policy(up, rewritten=True), "no-cache")
        self.assertEqual(
            game_proxy.cache_policy(up),
            "public, max-age=31536000, immutable")
        self.assertEqual(game_proxy.cache_policy({}), "public, max-age=600")
        # a publisher edge error is not a cacheable answer: observed live as a
        # 450 with a week-long policy from the CDN on a missing asset
        self.assertEqual(
            game_proxy.cache_policy({"Cache-Control": "max-age=604800, public"},
                                    status=450), "no-store")
        self.assertEqual(
            game_proxy.cache_policy({"Cache-Control": "max-age=604800, public"},
                                    status=404), "no-store")
        self.assertEqual(
            game_proxy.validator_headers(up), {"ETag": '"v1"'})
        self.assertEqual(
            game_proxy.validator_headers({"etag": '"v2"', "Expires": "x"}),
            {"ETag": '"v2"', "Expires": "x"})

    def test_only_a_body_we_may_rewrite_is_held_back_from_the_cache(self):
        from demo import game_proxy
        self.assertTrue(game_proxy.rewritable(""))
        self.assertTrue(game_proxy.rewritable("build.js"))
        self.assertTrue(game_proxy.rewritable("_abs/h/config.json"))
        self.assertFalse(game_proxy.rewritable("data.unityweb"))
        self.assertFalse(game_proxy.rewritable("audio/track.ogg"))
        # and by answer shape, which is what decides a publisher 304
        for ctype in ("text/html", "application/javascript", "application/json",
                      "text/plain", "application/xml"):
            self.assertTrue(game_proxy.rewriteable_type(ctype), ctype)
        for ctype in ("application/octet-stream", "image/png",
                      "application/vnd.unityweb", "video/mp4"):
            self.assertFalse(game_proxy.rewriteable_type(ctype), ctype)

    def test_proxy_counters_report_what_the_proxy_did(self):
        from demo import game_proxy
        before = game_proxy.stats()
        self._fetch(_Upstream(b"0123456789"))
        after = game_proxy.stats()
        self.assertEqual(after["upstream"], before["upstream"] + 1)
        self.assertEqual(after["bytes"], before["bytes"] + 10)
        with self.assertRaises(game_proxy.ProxyError):
            self._fetch(urllib.error.URLError("no route"))
        self.assertEqual(game_proxy.stats()["failures"],
                         before["failures"] + 1)


class ProxyHttpTest(unittest.TestCase):
    """The publisher-game proxy over HTTP, with the publisher stubbed out."""

    GAME = GameProxyTest.GAME
    HOST = GameProxyTest.HOST

    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.game_path = f"/g/{quote(self.GAME)}/_abs/{self.HOST}"
        self.force_304_once = False
        self.served_304 = False
        self.answer = (200, {"Content-Type": "application/octet-stream",
                             "ETag": '"v1"',
                             "Cache-Control": "public, max-age=600"}, b"BUNDLE")
        self.calls: list[dict] = []
        self.keep_fetch = game_proxy.fetch
        self.keep_view = DEMO.wallet_view_for

        def stub(url, method="GET", body=None, headers=None, timeout=20,
                 follow=True):
            self.calls.append({"url": url, "method": method,
                               "headers": dict(headers or {})})
            status, up_headers, data = self.answer
            head = dict(up_headers)
            validator = (headers or {}).get("If-None-Match")
            if ((self.force_304_once and not self.served_304)
                    or (head.get("ETag") and validator == head["ETag"])):
                self.served_304 = True
                return 304, head, b""
            return status, head, data

        game_proxy.fetch = stub
        self.addCleanup(self._restore)

    def _restore(self):
        game_proxy.fetch = self.keep_fetch
        DEMO.wallet_view_for = self.keep_view
        self.server.shutdown()
        self.server.server_close()

    def _call(self, path, headers=None, method="GET"):
        req = urllib.request.Request(self.base + path, headers=headers or {},
                                     method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, dict(exc.headers), exc.read()

    def test_the_wallet_token_never_reaches_the_publisher(self):
        """The token rides the redirect so the document stays bound to the
        player; the publisher has no use for a player's credential."""
        status, _headers, _body = self._call(
            f"{self.game_path}/build.js?wallet_token=SECRET&lang=pt")
        self.assertEqual(status, 200)
        self.assertNotIn("SECRET", self.calls[0]["url"])
        self.assertIn("lang=pt", self.calls[0]["url"])
        # the launch token on a page-proxied publisher is ours, not theirs
        self._call(f"{self.game_path}/build.js?token=SECRET")
        self.assertNotIn("SECRET", self.calls[1]["url"])

    def test_an_untouched_asset_revalidates_instead_of_re_downloading(self):
        """The old `no-cache` on every answer meant a reload re-downloaded
        the whole game through us; a body we serve unchanged now keeps the
        publisher's validator and answers 304."""
        status, headers, body = self._call(f"{self.game_path}/data.unityweb")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"BUNDLE")
        self.assertEqual(headers["ETag"], '"v1"')
        self.assertEqual(headers["Cache-Control"], "public, max-age=600")
        self.assertEqual(self.calls[0]["headers"].get("If-None-Match"), None)
        status, headers, body = self._call(f"{self.game_path}/data.unityweb",
                                           {"If-None-Match": '"v1"'})
        self.assertEqual(status, 304)
        self.assertEqual(body, b"")
        self.assertEqual(headers["ETag"], '"v1"')
        self.assertEqual(self.calls[1]["headers"].get("If-None-Match"), '"v1"')

    def test_a_script_body_is_never_revalidated_against_the_publisher(self):
        """A bundle may be rewritten on the way out, and a rewritten body
        cannot be pinned to the publisher's validator: neither send the
        client's nor advertise one we would not honour."""
        self.answer = (200, {"Content-Type": "application/javascript",
                             "ETag": '"v1"',
                             "Cache-Control": "public, max-age=600"},
                       b"var x=1;")
        status, headers, body = self._call(f"{self.game_path}/build.js",
                                            {"If-None-Match": '"v1"'})
        self.assertEqual(status, 200)
        self.assertEqual(body, b"var x=1;")
        self.assertNotIn("If-None-Match", self.calls[0]["headers"])
        self.assertNotIn("ETag", headers)
        self.assertEqual(headers["Cache-Control"], "public, max-age=600")

    def test_a_publisher_304_on_a_patchable_body_serves_the_real_body(self):
        """An empty answer cannot be patched, and a 304 we forwarded would
        pin the client to bytes we never computed: ask again, unconditionally."""
        self.answer = (200, {"Content-Type": "application/javascript",
                             "ETag": '"v1"'}, b"var x=1;")
        self.force_304_once = True
        status, headers, body = self._call(f"{self.game_path}/build.js",
                                           {"If-None-Match": '"v1"'})
        self.assertEqual(status, 200)
        self.assertEqual(body, b"var x=1;")
        self.assertNotIn("ETag", headers)
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn("If-None-Match", self.calls[1]["headers"])
        # the same holds for a document whose path looked like an asset: the
        # answer shape, not the file name, is what says it is patchable
        self.answer = (200, {"Content-Type": "text/html", "ETag": '"v1"'},
                       b"<html><head></head></html>")
        self.served_304 = False
        self.force_304_once = True
        status, _headers, body = self._call(f"{self.game_path}/index.html",
                                            {"If-None-Match": '"v1"'})
        self.assertEqual(status, 200)
        self.assertIn(b"<html>", body)
        self.assertEqual(len(self.calls), 4)

    def test_a_balance_is_never_cached(self):
        DEMO.wallet_view_for = lambda token: {"token": token,
                                              "balance_minor": 2000,
                                              "bonus_minor": 0}
        self.answer = (200, {"Content-Type": "text/plain", "ETag": '"v1"'},
                       b"action=doInit&balance=999,999.00")
        status, headers, body = self._call(
            f"{self.game_path}/gs2c/reloadBalance.do")
        self.assertEqual(status, 200)
        self.assertIn(b"balance=20.00", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("ETag", headers)

    def test_head_answers_the_headers_of_the_get_it_stands_for(self):
        """The base class answered 501, which is a lie about an asset that is
        sitting right there behind the proxy."""
        status, headers, body = self._call(f"{self.game_path}/data.unityweb",
                                           method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(headers["ETag"], '"v1"')
        self.assertNotIn("Content-Length", headers)

    def test_a_root_level_request_without_a_session_is_not_proxied(self):
        """The storefront owns every root path: only a live game session
        earns a forward, or anyone could use us to fetch a publisher."""
        status, _headers, _body = self._call("/apps/pp/game.js")
        self.assertEqual(status, 404)
        self.assertEqual(self.calls, [])

    def test_a_declared_charset_is_not_declared_twice(self):
        """`text/javascript; charset=utf-8; charset=utf-8` is what a publisher
        that declares its own charset used to get back from us."""
        self.answer = (200, {"Content-Type": "text/html; charset=UTF-8"},
                       b"<html></html>")
        status, headers, _body = self._call(f"{self.game_path}/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=UTF-8")


class PgSoftTest(unittest.TestCase):
    """PG Soft: a minted session, and the hosts it binds.

    Every answer here is a canned mint. The live path is exercised by
    `demo/_pgsmoke.py`, which does mint for real; a suite that reached out to
    PG would be a suite that fails on PG's schedule rather than on ours.
    """

    # a real mint's shape: the stable triple plus the two per-session
    # alternates it ships alongside. Padded past the length the decoder
    # insists on, so this exercises the real path rather than the fallback.
    def _launcher(self, gi="126", stable=True):
        triples = [
            ("pg-demo", "api.f26xzzc7c.com", "api.8jkxzybcq.com"),
            ("rhzzzvqpd", "api.9zzzzz9q9.com", "api.7aaaaa7a.com"),
        ]
        if not stable:
            triples = triples[1:]
        parts = []
        for label, api1, api2 in triples:
            parts.append(f"https://m.{label}.com/GI/index.html?ot=ot123&l=pt&btt=2")
            parts.append(f"static.{label}.com")
            parts.append(f"https://static.{label}.com/x.gif?rand=abc")
            parts.append(api1)
            parts.append(api2)
        payload = "".join(parts) + "padding-to-clear-the-decoder-threshold-" * 8
        b64 = base64.b64encode(payload.replace("GI", gi).encode()).decode()
        return "<html><script type=module>(function(){/*%s*/})()</script>" % b64

    def setUp(self):
        pg_proxy._SESSIONS.clear()

    def test_the_stable_triple_is_preferred_over_the_rolling_ones(self):
        url, game_host, static_host, apis = pg_proxy.parse_session(
            self._launcher(), "126")
        self.assertEqual(game_host, "m.pg-demo.com")
        self.assertEqual(static_host, "static.pg-demo.com")
        # Every money host the answer named is bound, not only the chosen
        # triple's: the client health-checks both of them before it commits
        # to one, so binding a single host would break its own failover.
        # They are all hosts this publisher just named in this answer.
        self.assertEqual(apis[:2], ("api.f26xzzc7c.com", "api.8jkxzybcq.com"))
        self.assertIn("ot=ot123", url)

    def test_the_rolling_triple_is_used_when_the_stable_one_is_absent(self):
        url, game_host, static_host, apis = pg_proxy.parse_session(
            self._launcher(stable=False), "126")
        self.assertEqual(game_host, "m.rhzzzvqpd.com")
        self.assertEqual(static_host, "static.rhzzzvqpd.com")
        self.assertEqual(apis, ("api.9zzzzz9q9.com", "api.7aaaaa7a.com"))
        self.assertIn("/126/index.html", url)

    def test_a_mint_for_another_game_is_refused(self):
        with self.assertRaises(pg_proxy.PgError):
            pg_proxy.parse_session(self._launcher("65"), "126")

    def test_a_launcher_with_no_session_is_refused(self):
        with self.assertRaises(pg_proxy.PgError):
            pg_proxy.parse_session("<html><body>nothing here</body></html>", "126")

    def test_a_host_that_is_not_prefix_label_com_is_never_bound(self):
        """Binding a host is permission to fetch it server-side, so the shape
        is checked where the name comes out of a publisher's answer."""
        for bad in ("m.evil.example.com", "m.127.0.0.1", "m.a.b.c",
                    "m.attacker.com.evil.net", "m..com"):
            with self.assertRaises(pg_proxy.PgError, msg=bad):
                pg_proxy.Session("s", "126", "ot", "https://m.x.com/1",
                                 bad, "static.x.com", ())

    def test_a_bound_host_is_allowed_and_an_unbound_one_is_not(self):
        session = pg_proxy.Session("s1", "126", "ot",
                                   "https://m.pg-demo.com/126/index.html",
                                   "m.pg-demo.com", "static.pg-demo.com",
                                   ("api.f26xzzc7c.com",))
        pg_proxy.bind(session)
        self.assertTrue(pg_proxy.allowed_host("m.pg-demo.com"))
        self.assertTrue(pg_proxy.allowed_host("api.f26xzzc7c.com"))
        # the rolling alternate this process never minted stays closed
        self.assertFalse(pg_proxy.allowed_host("m.rhzzzvqpd.com"))
        self.assertFalse(pg_proxy.allowed_host("evil.com"))

    def test_a_binding_expires(self):
        session = pg_proxy.Session("s2", "126", "ot", "https://m.pg-demo.com/x",
                                   "m.pg-demo.com", "static.pg-demo.com", ())
        pg_proxy.bind(session)
        self.assertTrue(pg_proxy.allowed_host("m.pg-demo.com"))
        session.expires_at = time.time() - 1
        self.assertIsNone(pg_proxy.session_for("s2"))
        self.assertFalse(pg_proxy.allowed_host("m.pg-demo.com"))

    def test_a_sub_path_naming_a_session_we_never_minted_is_refused(self):
        game = {"game_id": "pg:fortune-tiger", "demo_url":
                "https://public.pg-demo.com/demo/?gi=126&lang=pt"}
        with self.assertRaises(game_proxy.ProxyError):
            game_proxy.target_url(game, "pg/never-minted/", "")

    def test_the_minted_document_is_sent_verbatim_and_assets_keep_their_signature(self):
        session = pg_proxy.Session("s3", "126", "ot",
                                   "https://m.pg-demo.com/126/index.html?ot=ot123&l=pt&btt=2",
                                   "m.pg-demo.com", "static.pg-demo.com", ())
        pg_proxy.bind(session)
        game = {"game_id": "pg:fortune-tiger", "demo_url":
                "https://public.pg-demo.com/demo/?gi=126&lang=pt"}
        document = game_proxy.target_url(game, "pg/s3/", "token=player-secret")
        # the document is the publisher's, minted by the publisher: our own
        # parameters are not merged into it, and a player's wallet token can
        # never reach PG this way
        self.assertEqual(document, session.game_url)
        self.assertNotIn("player-secret", document)
        asset = game_proxy.target_url(game, "pg/s3/loader/06.js",
                                      "verify=123-abc%3D")
        # every asset URL is signed; dropping the signature would 403
        self.assertTrue(asset.endswith("/loader/06.js?verify=123-abc%3D"))

    def test_the_document_is_recognised_as_a_document_and_names_its_own_host(self):
        session = pg_proxy.Session("s4", "126", "ot",
                                   "https://m.pg-demo.com/126/index.html?ot=ot",
                                   "m.pg-demo.com", "static.pg-demo.com", ())
        pg_proxy.bind(session)
        # the catalog host is the *launcher*; the game came from the session's
        # own host, and the cookie that binds the session has to say so
        self.assertTrue(game_proxy.pg_document("pg/s4/"))
        self.assertTrue(game_proxy.pg_document("pg/s4"))
        self.assertFalse(game_proxy.pg_document("pg/s4/loader/06.js"))
        self.assertFalse(game_proxy.pg_document(""))
        self.assertEqual(game_proxy.pg_doc_host("pg/s4/"), "m.pg-demo.com")

    def test_a_trailing_slash_sub_path_is_treated_as_a_document(self):
        """Not PG-specific in intent: a sub-path that ends in `/` names a
        document, so it is the one that earns the `<base>` repair and the
        bridge. PG just happens to be the one that always looks like this."""
        self.assertTrue(game_proxy.rewritable("pg/abc/"))
        self.assertTrue(game_proxy.rewritable("anything/"))
        # an image is not something we rewrite, so it revalidates normally
        self.assertFalse(game_proxy.rewritable("logo.png"))

    def test_the_launch_mints_and_hides_the_wallet_token_from_pg(self):
        demo = Demo(data_dir=tempfile.mkdtemp())
        game = game_proxy.game_for("pg:fortune-tiger")
        self.assertIsNotNone(game)
        minted = pg_proxy.Session("minted-1", "126", "ot",
                                  "https://m.pg-demo.com/126/index.html?ot=ot",
                                  "m.pg-demo.com", "static.pg-demo.com", (),
                                  hv="triple-hv", us="triple-us")
        pg_proxy.bind(minted)

        def _mint(gi, lang="pt", session_id=""):
            return minted

        original, pg_proxy.mint = pg_proxy.mint, _mint
        try:
            url = demo.interposed_launch("pg:fortune-tiger", "tok-abc",
                                         "https://ours.example")
        finally:
            pg_proxy.mint = original
        # our own path carries the session, so the per-session hosts resolve;
        # the minted query rides for the client (it boots off location.search)
        # and the token rides for us, both stripped before anything leaves
        from urllib.parse import parse_qs, urlsplit
        parts = urlsplit(url)
        # gi-rooted, so the client builds publisher-identical asset URLs
        self.assertEqual(
            parts.scheme + "://" + parts.netloc + parts.path,
            "https://ours.example/126/")
        query = parse_qs(parts.query)
        self.assertEqual(query["ot"], ["ot"])
        self.assertEqual(query["__hv"], ["triple-hv"])
        self.assertEqual(query["__sv"], ["triple-us"])
        self.assertEqual(query["token"], ["tok-abc"])
        self.assertEqual(query["pg"], ["minted-1"])
        # `or` is the mangled static host (random shift per launch, so
        # only the round-trip is asserted, not the value)
        self.assertEqual(pg_proxy.unmangle(query["or"][0]),
                         "static.pg-demo.com")
        game_query = game_proxy.target_url(game, "pg/minted-1/", "token=tok-abc")
        self.assertNotIn("tok-abc", game_query)

    def test_the_domain_mangling_matches_a_real_launcher_redirect(self):
        """`ao`/`or` are computed, not minted: the mint page ships the
        algorithm (a letter shift + the shift as two digits), and this is
        the exact value a live launcher produced for the same input."""
        self.assertEqual(pg_proxy.mangle("api.f26xzzc7c.com", 18),
                         "18sha=x26prru7u=uge")
        for domain in ("api.f26xzzc7c.com", "static.eajzzxhro.com",
                       "m.pg-demo.com"):
            for shift in (1, 7, 18, 24, 25):
                self.assertEqual(
                    pg_proxy.unmangle(pg_proxy.mangle(domain, shift)),
                    domain)
        # digits and hyphens pass through, dots become '='
        self.assertEqual(pg_proxy.mangle("f26.iii", 18), "18x26=aaa")

    def test_the_mint_blob_decodes_to_triples_with_handshake_fields(self):
        """parse_triples reads the whole msgpack answer, not just the URL
        runs: every triple's game URL plus the `hv`/`us` fields the
        launcher forwards as `__hv`/`__sv`."""
        import struct as _struct

        def enc(value):
            if isinstance(value, str):
                raw = value.encode()
                if len(raw) <= 31:
                    return bytes([0xa0 + len(raw)]) + raw
                return b"\xd9" + bytes([len(raw)]) + raw
            if isinstance(value, int):
                return bytes([0xcc, value]) if value < 256 else \
                    b"\xcd" + _struct.pack(">H", value)
            if isinstance(value, float):
                return b"\xcb" + _struct.pack(">d", value)
            if isinstance(value, list):
                return bytes([0x90 + len(value)]) + b"".join(enc(v)
                                                             for v in value)
            if isinstance(value, dict):
                out = bytes([0x80 + len(value)])
                for k, v in value.items():
                    out += enc(k) + enc(v)
                return out
            raise AssertionError(f"no encoder for {value!r}")

        import base64 as _b64
        payload = {"m": {"tid": "t", "pad1": "x" * 200,
                        "pad2": "y" * 200}, "f": [
            {"u": "https://m.abc1234.com/126/index.html?ot=ot9&l=pt&btt=2",
             "w": 70.0,
             "rd": [{"v": "static.abc1234.com", "w": 100.0,
                     "hv": "triple-hv", "us": "triple-us",
                     "ust": "https://static.abc1234.com/p.gif"}],
             "ad": [{"v": "api.aaa1111.com", "w": 80.0}]}]}
        html = "<html>" + _b64.b64encode(enc(payload)).decode() + "</html>"
        triples = pg_proxy.parse_triples(html)
        self.assertEqual(set(triples), {"abc1234"})
        self.assertEqual(triples["abc1234"]["hv"], "triple-hv")
        self.assertEqual(triples["abc1234"]["us"], "triple-us")
        self.assertIn("ot=ot9", triples["abc1234"]["game_url"])
        # garbage is not a mint: no triples, no exception
        self.assertEqual(pg_proxy.parse_triples("<html>no blob</html>"), {})
        self.assertEqual(pg_proxy.parse_triples(
            "<html>" + _b64.b64encode(b"\xc0").decode() + "</html>"), {})


    def test_the_catalog_resolves_a_game_by_its_gi(self):
        game = game_proxy.game_for_gi("126")
        self.assertIsNotNone(game)
        self.assertEqual(game["game_id"], "pg:fortune-tiger")
        self.assertIsNone(game_proxy.game_for_gi("000"))

    def test_the_bridge_carries_the_pg_tap_config(self):
        """The theater tap's two facts ride the bridge config: which spin
        endpoint the R$0 gate guards, and which game id the wallet poll
        names. Other providers get neither."""
        import json as _json
        import re as _re
        view = {"balance_minor": 10000, "bonus_minor": 0,
                "min_stake_minor": 200, "can_play": True}
        pg = game_proxy.inject_bridge(b"<head></head>", "pg:fortune-tiger",
                                      "tok", view).decode()
        cfg = _json.loads(_re.search(
            r"window\.__WALLET__=(.*?);</script>", pg).group(1))
        self.assertEqual(cfg["bet_url"], "/v4/Spin")
        self.assertEqual(cfg["pg_gi"], "126")
        pp = game_proxy.inject_bridge(
            b"<head></head>", "pp:gates-of-olympus", "tok",
            view).decode()
        self.assertNotIn("pg_gi", pp)
        self.assertNotIn("bet_url", pp)

    def test_the_money_endpoints_are_named_where_they_were_measured(self):
        """The paths are written down because they were measured, not guessed.

        Every one of these was read off a real capture; a tap that builds a
        URL from them is building it from evidence. If PG moves them, this
        is the list that has to change.
        """
        self.assertEqual(pg_proxy.SESSION_PATH,
                         "/web-api/auth/session/v2/verifySession")
        self.assertEqual(pg_proxy.WALLET_PATH,
                         "/web-api/game-proxy/v2/GameWallet/Get")
        self.assertEqual(pg_proxy.NAME_PATH,
                         "/web-api/game-proxy/v2/GameName/Get")
        # `cb` is what the game shows, and it comes first for a reason
        self.assertEqual(pg_proxy.WALLET_BALANCE_KEYS[0], "cb")
        self.assertIn("tb", pg_proxy.WALLET_BALANCE_KEYS)

    def test_a_slug_becomes_the_title_the_lobby_shows(self):
        """`GameName/Get`'s "31" is a localization key — it answers "Baccarat
        Deluxe" for every title — so the name comes from the slug, which is
        the one per-game identifier the handshake hands over."""
        from scripts.discover_pgsoft_demos import title_from_slug
        self.assertEqual(title_from_slug("dragon-tiger-luck"), "Dragon Tiger Luck")
        self.assertEqual(title_from_slug("fortune-tiger"), "Fortune Tiger")
        self.assertEqual(title_from_slug("mahjong-ways"), "Mahjong Ways")
        # acronyms stay uppercase, and an empty slug is not a title
        self.assertEqual(title_from_slug("lgd-monkey-kg"), "Lgd Monkey Kg")
        self.assertEqual(title_from_slug("win-win-fpc"), "Win Win Fpc")
        self.assertEqual(title_from_slug(""), "")

    def test_the_wallet_answer_carries_our_saldo(self):
        """Display sync: GameWallet/Get's cb/tb show the player's saldo in
        the publisher's own shape; pb follows so no phantom delta appears,
        and the unknown bonus keys are left alone."""
        import json
        body = json.dumps({
            "dt": {"tb": 100000.00, "cb": 100000.00, "pb": 0.00,
                   "tbb": 5.00, "tfgb": 7,
                   "ch": {"cb": 100000.00, "k": "0_C"}}}).encode()
        out = json.loads(pg_proxy.rewrite_wallet(body, 10500).decode())
        self.assertEqual(out["dt"]["cb"], 105.0)
        self.assertEqual(out["dt"]["tb"], 105.0)
        self.assertEqual(out["dt"]["pb"], 105.0)
        self.assertEqual(out["dt"]["ch"]["cb"], 105.0)
        self.assertEqual(out["dt"]["tbb"], 5.00)
        self.assertEqual(out["dt"]["tfgb"], 7)
        # ints stay ints
        body = json.dumps({"dt": {"tb": 3, "cb": 3, "pb": 0}}).encode()
        out = json.loads(pg_proxy.rewrite_wallet(body, 10500).decode())
        self.assertEqual(out["dt"]["cb"], 105)
        self.assertIsInstance(out["dt"]["cb"], int)

    def test_the_wallet_rewrite_passes_through_what_it_does_not_know(self):
        binary = bytes([0x08, 0x96, 0x01, 0x1a, 0x04, 0x74, 0x65, 0x73, 0x74])
        self.assertEqual(pg_proxy.rewrite_wallet(binary, 10500), binary)
        for raw in (b"{}", b'{"dt": null}',
                    b'{"dt": {"tbb": 5.00}}', b"[1, 2]", b"not json"):
            self.assertEqual(pg_proxy.rewrite_wallet(raw, 10500), raw)

    def test_money_tails_ride_the_api_host_and_assets_the_game_host(self):
        session = pg_proxy.Session(
            "s5", "126", "ot",
            "https://m.pg-demo.com/126/index.html?ot=ot123&l=pt&btt=2",
            "m.pg-demo.com", "static.pg-demo.com",
            ("api.f26xzzc7c.com", "api.8jkxzybcq.com"))
        pg_proxy.bind(session)
        game = {"game_id": "pg:fortune-tiger", "demo_url":
                "https://public.pg-demo.com/demo/?gi=126&lang=pt"}
        money = game_proxy.target_url(
            game, "pg/s5/web-api/game-proxy/v2/GameWallet/Get", "")
        self.assertTrue(money.startswith("https://api.f26xzzc7c.com/"),
                        money)
        spin = game_proxy.target_url(game, "pg/s5/game-api/fortune-tiger/", "")
        self.assertTrue(spin.startswith("https://api.f26xzzc7c.com/"), spin)
        asset = game_proxy.target_url(game, "pg/s5/loader/06.js",
                                      "verify=123-abc%3D")
        self.assertTrue(asset.startswith("https://m.pg-demo.com/"), asset)
        # the money classification the serve path reads
        money_paths = game_proxy.MONEY_PATHS["pg_soft"]
        import re
        sub = "pg/s5/web-api/game-proxy/v2/GameWallet/Get"
        self.assertTrue(any(re.search(p, sub) for p in money_paths))
        self.assertFalse(any(re.search(p, "pg/s5/loader/06.js")
                             for p in money_paths))


class KenoTest(unittest.TestCase):
    """Keno: 20 of 80, the hit count pays, and the ladder is derived.

    The reason this game exists at all is in decision 0034: Keno was set
    aside because it "needs a full paytable to get exactly right". These
    checks are the answer to that — the ladder is computed from the exact
    hit distribution and scaled to the house keep, so it cannot be subtly
    wrong, and the RTP is asserted rather than asserted-in-a-comment.
    """

    PICK5 = "5:3,17,42,58,71"
    PICK10 = "10:3,17,42,58,71,4,19,9,12,77"

    # --- the paytable is derived, not typed ------------------------------

    def test_the_ladder_rtp_is_97_percent_at_every_spot_count(self):
        for spots in range(KENO_MIN_SPOTS, KENO_MAX_SPOTS + 1):
            self.assertAlmostEqual(
                keno_rtp(spots), 0.97, places=4,
                msg=f"{spots} spots pays {keno_rtp(spots):.6f}")

    def test_the_catalog_rtp_is_the_model(self):
        self.assertAlmostEqual(arcade_theoretical_rtp(KENO_GAME_ID),
                               0.97, places=4)

    def test_every_extra_hit_doubles_the_payout(self):
        """The shape is the design: a clean ladder, 2x per extra hit."""
        for spots in range(2, KENO_MAX_SPOTS + 1):
            table = keno_paytable(spots)
            for hits in range(1, spots):
                self.assertAlmostEqual(
                    float(table[hits + 1]) / float(table[hits]), 2.0,
                    places=2,
                    msg=f"{spots} spots, tier {hits}")

    def test_zero_hits_never_pays(self):
        """It is the common case, and a tier that paid would have to be
        worthless per hit while still reading as a win."""
        for spots in range(KENO_MIN_SPOTS, KENO_MAX_SPOTS + 1):
            self.assertEqual(keno_multiplier(spots, 0), Fraction(0))

    def test_hit_probabilities_are_exact_and_add_up_to_one(self):
        for spots in range(1, KENO_MAX_SPOTS + 1):
            total = sum(keno_hit_probability(spots, k) for k in range(spots + 1))
            self.assertEqual(total, 1, msg=f"{spots} spots")
            # the expectation is the textbook one: s * D / N
            expected = Fraction(spots * KENO_DRAWN, KENO_POOL)
            got = sum(Fraction(k) * keno_hit_probability(spots, k)
                      for k in range(spots + 1))
            self.assertEqual(got, expected, msg=f"{spots} spots")

    def test_one_spot_pays_the_odds_of_one_number(self):
        """20 of 80 drawn: a single pick lands a quarter of the time."""
        self.assertEqual(keno_hit_probability(1, 1), Fraction(20, 80))
        self.assertAlmostEqual(float(keno_multiplier(1, 1)), 3.88, places=2)

    def test_the_realised_rtp_is_reported_and_close_to_the_model(self):
        """The model is 97%; what a player collects is rounded to the centavo
        per round, so it sits just under it. Reported, not hidden."""
        for spots in (1, 5, 10):
            for stake in (100, 1000):
                realised = keno_realised_rtp(spots, stake)
                # round-half-up is unbiased, so this lands on EITHER side of
                # the model; what must hold is that it is close to it
                self.assertAlmostEqual(realised, 0.97, delta=0.003,
                                       msg=f"{spots} spots at {stake}")

    # --- the selection ---------------------------------------------------

    def test_the_selection_parses(self):
        self.assertEqual(parse_keno_selection(self.PICK5), (5, (3, 17, 42, 58, 71)))
        # the order the player clicked does not change the round
        self.assertEqual(parse_keno_selection("5:71,42,17,58,3"), (5, (3, 17, 42, 58, 71)))

    def test_a_bad_selection_is_refused(self):
        for bad in ("", "garbage", "5:1,2", "5:1,2,3,4,81", "5:1,2,3,4,4",
                    "0:1", "11:1,2,3,4,5,6,7,8,9,10,11", "5"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                parse_keno_selection(bad)

    # --- the draw --------------------------------------------------------

    def test_the_draw_is_deterministic_and_well_formed(self):
        for round_id in ("a", "b", "c"):
            drawn = keno_draw(KENO_GAME_ID, round_id)
            self.assertEqual(len(drawn), KENO_DRAWN)
            self.assertEqual(len(set(drawn)), KENO_DRAWN)
            self.assertTrue(all(1 <= n <= KENO_POOL for n in drawn))
            self.assertEqual(list(drawn), sorted(drawn))
        self.assertEqual(keno_draw(KENO_GAME_ID, "a"),
                         keno_draw(KENO_GAME_ID, "a"))
        self.assertNotEqual(keno_draw(KENO_GAME_ID, "a"),
                            keno_draw(KENO_GAME_ID, "b"))

    def test_the_round_is_repeatable_from_the_ledger_alone(self):
        one = keno_round(KENO_GAME_ID, "fixed", self.PICK5, 1000)
        two = keno_round(KENO_GAME_ID, "fixed", self.PICK5, 1000)
        self.assertEqual(one, two)

    # --- settlement ------------------------------------------------------

    def test_every_hit_count_pays_exactly_the_ladder(self):
        """Forced through every tier: the payout is the ladder, not a
        round-number near it."""
        base = "5:3,17,42,58,71"
        paid = {}
        for i in range(400):
            result = keno_round(KENO_GAME_ID, f"tier{i}", base, 1000)
            hits = int(result.symbols[2].split("/")[0])
            paid.setdefault(hits, result)
        table = keno_paytable(5)
        for hits, result in paid.items():
            expected = keno_payout(1000, table.get(hits, Fraction(0)))
            self.assertEqual(result.payout_minor, expected,
                             msg=f"{hits} hits should pay {expected}")

    def test_a_sub_stake_tier_is_a_partial_return_not_a_win(self):
        """1 hit on 10 spots pays 0.22x. Reporting that as a win would be a
        lie the panel then displays."""
        result = keno_round(KENO_GAME_ID, "partial", self.PICK10, 1000)
        found = False
        for i in range(600):
            r = keno_round(KENO_GAME_ID, f"p{i}", self.PICK10, 1000)
            if r.multiplier not in ("0",) and float(r.multiplier) < 1:
                self.assertFalse(r.is_win, msg=f"{r.tier} pays {r.multiplier}x")
                self.assertGreater(r.payout_minor, 0)
                found = True
        self.assertTrue(found, "no sub-stake tier appeared; the case is untested")

    def test_a_round_settles_through_the_books(self):
        demo = Demo(data_dir=tempfile.mkdtemp())
        player = demo.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })["player_id"]
        demo.deposit({"player": player, "amount_minor": 100000, "method": "pix"})
        before = demo.profile(player)["available_minor"]
        demo.spin({"player": player, "game_id": KENO_GAME_ID,
                   "stake_minor": 1000, "selection": self.PICK10,
                   "round_id": "settle-1"})
        after = demo.profile(player)["available_minor"]
        # 1000 staked, and whatever the ladder paid came back
        self.assertLessEqual(after, before - 1000 + 1000 * 115)
        self.assertGreaterEqual(after, before - 1000)
        demo.books.assert_balanced()

    def test_a_missing_selection_is_refused_and_moves_no_money(self):
        demo = Demo(data_dir=tempfile.mkdtemp())
        player = demo.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })["player_id"]
        demo.deposit({"player": player, "amount_minor": 100000, "method": "pix"})
        before = demo.profile(player)["available_minor"]
        with self.assertRaises(Exception):
            demo.spin({"player": player, "game_id": KENO_GAME_ID,
                       "stake_minor": 1000, "round_id": "no-sel"})
        self.assertEqual(demo.profile(player)["available_minor"], before)
        demo.books.assert_balanced()

    def test_a_round_lands_in_history(self):
        demo = Demo(data_dir=tempfile.mkdtemp())
        player = demo.upsert_player({
            "name": "Ana Souza", "cpf": "529.982.247-25",
            "pix_key": "ana.souza@example.com",
            "bank": {"bank_code": "001", "agency": "1234",
                     "account": "56789-0", "holder_name": "Ana Souza"},
        })["player_id"]
        demo.deposit({"player": player, "amount_minor": 100000, "method": "pix"})
        demo.spin({"player": player, "game_id": KENO_GAME_ID,
                   "stake_minor": 1000, "selection": self.PICK5,
                   "round_id": "hist-1"})
        rounds = demo.history(player)
        keno = [r for r in rounds if r["game_id"] == KENO_GAME_ID]
        self.assertEqual(len(keno), 1)
        self.assertEqual(keno[0]["unit"], keno_round(
            KENO_GAME_ID, "hist-1", self.PICK5, 1000).unit)

    # --- the catalog row -------------------------------------------------

    def test_it_is_certified_and_listed_under_originais(self):
        self.assertIn(KENO_GAME_ID, ARCADE_GAME_IDS)
        self.assertEqual(DEMO_CATEGORY.get(KENO_GAME_ID), "Originais")
        demo = Demo(data_dir=tempfile.mkdtemp())
        catalogue = demo.catalog()
        rows = catalogue["games"] if isinstance(catalogue, dict) else catalogue
        row = next(r for r in rows if r["game_id"] == KENO_GAME_ID)
        self.assertEqual(row["provider"], "demo_studio")
        self.assertEqual(row["rtp"], "97.00")
        # the cert gate must let it launch, like the other originals
        self.assertEqual(demo.registry.get(KENO_GAME_ID).status, "certified")
        # and the cert gate lets it through
        self.assertIn(KENO_GAME_ID, demo.registry.launchable_ids())



if __name__ == "__main__":
    unittest.main(verbosity=2)
