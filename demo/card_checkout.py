"""Hosted card deposits, isolated from the merchant's other applications."""
import json
import os
import re
import uuid
import logging
from urllib.error import HTTPError
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .payments import PaymentError, process_deposit


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise PaymentError("Mercado Pago redirect refused")


def request(path, body=None):
    token = os.environ.get("MERCADOPAGO_ACCESS_TOKEN", "")
    if not token:
        raise PaymentError("Cartão indisponível. Escolha outro método.")
    req = Request("https://api.mercadopago.com" + path,
                  data=json.dumps(body).encode() if body is not None else None,
                  headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with build_opener(NoRedirect()).open(req, timeout=15) as response:
            return json.load(response)
    except HTTPError as error:
        logging.getLogger(__name__).warning("Mercado Pago API refused request: HTTP %s", error.code)
        if error.code in (401, 403):
            raise PaymentError("Mercado Pago recusou o acesso desta conta. Verifique as credenciais e as permissões da aplicação.") from None
        if error.code == 400:
            raise PaymentError("Mercado Pago recusou a configuração do checkout. Entre em contato antes de tentar pagar novamente.") from None
        raise PaymentError("Mercado Pago indisponível. Tente novamente.") from None
    except Exception:
        raise PaymentError("Mercado Pago indisponível. Tente novamente.") from None


def create(demo, payload):
    player = payload["player"]
    if (demo.players.read_all().get(player) or {}).get("is_test"):
        raise PaymentError("Contas de teste não abrem cobranças reais de cartão.")
    amount = demo._minor(payload["amount_minor"])
    if amount < 500:
        raise PaymentError("O dep?sito m?nimo com cart?o ? R$ 5,00.")
    key = str(payload.get("deposit_id", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", key):
        raise PaymentError("Identificador de depósito inválido")
    demo.exclusions.assert_playable(player)
    demo._assert_player_limits(player, deposit_amount=amount)
    base = os.environ.get("CARD_PUBLIC_BASE_URL", "https://cadiback-web.vercel.app").rstrip("/")
    if urlparse(base).scheme != "https":
        raise PaymentError("Checkout requires an HTTPS return address")
    identity = player + ":" + key
    with demo.books.lock:
        rows = demo.card_charges.read_all()
        row = rows.get(identity)
        if row and row["amount_minor"] != amount:
            raise PaymentError("Identificador já utilizado com outro valor")
        if row and row.get("checkout_url"):
            return public(row)
        if not row:
            row = {"reference": "operator-card-" + uuid.uuid4().hex, "amount_minor": amount,
                   "player": player, "deposit_id": key, "status": "pending"}
            rows[identity] = row
            demo.card_charges.write_all(rows)
    # References survive ambiguous provider timeouts; only the first approved
    # payment can credit this deposit even if a preference must be recreated.
    raw = request("/checkout/preferences", {
        "items": [{"id": row["reference"], "title": "Crédito de carteira Candibet", "quantity": 1,
                   "currency_id": "BRL", "unit_price": amount / 100}],
        "external_reference": row["reference"], "metadata": {"operator_deposit": row["reference"]},
        "back_urls": {k: base + "/" for k in ("success", "pending", "failure")},
        "auto_return": "approved", "expires": True,
        "expiration_date_to": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        "payment_methods": {"excluded_payment_types": [{"id": k} for k in
            ("ticket", "atm", "bank_transfer", "account_money")], "installments": 1},
    })
    url = urlparse(raw.get("init_point", ""))
    if not raw.get("id") or url.scheme != "https" or url.hostname not in ("www.mercadopago.com.br", "www.mercadopago.com"):
        raise PaymentError("Checkout inválido recebido do provedor")
    with demo.books.lock:
        rows = demo.card_charges.read_all()
        rows[identity].update(checkout_url=raw["init_point"], preference_id=str(raw["id"]))
        demo.card_charges.write_all(rows)
        return public(rows[identity])


def public(row):
    return {k: row.get(k) for k in ("deposit_id", "amount_minor", "status", "checkout_url")}


def status(demo, payload):
    if not os.environ.get("MERCADOPAGO_ACCESS_TOKEN"):
        raise PaymentError("Cartão indisponível. Escolha outro método.")
    identity = payload["player"] + ":" + str(payload.get("deposit_id", ""))
    row = demo.card_charges.read_all().get(identity)
    if not row:
        raise PaymentError("Depósito não encontrado")
    if row["status"] == "paid":
        return public(row)
    matches = request("/v1/payments/search?" + urlencode({"external_reference": row["reference"]})).get("results", [])
    for match in matches:
        payment_id = str(match.get("id", ""))
        if not payment_id.isascii() or not payment_id.isdigit():
            continue
        payment = request("/v1/payments/" + payment_id)
        if payment.get("status") != "approved":
            continue
        if (payment.get("external_reference") != row["reference"] or payment.get("currency_id") != "BRL"
                or payment.get("live_mode") is not True
                or (payment.get("metadata") or {}).get("operator_deposit") != row["reference"]
                or payment.get("payment_type_id") not in ("credit_card", "debit_card")
                or Decimal(str(payment.get("transaction_amount"))) * 100 != row["amount_minor"]):
            raise PaymentError("Pagamento divergente; entre em contato antes de pagar novamente.")
        with demo.books.lock:
            rows = demo.card_charges.read_all()
            current = rows[identity]
            if current["status"] != "paid":
                process_deposit(demo.books, demo.exclusions, demo.limits, current["player"],
                                current["amount_minor"], "debit", deposit_today_minor=demo._deposited_today(current["player"]),
                                deposit_id=current["reference"], metadata={"provider": "mercadopago", "payment_id": payment_id})
                current.update(status="paid", payment_id=payment_id)
                demo.card_charges.write_all(rows)
            return public(current)
    return public(row)
