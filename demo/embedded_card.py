"""Tokenized embedded cards. PAN/CVV never enter the application or its stores."""
import hashlib
import json
import os
import re
import uuid
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from . import card_checkout as legacy
from .payments import PaymentError, process_deposit, validate_cpf, validate_cnpj

CARD_TYPES = ("credit_card", "debit_card", "prepaid_card")
TERMINAL = ("rejected", "cancelled", "refunded", "charged_back")


def configured():
    return bool(os.environ.get("MERCADOPAGO_ACCESS_TOKEN") and os.environ.get("MERCADOPAGO_PUBLIC_KEY"))


def public(row):
    result = {k: row.get(k) for k in ("deposit_id", "amount_minor", "status", "payment_id")}
    result.update(checkout_mode="embedded", public_key=os.environ.get("MERCADOPAGO_PUBLIC_KEY", ""))
    if row.get("three_ds_info"):
        result["three_ds_info"] = row["three_ds_info"]
    return result


def assert_player(demo, player):
    if not configured() or (demo.players.read_all().get(player) or {}).get("is_test"):
        raise PaymentError("Cartão indisponível para esta conta.")
    demo.exclusions.assert_playable(player)


def create(demo, payload):
    player = payload["player"]
    assert_player(demo, player)
    amount = demo._minor(payload["amount_minor"])
    if amount < 500:
        raise PaymentError("O depósito mínimo com cartão é R$ 5,00.")
    key = str(payload.get("deposit_id", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", key):
        raise PaymentError("Identificador de depósito inválido")
    demo._assert_player_limits(player, deposit_amount=amount)
    with demo.books.lock:
        rows = demo.card_charges.read_all()
        row = rows.get(player + ":" + key)
        if row:
            if row["amount_minor"] != amount:
                raise PaymentError("Identificador já utilizado com outro valor")
            return public(row) if row.get("checkout_mode") == "embedded" else legacy.public(row)
        row = dict(reference="operator-card-" + uuid.uuid4().hex, player=player,
                   deposit_id=key, amount_minor=amount, status="prepared", checkout_mode="embedded")
        rows[player + ":" + key] = row
        demo.card_charges.write_all(rows)
        return public(row)


def payment_body(form, row):
    if not isinstance(form, dict) or set(form) - {"token", "payment_method_id", "payment_method_option_id", "issuer_id", "installments", "payer", "transaction_amount", "processing_mode"}:
        raise PaymentError("Envie somente o token gerado pelo formulário seguro.")
    token, method = form.get("token"), form.get("payment_method_id")
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", token):
        raise PaymentError("Token de cartão inválido. Confira os dados do formulário.")
    if not isinstance(method, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", method):
        raise PaymentError("Bandeira de cartão inválida.")
    if form.get("installments") not in (1, "1"):
        raise PaymentError("O depósito com cartão é feito em uma parcela.")
    payer = form.get("payer")
    if not isinstance(payer, dict) or set(payer) - {"email", "identification", "first_name", "last_name"}:
        raise PaymentError("Dados do pagador inválidos.")
    email = payer.get("email")
    document = payer.get("identification")
    if not isinstance(email, str) or not re.fullmatch(r"[^\s@]{1,100}@[^\s@]{1,100}\.[^\s@]{2,50}", email):
        raise PaymentError("Confira o e-mail do pagador.")
    if (not isinstance(document, dict) or set(document) != {"type", "number"}
            or document.get("type") not in ("CPF", "CNPJ")
            or not re.fullmatch(r"[0-9]{11}|[0-9]{14}", str(document.get("number", "")))):
        raise PaymentError("Confira o CPF ou CNPJ do pagador.")
    document = {"type": document["type"], "number":
                (validate_cpf if document["type"] == "CPF" else validate_cnpj)(str(document["number"]))}
    body = dict(transaction_amount=row["amount_minor"] / 100, token=token,
                payment_method_id=method, installments=1,
                payer={"email": email, "identification": document},
                description="Crédito de carteira Candibet", external_reference=row["reference"],
                metadata={"operator_deposit": row["reference"]}, three_d_secure_mode="optional")
    if form.get("issuer_id") not in (None, ""):
        issuer = str(form["issuer_id"])
        if not re.fullmatch(r"[0-9]{1,20}", issuer):
            raise PaymentError("Emissor do cartão inválido.")
        body["issuer_id"] = issuer
    return body


def submit(demo, payload):
    player = payload["player"]
    assert_player(demo, player)
    identity = player + ":" + str(payload.get("deposit_id", ""))
    with demo.books.lock:
        rows = demo.card_charges.read_all()
        row = rows.get(identity)
        if not row or row.get("checkout_mode") != "embedded":
            raise PaymentError("Depósito não encontrado")
        if row["status"] == "paid" or row.get("payment_id"):
            return status(demo, payload)
        demo._assert_player_limits(player, deposit_amount=row["amount_minor"])
        body = payment_body(payload.get("form_data"), row)
        digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        if row.get("request_digest") and row["request_digest"] != digest:
            raise PaymentError("Pagamento já enviado. Verifique o pagamento antes de tentar novamente.")
        methods = legacy.request("/v1/payment_methods")
        if not any(m.get("id") == body["payment_method_id"] and m.get("payment_type_id") in CARD_TYPES for m in methods):
            raise PaymentError("Este método não é um cartão aceito.")
        row.update(request_digest=digest, status="submitting")
        demo.card_charges.write_all(rows)
    # Commit the attempt before provider I/O. Retrying this exact body uses the
    # same provider key; a new token/body cannot silently become another charge.
    payment = legacy.request("/v1/payments", body, idempotency_key=row["reference"])
    return reconcile(demo, identity, payment)


def validate_payment(row, payment):
    try:
        amount = Decimal(str(payment.get("transaction_amount"))) * 100
        valid_amount = amount.is_finite() and amount == row["amount_minor"]
    except (InvalidOperation, TypeError, ValueError):
        valid_amount = False
    if (not valid_amount or payment.get("external_reference") != row["reference"]
            or payment.get("currency_id") != "BRL" or payment.get("live_mode") is not True
            or not isinstance(payment.get("metadata"), dict)
            or payment["metadata"].get("operator_deposit") != row["reference"]
            or payment.get("payment_type_id") not in CARD_TYPES
            or not re.fullmatch(r"[0-9]{1,30}", str(payment.get("id", "")))):
        raise PaymentError("Pagamento divergente; entre em contato antes de pagar novamente.")


def reconcile(demo, identity, payment):
    with demo.books.lock:
        rows = demo.card_charges.read_all()
        row = rows[identity]
        validate_payment(row, payment)
        if row["status"] == "paid":
            return public(row)
        payment_id = str(payment["id"])
        if row.get("payment_id") and row["payment_id"] != payment_id:
            raise PaymentError("Identificador de pagamento divergente.")
        provider_status = payment.get("status")
        row.update(payment_id=payment_id, status=provider_status if provider_status in TERMINAL else "pending")
        row.pop("three_ds_info", None)
        info = payment.get("three_ds_info")
        if provider_status == "pending" and payment.get("status_detail") == "pending_challenge" and isinstance(info, dict):
            row["three_ds_info"] = {k: info[k] for k in ("external_resource_url", "creq") if isinstance(info.get(k), str)}
        if provider_status == "approved":
            process_deposit(demo.books, demo.exclusions, demo.limits, row["player"], row["amount_minor"],
                            "debit", deposit_today_minor=demo._deposited_today(row["player"]),
                            deposit_id=row["reference"], metadata={"provider": "mercadopago", "payment_id": payment_id})
            row["status"] = "paid"
        demo.card_charges.write_all(rows)
        return public(row)


def status(demo, payload):
    identity = payload["player"] + ":" + str(payload.get("deposit_id", ""))
    row = demo.card_charges.read_all().get(identity)
    if not row:
        raise PaymentError("Depósito não encontrado")
    if row.get("checkout_mode") != "embedded":
        return legacy.status(demo, payload)
    if not configured():
        raise PaymentError("Cartão indisponível. Escolha outro método.")
    if row["status"] == "paid":
        return public(row)
    if row.get("payment_id"):
        return reconcile(demo, identity, legacy.request("/v1/payments/" + row["payment_id"]))
    if row["status"] != "prepared":
        matches = legacy.request("/v1/payments/search?" + urlencode({"external_reference": row["reference"]})).get("results", [])
        for match in matches:
            payment_id = str(match.get("id", ""))
            if re.fullmatch(r"[0-9]{1,30}", payment_id):
                return reconcile(demo, identity, legacy.request("/v1/payments/" + payment_id))
    return public(row)
