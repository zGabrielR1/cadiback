import os
import tempfile
import unittest
import urllib.error
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from frame.compliance.sigap import (
    BRAZIL,
    ExclusionRegistry,
    GameCertification,
    GameRegistry,
    Limits,
    SigapReporter,
    certification_deadline,
)
from frame.core import devig
from frame.core.ids import (
    AMBIGUOUS,
    EXACT,
    QUALIFIED,
    fixture_key,
    idempotency_key,
    match_teams,
    normalize,
)
from frame.core.ledger import IntegrityLedger
from frame.core.money import allocate, check_odds, gross_return, to_cents, to_real
from frame.models.registry import default_registry
from frame.ops.health import check_books, check_ledger, health
from frame.ops.notifier import LocalNotifier
from frame.ops.scheduler import Scheduler
from frame.validation import gates
from frame.verticals.casino.stub import CasinoStub
from frame.verticals.sports.stub import SportsStub
from frame.wallet.books import (
    BET_STAKED,
    BONUS_ISSUED,
    GGR_REVENUE,
    OPERATOR_CASH,
    PAYABLE_PLAYER,
    PLAYER_BALANCE,
    PLAYER_BONUS,
    BalanceError,
    Books,
    DuplicatePosting,
    WalletError,
)


class MoneyTest(unittest.TestCase):
    def test_int_only_core(self):
        self.assertEqual(to_cents(10), 1000)
        self.assertEqual(to_cents("19.99"), 1999)
        self.assertEqual(to_cents(Decimal("0.015")), 2)
        with self.assertRaises(Exception):
            to_cents(True)
        with self.assertRaises(Exception):
            to_cents("abc")

    def test_allocate_sums_exactly(self):
        self.assertEqual(sum(allocate(100, [1, 1, 1])), 100)
        self.assertEqual(sum(allocate(7, [2, 3])), 7)
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])
        with self.assertRaises(Exception):
            allocate(-5, [1])
        with self.assertRaises(Exception):
            allocate(5, [])

    def test_odds_bounds(self):
        check_odds("2.50")
        check_odds("1.01")
        with self.assertRaises(Exception):
            check_odds("1.00")
        with self.assertRaises(Exception):
            check_odds("1000.01")

    def test_payout(self):
        self.assertEqual(gross_return(100, "2.00"), 200)
        self.assertEqual(gross_return(199, "1.95"), 388)
        with self.assertRaises(Exception):
            gross_return(-1, "2.00")


class IdsTest(unittest.TestCase):
    def test_fixture_key_deterministic(self):
        key = fixture_key("football", "bra.1", "Fluminense", "Vasco", date(2026, 10, 3))
        self.assertEqual(key, fixture_key("football", "bra.1", "Fluminense", "Vasco", "2026-10-03"))
        self.assertEqual(key, fixture_key("football", "bra.1", "Vasco", "Fluminense", date(2026, 10, 3)))
        self.assertEqual(len(key), 32)

    def test_fixture_key_rejects(self):
        with self.assertRaises(Exception):
            fixture_key("football", "bra.1", "Vasco", "Vasco", date(2026, 10, 3))
        with self.assertRaises(Exception):
            fixture_key("football", "bra.1", "", "Vasco", date(2026, 10, 3))

    def test_refuses_to_guess(self):
        result = match_teams("Nacional", "Nacional", ["Nacional", "Atlético Nacional"])
        self.assertEqual(result.status, EXACT)
        vague = match_teams("Sport", "Sporting", ["Sport Club", "Sporting CP"])
        self.assertEqual(vague.status, AMBIGUOUS)
        self.assertIsNotNone(vague.closest)

    def test_nacional_hazard_stays_ambiguous(self):
        result = match_teams("Nacional", "Atlético Nacional", ["Nacional", "Atlético Nacional"])
        self.assertEqual(result.status, AMBIGUOUS)
        self.assertFalse(result.resolved)

    def test_qualified(self):
        result = match_teams("Flamengo FC", "Flamengo", ["Flamengo"])
        self.assertEqual(result.status, QUALIFIED)
        self.assertEqual(result.qualifier, "fc")
        rio = match_teams("Flamengo RJ", "Flamengo", ["Flamengo"])
        self.assertEqual(rio.status, AMBIGUOUS)

    def test_accent_fold(self):
        self.assertEqual(normalize("São Paulo"), "sao paulo")
        self.assertEqual(idempotency_key("a", "b"), idempotency_key("a", "b"))
        with self.assertRaises(Exception):
            idempotency_key("a", "")


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "ledger.jsonl")

    def test_write_once_fill_once(self):
        ledger = IntegrityLedger(self.path)
        self.assertTrue(ledger.observe("bet:1", "stake", 5000))
        self.assertFalse(ledger.observe("bet:1", "stake", 9000))
        self.assertEqual(ledger.get("bet:1")["stake"], 5000)
        self.assertTrue(ledger.fill("bet:1", "close", "2.10"))
        self.assertFalse(ledger.fill("bet:1", "close", "1.90"))
        report = ledger.verify()
        self.assertTrue(report.intact)
        self.assertEqual(report.records, 2)

    def test_tamper_detected(self):
        ledger = IntegrityLedger(self.path)
        ledger.observe("bet:1", "stake", 5000)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write('{"seq":99,"ts":"x","prev":"y","hash":"z","kind":"observe","subject":"bet:2","field":"stake","value":1}\n')
        report = IntegrityLedger(self.path).verify()
        self.assertFalse(report.intact)
        self.assertIsNotNone(report.broken_at)


class DevigTest(unittest.TestCase):
    PRICES = ("2.75", "3.10", "2.62")

    def test_fairs_sum_to_one(self):
        for method in devig.METHODS:
            fair = devig.fair(self.PRICES, method=method, kind=devig.ONE_X_TWO)
            self.assertAlmostEqual(float(sum(fair, Decimal(0))), 1.0, places=8)

    def test_zero_margin_book_returns_itself(self):
        book = ("2.00", "3.333333333333333", "5.00")
        raw = [float(Decimal(1) / Decimal(p)) for p in book]
        self.assertAlmostEqual(sum(raw), 1.0, places=6)
        for method in devig.METHODS:
            fair = devig.fair(book, method=method, kind=devig.ONE_X_TWO)
            for got, want in zip(fair, raw):
                self.assertAlmostEqual(float(got), want, places=6)

    def test_shin_monotone_and_bounded(self):
        raw = devig.implied(self.PRICES)
        grid = [Decimal(i) / Decimal(100) for i in range(0, 100, 5)]
        totals = [float(sum(devig._shin_curve(raw, z), Decimal(0))) for z in grid]
        for earlier, later in zip(totals, totals[1:]):
            self.assertGreaterEqual(earlier, later)
        self.assertGreater(totals[0], 1.0)
        self.assertLess(totals[-1], 1.0)
        for value in devig.devig_shin(self.PRICES):
            self.assertGreater(float(value), 0.0)
            self.assertLess(float(value), 1.0)

    def test_two_way_only_mult(self):
        fair = devig.fair(("1.90", "1.92"), method=devig.MULTIPLICATIVE, kind=devig.TWO_WAY)
        self.assertAlmostEqual(float(sum(fair, Decimal(0))), 1.0, places=10)

    def test_v1_bug_guard(self):
        with self.assertRaises(devig.MarketError):
            devig.margin_report(("1.90", "1.92"), kind=devig.ONE_X_TWO)
        with self.assertRaises(devig.MarketError):
            devig.margin_report(("1.80", "2.20"), kind="1x2-evil")

    def test_arb_rejected(self):
        with self.assertRaises(devig.MarketError):
            devig.check_market(("2.10", "2.10", "2.10"), devig.ONE_X_TWO)

    def test_margin_report(self):
        report = devig.margin_report(self.PRICES, kind=devig.ONE_X_TWO)
        self.assertGreater(float(report.overround), 0)
        payload = report.as_dict()
        self.assertEqual(payload["kind"], "1x2")


class WalletTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.books = Books(os.path.join(self.tmp, "books.jsonl"))

    def test_deposit_and_bet_loss(self):
        self.books.deposit("dep:1", "ana", 10000)
        self.books.place_bet("bet:1", "ana", 5000, "2.00")
        self.books.settle_bet_loss("stl:1", "ana", 5000)
        self.books.assert_balanced()
        self.assertEqual(self.books.available("ana"), 5000)
        self.assertEqual(self.books.ggr(), 5000)

    def test_bet_win(self):
        self.books.deposit("dep:1", "ana", 10000)
        self.books.place_bet("bet:1", "ana", 5000, "2.00")
        self.books.settle_bet_win("stl:1", "ana", 5000, "2.00")
        self.books.assert_balanced()
        self.assertEqual(self.books.available("ana"), 15000)
        self.assertEqual(self.books.ggr(), -5000)

    def test_push_returns_cash(self):
        self.books.deposit("dep:1", "ana", 10000)
        self.books.place_bet("bet:1", "ana", 5000, "2.00")
        self.books.settle_bet_push("stl:1", "ana", 5000)
        self.books.assert_balanced()
        self.assertEqual(self.books.available("ana"), 10000)

    def test_bonus_stake_push_returns_nothing_to_player(self):
        self.books.grant_bonus("bon:1", "ana", 2000)
        self.books.place_bet("bet:1", "ana", 2000, "2.00", bonus_part=2000)
        self.books.settle_bet_push("stl:1", "ana", 2000, bonus_part=2000)
        self.books.assert_balanced()
        self.assertEqual(self.books.available("ana"), 0)
        self.assertEqual(self.books.bonus_available("ana"), 0)

    def test_bonus_stake_win_pays_back_to_bonus_balance(self):
        """A win on a bonus-funded stake must not become withdrawable cash
        before the wagering requirement is met: the bonus portion of the
        payout returns to `player:bonus`."""
        self.books.deposit("dep:1", "ana", 10000)
        self.books.grant_bonus("bon:1", "ana", 2000)
        self.books.place_bet("bet:1", "ana", 500, "2.00", bonus_part=500)
        self.books.settle_bet_win("stl:1", "ana", 500, "2.00", bonus_part=500)
        self.books.assert_balanced()
        self.assertEqual(self.books.available("ana"), 10000)
        self.assertEqual(self.books.bonus_available("ana"), 2500)
        # mixed stake: 600 cash + 400 bonus of a 1000 stake at 2.00
        self.books.place_bet("bet:2", "ana", 1000, "2.00", bonus_part=400)
        self.books.settle_bet_win("stl:2", "ana", 1000, "2.00", bonus_part=400)
        self.books.assert_balanced()
        self.assertEqual(self.books.available("ana"), 10600)
        self.assertEqual(self.books.bonus_available("ana"), 2900)
        self.assertEqual(self.books.ggr(), -1500)
        with self.assertRaises(WalletError):
            self.books.settle_bet_win("stl:3", "ana", 100, "2.00", bonus_part=200)

    def test_insufficient_and_idempotent(self):
        self.books.deposit("dep:1", "ana", 1000)
        with self.assertRaises(WalletError):
            self.books.place_bet("bet:1", "ana", 5000, "2.00")
        with self.assertRaises(WalletError):
            self.books.withdraw("wd:1", "ana", 5000)
        with self.assertRaises(DuplicatePosting):
            self.books.deposit("dep:1", "ana", 1000)

    def test_withdrawal_two_step(self):
        self.books.deposit("dep:1", "ana", 10000)
        self.books.withdraw("wd:1", "ana", 4000)
        self.assertEqual(self.books.available("ana"), 6000)
        self.books.settle_withdrawal("wdp:1", "ana", 4000)
        self.books.assert_balanced()
        self.assertEqual(self.books.balance(PAYABLE_PLAYER), 0)

    def test_replay_survives(self):
        self.books.deposit("dep:1", "ana", 10000)
        self.books.place_bet("bet:1", "ana", 5000, "2.00")
        self.books.settle_bet_loss("stl:1", "ana", 5000)
        second = Books(self.books.path)
        second.assert_balanced()
        self.assertEqual(len(second.postings), 3)
        self.assertEqual(second.available("ana"), 5000)
        self.assertEqual(second.ggr(), 5000)
        with self.assertRaises(DuplicatePosting):
            second.deposit("dep:1", "ana", 10000)

    def test_casino_settlement_allows_any_payout(self):
        """A publisher slot round can pay less than the stake; the round must
        still balance for any payout, including a sub-stake win."""
        self.books.deposit("dep:1", "ana", 10000)
        self.books.place_bet("bet:1", "ana", 1000, "2.00")
        self.books.settle_casino("stl:1", "ana", 1000, 420)   # 0.42x win
        self.books.assert_balanced()
        self.assertEqual(self.books.available("ana"), 9420)
        self.assertEqual(self.books.ggr(), 580)
        self.books.place_bet("bet:2", "ana", 1000, "2.00")
        self.books.settle_casino("stl:2", "ana", 1000, 1750)  # above the stake
        self.books.place_bet("bet:3", "ana", 1000, "2.00")
        self.books.settle_casino("stl:3", "ana", 1000, 0)     # a loss
        self.books.assert_balanced()
        self.assertEqual(self.books.available("ana"), 9170)
        # the bonus-funded share of a payout returns to bonus, not cash
        self.books.grant_bonus("bon:1", "ana", 2000)
        self.books.place_bet("bet:4", "ana", 1000, "2.00", bonus_part=1000)
        self.books.settle_casino("stl:4", "ana", 1000, 500, bonus_part=1000)
        self.books.assert_balanced()
        self.assertEqual(self.books.available("ana"), 9170)
        self.assertEqual(self.books.bonus_available("ana"), 1500)
        with self.assertRaises(WalletError):
            self.books.settle_casino("stl:5", "ana", 1000, -1)

    def test_unbalanced_rejected(self):
        with self.assertRaises(BalanceError):
            self.books.post("bad:1", "bad", [(PLAYER_BALANCE, 100), (GGR_REVENUE, 0)])


class ComplianceTest(unittest.TestCase):
    def _cert(self, game_id="pp:gates-of-olympus", **over):
        base = dict(
            game_id=game_id,
            provider="pragmatic_play",
            title="Gates of Olympus",
            rng_reference="rng-1",
            certificate_id="BR-GLI-0001",
            lab="GLI",
            issued_for=BRAZIL,
            status="certified",
            sigap_submission="submitted",
            certified_on="2026-08-01",
            rtp="96.50",
        )
        base.update(over)
        return GameCertification(**base)

    def test_foreign_cert_blocks_launch(self):
        registry = GameRegistry()
        registry.register(self._cert(issued_for="MT"))
        with self.assertRaises(Exception):
            registry.assert_launchable("pp:gates-of-olympus")
        registry.register(self._cert(game_id="ok:1"))
        registry.assert_launchable("ok:1")
        self.assertEqual(registry.launchable_ids(), ["ok:1"])
        self.assertEqual(len(registry.blocked()), 1)

    def test_exclusion(self):
        exclusions = ExclusionRegistry()
        exclusions.self_exclude("bruno", "2027-01-01")
        exclusions.assert_playable("ana")
        with self.assertRaises(Exception):
            exclusions.assert_playable("bruno")
        exclusions.block("carla")
        with self.assertRaises(Exception):
            exclusions.assert_playable("carla")

    def test_limits(self):
        limits = Limits(deposit_daily=50000)
        self.assertEqual(limits.breached(deposit_today=10000), [])
        self.assertEqual(limits.breached(deposit_today=60000), ["deposit limit"])

    def test_sigap_window(self):
        reporter = SigapReporter()
        start = datetime(2026, 9, 30, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc)
        envelope = reporter.build_window(start, end, 100000, 92000, 50000, 30000, 120, {"sports": 60000})
        self.assertEqual(envelope["ggr"], 8000)
        self.assertEqual(envelope["retention_until"][:4], "2031")
        self.assertTrue(reporter.cadence_ok(start, end))
        self.assertFalse(reporter.cadence_ok(start, start + timedelta(hours=12)))
        self.assertEqual(certification_deadline(date(2026, 1, 15)), date(2026, 4, 15))
        with self.assertRaises(Exception):
            reporter.build_window(end, start, 1, 1, 1, 1, 1)


class ValidationTest(unittest.TestCase):
    def test_freshness(self):
        report = gates.GateReport("x")
        gates.check_freshness(report, datetime.now(timezone.utc))
        self.assertTrue(report.ok)
        stale = gates.GateReport("y")
        gates.check_freshness(stale, datetime.now(timezone.utc) - timedelta(hours=2))
        self.assertFalse(stale.ok)
        with self.assertRaises(gates.GateError):
            stale.require()
        naive = gates.GateReport("z")
        gates.check_freshness(naive, datetime.now())
        self.assertFalse(naive.ok)

    def test_odds_and_margin(self):
        report = gates.GateReport("m")
        gates.check_odds(report, [1.95, 3.40, 4.20])
        self.assertTrue(report.ok)
        bad = gates.GateReport("m")
        gates.check_odds(bad, [1.00, 5.00])
        self.assertFalse(bad.ok)
        thin = gates.GateReport("t")
        gates.check_margin(thin, [2.00, 2.01])
        self.assertFalse(thin.ok)

    def test_stake_and_duplicate_and_settlement(self):
        report = gates.GateReport("s")
        gates.check_stake(report, 500, 100000)
        self.assertTrue(report.ok)
        zero = gates.GateReport("s")
        gates.check_stake(zero, 0, 100000)
        self.assertFalse(zero.ok)
        dup = gates.GateReport("d")
        gates.check_duplicate(dup, {}, "k", "v")
        self.assertTrue(dup.ok)
        dup2 = gates.GateReport("d")
        gates.check_duplicate(dup2, {"k": "other"}, "k", "v")
        self.assertFalse(dup2.ok)
        settle = gates.GateReport("st")
        gates.check_settlement(settle, 5000, 9750, 2.0)
        self.assertTrue(settle.ok)
        bad = gates.GateReport("st")
        gates.check_settlement(bad, 5000, 50000, 2.0)
        self.assertFalse(bad.ok)


class RegistryTest(unittest.TestCase):
    def test_devig_providers(self):
        registry = default_registry()
        self.assertEqual(registry.names(), ["additive", "multiplicative", "power", "shin"])
        fair = registry.fair("shin", ("2.75", "3.10", "2.62"), "1x2")
        self.assertAlmostEqual(sum(fair), 1.0, places=6)
        with self.assertRaises(Exception):
            registry.fair("nope", ("2.00", "2.00"), "2way")
        with self.assertRaises(Exception):
            registry.fair("shin", ("2.00",), "2way")


class SportsStubTest(unittest.TestCase):
    def test_lifecycle(self):
        engine = SportsStub()
        fixtures = engine.fixtures()
        self.assertEqual(len(fixtures), 1)
        markets = engine.markets(fixtures[0].key)
        self.assertTrue(all(m.key for m in markets))
        key = next(m.key for m in markets if m.kind == "1x2")
        receipt = engine.accept("bet:1", key, 5000)
        self.assertEqual(receipt.accepted_version, 1)
        engine.reprice(key, (1.80, 3.60, 4.60))
        with self.assertRaises(Exception):
            engine.accept("bet:1", key, 5000)
        self.assertEqual(engine.settle("bet:1", {"selection": "home"}), "won")
        with self.assertRaises(Exception):
            engine.settle("bet:1", {"selection": "home"})
        with self.assertRaises(Exception):
            engine.settle("bet:9", {"selection": "home"})
        with self.assertRaises(Exception):
            engine.settle("bet:2", {"selection": "rocket"})


class CasinoStubTest(unittest.TestCase):
    def test_cert_gate(self):
        agg = CasinoStub()
        session = agg.launch("ana", "pp:gates-of-olympus", "pt-BR", "BRL")
        result = agg.bet(session, "round:1", 1000)
        self.assertEqual(result.stake_minor, 1000)
        with self.assertRaises(Exception):
            agg.bet(session, "round:1", 1000)
        with self.assertRaises(Exception):
            agg.launch("ana", "ev:lightning-roulette", "pt-BR", "BRL")
        with self.assertRaises(Exception):
            agg.launch("ana", "pp:gates-of-olympus", "pt-BR", "USD")
        self.assertTrue(agg.wallet_credit("round:1", 0))
        self.assertFalse(agg.wallet_credit("round:1", 0))
        self.assertEqual(len(agg.round_history(session, 10)), 1)


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.scheduler = Scheduler(self.tmp, max_per_cycle=2, cooldown_seconds=3600, daily_limit=3)

    def test_caps_cooldown_daily(self):
        first = self.scheduler.gate(["a", "b", "c"])
        self.assertEqual(first, ["a", "b"])
        self.assertEqual(self.scheduler.gate(["a", "b"]), [])
        self.assertEqual(self.scheduler.gate(["c"]), ["c"])
        self.assertEqual(self.scheduler.gate(["d"]), [])
        self.assertEqual(self.scheduler.notified_today(), 3)

    def test_dry_run_records_nothing(self):
        chosen = self.scheduler.gate(["a"], dry_run=True)
        self.assertEqual(chosen, ["a"])
        self.assertEqual(self.scheduler.notified_today(), 0)
        self.assertEqual(self.scheduler.gate(["a"]), ["a"])

    def test_receipt(self):
        record = self.scheduler.receipt("core", 140, 2, 1, [])
        self.assertEqual(record["tier"], "core")
        self.assertEqual(self.scheduler.last_receipt()["screened"], 140)


class OpsTest(unittest.TestCase):
    def test_local_notifier(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "outbox.jsonl")
        channel = LocalNotifier(path)
        self.assertTrue(channel.test())
        self.assertTrue(os.path.getsize(path) > 0)

    def test_health_wires(self):
        tmp = tempfile.mkdtemp()
        scheduler = Scheduler(os.path.join(tmp, "state"))
        scheduler.receipt("core", 10, 1, 1, [])
        ledger_path = os.path.join(tmp, "ledger.jsonl")
        IntegrityLedger(ledger_path).observe("x", "y", 1)
        books_path = os.path.join(tmp, "books.jsonl")
        Books(books_path).deposit("dep:1", "ana", 1000)
        report = health(scheduler, ledger_path, books_path)
        self.assertTrue(report.healthy)
        self.assertEqual(report.status, "ok")


class SportsFeedTest(unittest.TestCase):
    """The live-feed seam: what it does with a provider that is not answering."""

    def _closed_error(self, url: str) -> urllib.error.HTTPError:
        return urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)

    def _capture(self, module) -> list:
        """Run module._http against a 503 and report whether it was closed."""
        error = self._closed_error("https://provider.example/x")
        keep = module.urllib.request.urlopen
        closed: list[bool] = []
        error.close = lambda: closed.append(True)
        module.urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(error)
        try:
            with self.assertRaises(urllib.error.HTTPError):
                module._http("https://provider.example/x")
        finally:
            module.urllib.request.urlopen = keep
        return closed

    def test_a_provider_error_closes_its_response(self):
        """A 503 answer holds its connection open until the collector runs;
        on a feed polled every 30s that is a silent leak, and the operator
        sees nothing but a memory that climbs."""
        from frame.verticals.sports import espn_engine, superbet_engine
        for module in (espn_engine, superbet_engine):
            self.assertEqual(self._capture(module), [True], module.__name__)


if __name__ == "__main__":
    unittest.main(verbosity=2)
