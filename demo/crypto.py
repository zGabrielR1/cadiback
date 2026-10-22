"""NOWPayments crypto rail — the v1 API, stdlib only.

The operator's own double-entry ledger stays the source of truth. A crypto
invoice is a *request* to move money; a deposit reaches the books only after
the provider independently confirms the payment. The IPN webhook is a hint that
something happened, never proof that it did — every confirmation re-reads the
payment from NOWPayments and checks the amount before a centavo is posted.
That matters more here than with Pix: a crypto IPN can be replayed or forged,
so nothing but a fresh read of the provider is trusted.

    create:   POST /v1/payment            -> a pending invoice + pay address
    confirm:  POST /v1/ipn (x-nowpayments-sig, HMAC-SHA512)
              GET  /v1/payment/{id}       -> status "finished" + price_amount

Docs: nowpayments.io — API v1 (payments) and IPN callback signing.
Credentials come from the environment (or a gitignored `.env.crypto` beside
this repository) and never appear in a log or an error message.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
import threading
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

DEFAULT_BASE_URL = "https://api.nowpayments.io/v1"

# Statuses that mean the money is really here. NOWPayments also emits transit
# statuses (waiting/confirming/sending) and terminal ones; only these two
# families credit. "partially_paid" deliberately does NOT: the amount is short,
# so the amount check would reject it anyway, but it must never look like paid.
PAID_STATUSES = frozenset({"finished", "confirmed"})

_STATUS_MAP = {
    "waiting": "PENDING",
    "confirming": "PENDING",
    "sending": "PENDING",
    "partially_paid": "PENDING",
    "confirmed": "PAID",
    "finished": "PAID",
    "failed": "EXPIRED",
    "refunded": "REFUNDED",
    "expired": "EXPIRED",
}

# Coins offered on the cashier. The codes are NOWPayments' `pay_currency`
# values; the labels are what a player sees. Kept static so the storefront can
# render the picker without the provider being reachable.
SUPPORTED_COINS: tuple[tuple[str, str], ...] = (
    ("btc", "Bitcoin (BTC)"),
    ("eth", "Ethereum (ETH)"),
    ("usdttrc20", "USDT (TRC-20)"),
    ("usdterc20", "USDT (ERC-20)"),
    ("usdc", "USD Coin (USDC)"),
    ("ltc", "Litecoin (LTC)"),
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ENV_FILE = os.path.join(_REPO_ROOT, ".env.crypto")


class CryptoError(ValueError):
    """A refusal or an unreachable provider, phrased for a client."""


@dataclass(frozen=True)
class CryptoCharge:
    """One crypto invoice, reduced to what the operator needs."""

    provider_ref: str
    status: str            # PAID | PENDING | EXPIRED | REFUNDED
    amount_cents: int      # the fiat price we asked for, in centavos
    pay_address: str = ""
    pay_currency: str = ""
    pay_amount: float = 0.0
    price_currency: str = "brl"


# A NOWPayments API key is dash-separated uppercase groups
# (`TESTKEY1-TESTKEY2-TESTKEY3`); an IPN secret is whatever the merchant
# set in the dashboard (a UUID, typically). A credentials file tends to get
# written whichever way is quickest at the time, so a *bare* line (no `KEY=`)
# is classified by that shape rather than refused — and the file's line order
# is not relied on, so swapping the two still loads.
_API_KEY_RE = re.compile(r"^[A-Z0-9]{5,}(?:-[A-Z0-9]{5,}){2,}$")


def read_env_pairs(path: str) -> dict[str, str]:
    """`KEY=value` lines, plus the bare two-line credential file.

    `#` comments and inline comments are tolerated. A bare line (no `=`) is a
    secret written without its name: the one shaped like a NOWPayments API key
    becomes `CRYPTO_API_KEY`, the other `CRYPTO_IPN_SECRET`.
    """
    values: dict[str, str] = {}
    if not path or not os.path.isfile(path):
        return values
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return values
    bare: list[str] = []
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "=" not in text:
            bare.append(text)
            continue
        name, _, value = text.partition("=")
        value = value.split(" #", 1)[0].strip()
        if name.strip():
            values[name.strip()] = value
    for secret in bare:
        if _API_KEY_RE.match(secret) and not values.get("CRYPTO_API_KEY"):
            values["CRYPTO_API_KEY"] = secret
        elif not values.get("CRYPTO_IPN_SECRET"):
            values["CRYPTO_IPN_SECRET"] = secret
        elif not values.get("CRYPTO_API_KEY"):
            values["CRYPTO_API_KEY"] = secret
    return values


# the older name; a caller that only wants the `KEY=value` file keeps working
_read_env_file = read_env_pairs


@dataclass(frozen=True)
class CryptoConfig:
    api_key: str = ""
    ipn_secret: str = ""
    base_url: str = DEFAULT_BASE_URL
    price_currency: str = "brl"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None,
                 env_file: str = DEFAULT_ENV_FILE) -> "CryptoConfig":
        """Environment first; a local `.env.crypto` fills whatever is missing.

        `env` (tests) is exclusive: when a caller hands over a mapping, no
        ambient state is consulted, so a test can never be steered by this
        machine's own credentials.
        """
        if env is not None:
            source = dict(env)
        else:
            source = _read_env_file(env_file)
            source.update(os.environ)
        return cls(
            api_key=(source.get("CRYPTO_API_KEY") or "").strip(),
            ipn_secret=(source.get("CRYPTO_IPN_SECRET") or "").strip(),
            base_url=(source.get("CRYPTO_BASE_URL") or DEFAULT_BASE_URL)
                     .strip().rstrip("/"),
            price_currency=(source.get("CRYPTO_PRICE_CURRENCY") or "brl")
                           .strip().lower(),
        )

    @property
    def configured(self) -> bool:
        """Enough to charge: a key and an https endpoint.

        An `http://` base would put the API key on the wire, so it is treated
        as unconfigured rather than used. The IPN secret is only needed to
        *verify* callbacks; without it the webhook refuses, but the poll still
        credits a finished payment.
        """
        return bool(self.api_key and self.base_url.startswith("https://"))

    @property
    def env_name(self) -> str:
        return "sandbox" if "sandbox" in self.base_url else "production"


class _NoCrossOriginRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse to replay the API key to another host on a redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).netloc != req.host:
            raise CryptoError("refusing cross-host redirect with credentials")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_NoCrossOriginRedirect())


def _default_transport(method: str, url: str, api_key: str,
                       payload: dict | None = None, idempotency_key: str = "",
                       timeout: int = 20) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"x-api-key": api_key, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    request = urllib.request.Request(url, data=body, method=method,
                                     headers=headers)
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise CryptoError(f"NOWPayments refused ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise CryptoError(f"NOWPayments unreachable: {exc.reason}") from exc
    except ValueError as exc:
        raise CryptoError(f"NOWPayments returned unreadable JSON: {exc}") from exc


def _cents(raw: dict) -> int:
    return int(round(float(raw.get("price_amount") or 0) * 100))


def resolve_ipn(payload: dict) -> dict:
    """Reduce an IPN body to (event, deposit id, charge, amount, paid).

    `order_id` is our own deposit id, set when the invoice was made; it is the
    only field that ties an event back to a player. Everything is read
    defensively — a malformed body yields blanks, never a crash.
    """
    status = str(payload.get("payment_status") or "").lower()
    return {
        "event": f"payment.{status}" if status else "payment",
        "deposit_id": str(payload.get("order_id") or ""),
        "provider_ref": str(payload.get("payment_id") or ""),
        "amount_cents": _cents(payload),
        "status": _STATUS_MAP.get(status, ""),
        "paid": status in PAID_STATUSES,
    }


def sign_ipn(payload: dict, secret: str) -> str:
    """The signature NOWPayments puts in `x-nowpayments-sig`.

    HMAC-SHA512 over the JSON body with its keys sorted. The provider's own
    sample serialises with `json.dumps(body, sort_keys=True)`; the compact
    form is what the docs' code sample actually produces. The verifier accepts
    either, and both are HMACs of *this* body, so neither weakens the check.
    """
    compact = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(secret.encode("utf-8"), compact.encode("utf-8"),
                    hashlib.sha512).hexdigest()


class CryptoClient:
    """The thin crypto surface the operator uses. Transport is injectable, so
    the whole deposit path is testable without a network or a real key."""

    def __init__(self, config: CryptoConfig,
                 transport: Callable = _default_transport) -> None:
        if not config.api_key:
            raise CryptoError("CRYPTO_API_KEY required for the crypto client")
        if not config.base_url.startswith("https://"):
            raise CryptoError("CRYPTO_BASE_URL must be https://")
        self.config = config
        self.transport = transport
        self._minimum_cache = {}
        self._minimum_lock = threading.Lock()

    def minimum_payment(self, pay_currency: str, *, refresh: bool = False) -> dict:
        """Merchant-specific minimum, same fixed-rate/fee flags as create.

        Leaving currency_to unset uses the merchant's configured outcome,
        as payment creation does. Never guess BRL from a crypto amount.
        """
        coin = str(pay_currency or "").lower()
        if coin not in {code for code, _ in SUPPORTED_COINS}:
            raise CryptoError("moeda não suportada")
        with self._minimum_lock:
            cached = self._minimum_cache.get(coin)
            if cached and not refresh and time.monotonic() < cached[0]:
                return {**cached[1], "valid_for_seconds": max(1, int(cached[0] - time.monotonic()))}
            query = urllib.parse.urlencode({
                "currency_from": coin, "fiat_equivalent": self.config.price_currency,
                "is_fixed_rate": "true", "is_fee_paid_by_user": "false"})
            raw = self._call("GET", "/min-amount?" + query, timeout=6)
            try:
                fiat = Decimal(str(raw["fiat_equivalent"]))
                crypto = Decimal(str(raw["min_amount"]))
                if not fiat.is_finite() or fiat <= 0 or not crypto.is_finite() or crypto <= 0:
                    raise ValueError()
                minimum = int((fiat * 100).to_integral_value(rounding=ROUND_CEILING))
            except (KeyError, ValueError, InvalidOperation, TypeError, OverflowError):
                raise CryptoError("Não foi possível consultar o mínimo desta rede. Tente novamente.") from None
            if self.config.price_currency != "brl":
                raise CryptoError("O caixa em reais exige cotação BRL da NOWPayments.")
            quote = {"min_minor": minimum, "pay_currency": coin,
                     "currency": "brl", "provider": "NOWPayments",
                     "min_crypto": str(crypto), "valid_for_seconds": 60}
            self._minimum_cache[coin] = (time.monotonic() + 60, quote)
            return dict(quote)

    def _call(self, method: str, path: str, payload: dict | None = None,
              idem: str = "", timeout: int = 20) -> dict:
        result = self.transport(method, self.config.base_url + path,
                                self.config.api_key, payload, idem, timeout)
        if not isinstance(result, dict):
            raise CryptoError("NOWPayments returned a non-object answer")
        return result

    def _to_charge(self, raw: dict) -> CryptoCharge:
        return CryptoCharge(
            provider_ref=str(raw.get("payment_id") or raw.get("id") or ""),
            status=_STATUS_MAP.get(str(raw.get("payment_status") or "")
                                   .lower(), "PENDING"),
            amount_cents=_cents(raw),
            pay_address=str(raw.get("pay_address") or ""),
            pay_currency=str(raw.get("pay_currency") or ""),
            pay_amount=float(raw.get("pay_amount") or 0.0),
            price_currency=self.config.price_currency,
        )

    def create_payment(self, *, txid: str, amount_cents: int,
                       pay_currency: str, description: str = "",
                       ipn_url: str = "") -> CryptoCharge:
        if amount_cents <= 0:
            raise CryptoError("charge amount must be positive")
        minimum = self.minimum_payment(pay_currency, refresh=True)
        if amount_cents < minimum["min_minor"]:
            amount = f'{minimum["min_minor"] / 100:.2f}'.replace(".", ",")
            raise CryptoError(f"Mínimo nesta rede: R$ {amount} (NOWPayments).")
        body = {
            "price_amount": round(amount_cents / 100, 2),
            "price_currency": self.config.price_currency,
            "pay_currency": (pay_currency or "usdttrc20").lower(),
            "order_id": txid,
            "order_description": description or f"Depósito {txid}",
            "is_fixed_rate": True,
            "is_fee_paid_by_user": False,
        }
        if ipn_url:
            body["ipn_callback_url"] = ipn_url
        raw = self._call("POST", "/payment", body, idem=f"dep:{txid}")
        if not raw.get("payment_id"):
            raise CryptoError("NOWPayments created no payment id")
        return self._to_charge(raw)

    def get_payment(self, provider_ref: str) -> CryptoCharge:
        raw = self._call("GET", f"/payment/{provider_ref}")
        return self._to_charge(raw)

    def verify_ipn(self, headers: dict, payload: dict) -> bool:
        """Verify the `x-nowpayments-sig` HMAC of the body.

        Compared in constant time; an unset secret refuses everything rather
        than accepting an unsigned event.
        """
        if not self.config.ipn_secret:
            return False
        signature = ""
        for key, value in (headers or {}).items():
            if str(key).lower() == "x-nowpayments-sig":
                signature = str(value)
                break
        if not signature:
            return False
        key = self.config.ipn_secret.encode("utf-8")
        body_compact = json.dumps(payload, sort_keys=True,
                                  separators=(",", ":")).encode("utf-8")
        body_spaced = json.dumps(payload, sort_keys=True).encode("utf-8")
        # the provider has shipped both serialisations; both sign *this* body
        for body in (body_compact, body_spaced):
            expected = hmac.new(key, body, hashlib.sha512).hexdigest()
            if hmac.compare_digest(signature, expected):
                return True
        return False
