"""PF/PJ, direct social sign-in and provider-minimum regressions."""
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from demo.asaas import AsaasClient, AsaasConfig, AsaasError
from demo.crypto import CryptoClient, CryptoConfig, CryptoError
from demo.payments import PaymentError, validate_cpf, validate_cnpj
from demo.server import Demo
from foundry.betterauth import SocialIdentity


class SignupCashierTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.demo = Demo(self.tmp.name, player_secret="signup-test-secret")

    def manual(self, **overrides):
        data = dict(name="Ana Souza", username="ana.souza", email="ana@example.com",
                    cpf="529.982.247-25", password="ana1234", pix_key="ana@example.com")
        return self.demo.register_player({**data, **overrides})

    def social(self, provider="google", subject="one", email="social@example.com"):
        identity = SocialIdentity(provider=provider, subject=subject, email=email, name="Ana Social")
        handoff = self.demo.social_login(identity)
        return self.demo.oauth_session(handoff["token"])

    def test_cpf_cnpj_validation_rejects_invalid_and_mixed_input(self):
        self.assertEqual(validate_cpf("529.982.247-25"), "52998224725")
        self.assertEqual(validate_cnpj("11.222.333/0001-81"), "11222333000181")
        self.assertEqual(validate_cnpj("00.000.000/e08g-12"), "00000000E08G12")
        for document in ("111.111.111-11", "529.982.247-26", "x52998224725"):
            with self.assertRaises(PaymentError):
                validate_cpf(document)
        for document in ("00.000.000/0000-00", "11.222.333/0001-80", "00.000.000/E08G-13"):
            with self.assertRaises(PaymentError):
                validate_cnpj(document)

    def test_pj_signup_login_masking_and_duplicate_protection(self):
        row = self.manual(person_type="PJ", cpf="", cnpj="11.222.333/0001-81")
        self.assertEqual(row["person_type"], "PJ")
        self.assertEqual(row["cpf_masked"], "")
        self.assertEqual(row["cnpj_masked"], "**.***.***/****-81")
        self.assertEqual(row["document_validation"], "check_digits")
        self.assertNotIn("document_fingerprint", row)
        self.assertNotIn("pix_raw", row)
        logged = self.demo.login_player({"identifier": "11.222.333/0001-81", "password": "ana1234"})
        self.assertEqual(logged["player_id"], row["player_id"])
        with self.assertRaisesRegex(ValueError, "CNPJ"):
            self.manual(person_type="PJ", cnpj="11222333000181", email="other@example.com", username="other")

    def test_alphanumeric_cnpj_works_in_signup_login_and_pix(self):
        row = self.manual(person_type="PJ", cpf="", cnpj="00.000.000/E08G-12", pix_key="00000000e08g12")
        self.assertEqual(row["pix_kind"], "cnpj")
        logged = self.demo.login_player({"identifier": "00000000e08g12", "password": "ana1234"})
        self.assertEqual(logged["player_id"], row["player_id"])

    def test_pf_mask_and_invalid_person_type(self):
        row = self.manual()
        self.assertEqual(row["cpf_masked"], "***.***.***-25")
        with self.assertRaises(PaymentError):
            self.manual(person_type="invalid")

    def test_both_social_providers_skip_document_username_password_and_pix_forms(self):
        for provider in ("google", "facebook"):
            row = self.social(provider, email=f"{provider}@example.com")
            self.assertFalse(row["needs_profile"])
            self.assertEqual(row["document_validation"], "not_requested")
            self.assertFalse(row["pix_registered"])
            self.assertEqual(len(self.demo.player_devices.active(row["player_id"])), 1)
            self.assertEqual(self.demo.player_from_token(row["player_token"]), row["player_id"])

    def test_first_withdrawal_requires_pix_and_registration_does_not_require_cpf(self):
        row = self.social()
        player = row["player_id"]
        self.demo.deposit({"player": player, "amount_minor": 1000, "method": "pix", "deposit_id": "seed"})
        with self.assertRaisesRegex(ValueError, "Pix key"):
            self.demo.withdraw({"player": player, "amount_minor": 500, "payout_id": "wd"})
        self.assertEqual(self.demo.books.available(player), 1000)
        with self.assertRaises(PaymentError):
            self.demo.register_pix_key(player, "not-a-key")
        profile = self.demo.register_pix_key(player, "ana@example.com")
        self.assertTrue(profile["pix_registered"])
        self.assertNotIn("pix_raw", profile)
        with self.assertRaises(PaymentError):
            self.demo.register_pix_key(player, "different@example.com")
        receipt = self.demo.withdraw({"player": player, "amount_minor": 500, "payout_id": "wd"})
        self.assertEqual(receipt["available_minor"], 500)
        self.demo.books.assert_balanced()

    def test_pix_minimum_is_enforced_before_provider_and_reported_to_ui(self):
        row = self.manual()
        calls = []
        def transport(*args):
            calls.append(args)
            return {}
        config = AsaasConfig(api_key="test", base_url="https://example.com", customer_id="c")
        self.demo.asaas = AsaasClient(config, transport=transport)
        self.assertEqual(self.demo.deposit_limits(row["player_id"], "pix")["min_minor"], 500)
        with self.assertRaises(AsaasError):
            self.demo.create_pix_deposit({"player": row["player_id"], "amount_minor": 499})
        self.assertEqual(calls, [])

    def test_pix_email_punctuation_cannot_change_the_payout_destination(self):
        row = self.social()
        player = row["player_id"]
        self.demo.register_pix_key(player, "ana.souza@example.com")
        with self.assertRaises(PaymentError):
            self.demo.register_pix_key(player, "ana-souza@example.com")
        self.assertEqual(self.demo.pix_keys[player], "ana.souza@example.com")
        with self.assertRaises(ValueError):
            self.demo.withdraw({"player": player, "amount_minor": 500,
                                "pix_key": "ana-souza@example.com", "payout_id": "no"})
        self.demo.register_pix_key(player, "ANA.SOUZA@EXAMPLE.COM")
        self.assertEqual(self.demo.pix_keys[player], "ana.souza@example.com")


class CryptoMinimumTest(unittest.TestCase):
    def client(self, fiat="99.33186531"):
        self.calls = []
        def transport(method, url, key, payload, idem, timeout):
            self.calls.append((method, url, payload))
            return {"currency_from": "usdttrc20", "min_amount": "19.701553", "fiat_equivalent": fiat}
        return CryptoClient(CryptoConfig(api_key="test"), transport=transport)

    def test_rounds_up_and_matches_actual_payment_flags_and_merchant_outcome(self):
        client = self.client()
        quote = client.minimum_payment("usdttrc20")
        self.assertEqual(quote["min_minor"], 9934)
        params = parse_qs(urlparse(self.calls[0][1]).query)
        self.assertEqual(params["fiat_equivalent"], ["brl"])
        self.assertEqual(params["is_fixed_rate"], ["true"])
        self.assertEqual(params["is_fee_paid_by_user"], ["false"])
        self.assertNotIn("currency_to", params)
        with self.assertRaises(CryptoError):
            client.create_payment(txid="low", amount_cents=9933, pay_currency="usdttrc20")
        self.assertTrue(all(method == "GET" for method, _, _ in self.calls))

    def test_cache_is_bounded_per_network_and_reloads_after_expiry(self):
        client = self.client()
        with patch("demo.crypto.time.monotonic", return_value=100):
            client.minimum_payment("usdttrc20")
            client.minimum_payment("usdttrc20")
            self.assertEqual(len(self.calls), 1)
            client.minimum_payment("btc")
            self.assertEqual(len(self.calls), 2)
        with patch("demo.crypto.time.monotonic", return_value=161):
            client.minimum_payment("usdttrc20")
            self.assertEqual(len(self.calls), 3)

    def test_unavailable_or_invalid_minimum_blocks_payment(self):
        for fiat in (None, "NaN", "Infinity", "0", "-1", "not-money"):
            client = self.client(fiat)
            with self.assertRaises(CryptoError):
                client.create_payment(txid="blocked", amount_cents=10000, pay_currency="btc")
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(self.calls[0][0], "GET")

    def test_payment_rechecks_a_minimum_that_changed_since_display(self):
        price = [5]
        calls = []
        def transport(method, url, key, payload, idem, timeout):
            calls.append(method)
            return {"min_amount": 1, "fiat_equivalent": price[0]}
        client = CryptoClient(CryptoConfig(api_key="test"), transport=transport)
        self.assertEqual(client.minimum_payment("btc")["min_minor"], 500)
        price[0] = 100
        with self.assertRaises(CryptoError):
            client.create_payment(txid="changed", amount_cents=1000, pay_currency="btc")
        self.assertEqual(calls, ["GET", "GET"])
        self.assertEqual(client.minimum_payment("btc")["min_minor"], 10000)
