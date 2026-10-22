"""Asaas Pix rail — the official v3 API, stdlib only. Sandbox first.

The operator's own double-entry ledger stays the source of truth. An Asaas
charge is a *request* to move money; a deposit reaches the books only after
the provider independently confirms the payment. The webhook is a hint that
something happened, never proof that it did — every confirmation re-reads the
charge from Asaas and checks the amount before a centavo is posted.

    create:   POST /payments {billingType: PIX}   -> a pending charge
              GET  /payments/{id}/pixQrCode        -> copy-paste + QR image
    confirm:  POST /payments/webhook (asaas-access-token, constant-time)
              GET  /payments/{id}                  -> RECEIVED/CONFIRMED + amount

Docs: developers.asaas.com — Pix integration and webhook security.
Credentials come from the environment (or a gitignored `.env.asaas` beside
this repository) and never appear in a log or an error message.
"""

from __future__ import annotations

import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Callable

DEFAULT_BASE_URL = "https://sandbox.asaas.com/api/v3"

# Events that mean money actually arrived. Asaas also delivers status-only
# events (PAYMENT_UPDATED) and terminal ones; only these two families credit.
PAID_EVENTS = frozenset({"PAYMENT_RECEIVED", "PAYMENT_CONFIRMED",
                         "PAYMENT_RECEIVED_IN_CASH"})

# Asaas answers many granular statuses; the operator only needs four outcomes:
# money is here, money is still coming, money went back, never going to arrive.
_STATUS_MAP = {
    "PENDING": "PENDING",
    "AWAITING_RISK_ANALYSIS": "PENDING",
    "DUNNING_REQUESTED": "PENDING",
    "RECEIVED": "PAID",
    "CONFIRMED": "PAID",
    "RECEIVED_IN_CASH": "PAID",
    "DUNNING_RECEIVED": "PAID",
    "REFUNDED": "REFUNDED",
    "REFUND_REQUESTED": "REFUNDED",
    "REFUND_IN_PROGRESS": "REFUNDED",
    "CHARGEBACK_REQUESTED": "REFUNDED",
    "CHARGEBACK_DISPUTE": "REFUNDED",
    "AWAITING_CHARGEBACK_REVERSAL": "REFUNDED",
    "OVERDUE": "EXPIRED",
    "AWAITING_CANCELLATION": "CANCELLED",
    "CANCELED": "CANCELLED",
    "DELETED": "CANCELLED",
}

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ENV_FILE = os.path.join(_REPO_ROOT, ".env.asaas")


class AsaasError(ValueError):
    """A refusal or an unreachable provider, phrased for a client."""


@dataclass(frozen=True)
class Charge:
    """One Pix charge, reduced to what the operator needs."""

    provider_ref: str
    status: str            # PAID | PENDING | EXPIRED | CANCELLED | REFUNDED
    amount_cents: int
    qr_text: str = ""
    copy_paste: str = ""
    qr_base64: str = ""


def _read_env_file(path: str) -> dict[str, str]:
    """`KEY=value` lines, `#` comments and inline comments tolerated.

    The same one-line-per-setting shape as `.env.render`; an inline `#` is
    dropped so a value may carry a trailing note (`... # sandbox first`).
    """
    values: dict[str, str] = {}
    if not path or not os.path.isfile(path):
        return values
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, value = line.partition("=")
        value = value.split(" #", 1)[0].strip()
        if name.strip():
            values[name.strip()] = value
    return values


@dataclass(frozen=True)
class AsaasConfig:
    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    customer_id: str = ""
    webhook_secret: str = ""

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None,
                 env_file: str = DEFAULT_ENV_FILE) -> "AsaasConfig":
        """Environment first; a local `.env.asaas` fills whatever is missing.

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
            api_key=(source.get("ASAAS_API_KEY") or "").strip(),
            base_url=(source.get("ASAAS_BASE_URL") or DEFAULT_BASE_URL)
                     .strip().rstrip("/"),
            customer_id=(source.get("ASAAS_CUSTOMER_ID") or "").strip(),
            webhook_secret=(source.get("ASAAS_WEBHOOK_SECRET") or "").strip(),
        )

    @property
    def configured(self) -> bool:
        """Enough to charge: a key, a customer, and an https endpoint.

        An `http://` base would put the account key on the wire, so it is
        treated as unconfigured rather than used.
        """
        return bool(self.api_key and self.customer_id
                    and self.base_url.startswith("https://"))

    @property
    def env_name(self) -> str:
        return "sandbox" if "sandbox" in self.base_url else "production"


class _NoCrossOriginRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse to replay the account key to another host on a redirect.

    urllib copies the original headers (including `access_token`) onto a
    302; a provider redirect must never be able to move the credential.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).netloc != req.host:
            raise AsaasError("refusing cross-host redirect with credentials")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_NoCrossOriginRedirect())


def _default_transport(method: str, url: str, api_key: str,
                       payload: dict | None = None, idempotency_key: str = "",
                       timeout: int = 15) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"access_token": api_key, "Accept": "application/json"}
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
        raise AsaasError(f"Asaas refused ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise AsaasError(f"Asaas unreachable: {exc.reason}") from exc
    except ValueError as exc:
        raise AsaasError(f"Asaas returned unreadable JSON: {exc}") from exc


def _cents(raw: dict) -> int:
    return int(round(float(raw.get("value") or 0) * 100))


def resolve_webhook(payload: dict) -> dict:
    """Reduce a webhook body to (event, deposit id, charge, amount, paid).

    `externalReference` is our own deposit id, set when the charge was made;
    it is the only field that ties an event back to a player. Everything is
    read defensively — a malformed body yields blanks, never a crash.
    """
    event = str(payload.get("event") or "")
    payment = payload.get("payment") if isinstance(payload.get("payment"), dict) else {}
    status = _STATUS_MAP.get(str(payment.get("status") or ""), "")
    return {
        "event": event,
        "deposit_id": str(payment.get("externalReference") or ""),
        "provider_ref": str(payment.get("id") or ""),
        "amount_cents": _cents(payment),
        "paid": event in PAID_EVENTS or status == "PAID",
    }


class AsaasClient:
    """The thin Pix surface the operator uses. Transport is injectable, so
    the whole deposit path is testable without a network or a real key."""

    def __init__(self, config: AsaasConfig,
                 transport: Callable = _default_transport) -> None:
        if not config.api_key:
            raise AsaasError("ASAAS_API_KEY required for the Asaas client")
        if not config.base_url.startswith("https://"):
            raise AsaasError("ASAAS_BASE_URL must be https://")
        self.config = config
        self.transport = transport

    def _call(self, method: str, path: str, payload: dict | None = None,
              idem: str = "", timeout: int = 15) -> dict:
        result = self.transport(method, self.config.base_url + path,
                                self.config.api_key, payload, idem, timeout)
        if not isinstance(result, dict):
            raise AsaasError("Asaas returned a non-object answer")
        return result

    @staticmethod
    def _to_charge(raw: dict) -> Charge:
        return Charge(
            provider_ref=str(raw.get("id") or ""),
            status=_STATUS_MAP.get(str(raw.get("status") or ""), "PENDING"),
            amount_cents=_cents(raw),
        )

    def _with_qr(self, charge: Charge) -> Charge:
        """Attach the copy-paste string and the QR image, best effort.

        A charge without a QR is still payable via its invoice link, so a
        failed QR fetch must not fail the whole deposit.
        """
        if not charge.provider_ref:
            return charge
        try:
            qr = self._call("GET", f"/payments/{charge.provider_ref}/pixQrCode")
        except AsaasError:
            return charge
        text = str(qr.get("payload") or "")
        return replace(charge, qr_text=text, copy_paste=text,
                       qr_base64=str(qr.get("encodedImage") or ""))

    def create_pix_charge(self, *, txid: str, amount_cents: int,
                          description: str = "") -> Charge:
        if amount_cents < 500:
            raise AsaasError("O depósito mínimo por Pix é R$ 5,00.")
        due = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
        body = {
            "customer": self.config.customer_id,
            "billingType": "PIX",
            "value": round(amount_cents / 100, 2),
            "dueDate": due,
            "description": description or f"Depósito {txid}",
            "externalReference": txid,
        }
        raw = self._call("POST", "/payments", body, idem=f"dep:{txid}")
        if not raw.get("id"):
            raise AsaasError("Asaas created no charge id")
        return self._with_qr(self._to_charge(raw))

    def get_charge(self, provider_ref: str, with_qr: bool = False) -> Charge:
        raw = self._call("GET", f"/payments/{provider_ref}")
        charge = self._to_charge(raw)
        return self._with_qr(charge) if with_qr else charge

    def verify_webhook(self, headers: dict) -> bool:
        """Asaas signs with a static token in the `asaas-access-token` header.

        Compared in constant time; an unset secret refuses everything rather
        than accepting an unsigned event.
        """
        if not self.config.webhook_secret:
            return False
        token = ""
        for key, value in (headers or {}).items():
            if str(key).lower() == "asaas-access-token":
                token = str(value)
                break
        return hmac.compare_digest(token, self.config.webhook_secret)
