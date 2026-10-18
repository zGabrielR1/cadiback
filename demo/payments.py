"""Demo payments: personal-info validation + Pix payout stub. Stdlib only.

Deposit methods are Pix / TED / debit / prepaid — the Portaria 615/2024
allowlist — plus the crypto coins (decision 0057) that settled as an accepted
rail. Anything else (credit, cash, boleto) is rejected by name, not by silence.
Pix keys follow the BCB shapes (CPF / CNPJ / email / phone / EVP). The account
holder must be the player (own-name rule). All money still moves through
``frame.wallet.Books`` so every demo real balances to zero.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from frame.core.ids import normalize
from frame.wallet.books import DuplicatePosting

PIX_METHODS = ("pix", "ted", "debit", "prepaid")
CRYPTO_METHODS = ("crypto", "bitcoin", "btc", "ethereum", "eth", "usdt", "usdc", "litecoin", "ltc")
PAYMENT_METHODS = PIX_METHODS + CRYPTO_METHODS
REJECTED_METHODS = ("credit", "cash", "boleto", "pix_credito")

_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_PHONE = re.compile(r"^\+?55?\d{10,11}$")
_EVP = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_BANK_CODE = re.compile(r"^\d{3}$")
_AGENCY = re.compile(r"^\d{4,5}$")
_ACCOUNT = re.compile(r"^\d{4,12}-\d$")


class PaymentError(ValueError):
    pass


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def validate_cpf(cpf: str) -> str:
    number = digits_only(cpf)
    if len(number) != 11 or len(set(number)) == 1:
        raise PaymentError("CPF must hold 11 digits")
    first = sum(int(d) * w for d, w in zip(number[:9], range(10, 1, -1))) % 11
    first = 0 if first < 2 else 11 - first
    second = sum(int(d) * w for d, w in zip(number[:10], range(11, 1, -1))) % 11
    second = 0 if second < 2 else 11 - second
    if int(number[9]) != first or int(number[10]) != second:
        raise PaymentError("CPF check digits do not match")
    return number


def validate_cnpj(cnpj: str) -> str:
    number = digits_only(cnpj)
    if len(number) != 14 or len(set(number)) == 1:
        raise PaymentError("CNPJ must hold 14 digits")
    weights1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    first = sum(int(d) * w for d, w in zip(number[:12], weights1)) % 11
    first = 0 if first < 2 else 11 - first
    weights2 = (6,) + weights1
    second = sum(int(d) * w for d, w in zip(number[:13], weights2)) % 11
    second = 0 if second < 2 else 11 - second
    if int(number[12]) != first or int(number[13]) != second:
        raise PaymentError("CNPJ check digits do not match")
    return number


@dataclass(frozen=True)
class PixKey:
    raw: str
    kind: str  # cpf | cnpj | email | phone | evp


def validate_email(email: str) -> str:
    """Player account email: BCB-shaped address, stored lowercase.

    Raises PaymentError (client-safe message) on anything that is not
    an deliverable-looking address.
    """
    value = (email or "").strip().lower()
    if len(value) > 254 or not _EMAIL.match(value):
        raise PaymentError("email inválido")
    return value


_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,19}$")


def validate_username(username: object) -> str:
    """Public handle chosen at signup, used to log in.

    3–20 chars, starts with a letter or digit, then letters/digits/`.`/`_`/`-`.
    Normalised to lowercase so ``Ana`` and ``ana`` are the same account, and
    the store keeps the lowercase form as the only spelling.
    """
    value = str(username or "").strip().lower()
    if not _USERNAME.match(value):
        raise PaymentError(
            "nome de usuário: 3-20 caracteres (letras, números, . _ -), "
            "começando por letra ou número")
    return value


MIN_PLAYER_PASSWORD_LEN = 6


def validate_player_password(password: object) -> str:
    """Player password policy: at least 6 chars with letters and digits.

    Deliberately separate from the panel's 4-char minimum: the player
    login faces the open site, the panel lives behind a hidden shortcut.
    """
    pw = str(password or "")
    if len(pw) < MIN_PLAYER_PASSWORD_LEN or len(pw) > 128:
        raise PaymentError(
            f"a senha precisa de ao menos {MIN_PLAYER_PASSWORD_LEN} caracteres")
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"[0-9]", pw):
        raise PaymentError("a senha precisa de letras e números")
    return pw


def classify_pix_key(raw: str) -> PixKey:
    value = (raw or "").strip()
    if not value:
        raise PaymentError("Pix key is required")
    if _EMAIL.match(value):
        return PixKey(value, "email")
    if _EVP.match(value):
        return PixKey(value, "evp")
    only = digits_only(value)
    if len(only) == 11:
        try:
            validate_cpf(only)
            return PixKey(value, "cpf")
        except PaymentError:
            pass
        if _PHONE.match(value) or _PHONE.match(only):
            return PixKey(value, "phone")
        raise PaymentError("11-digit Pix key is neither a valid CPF nor a phone")
    if len(only) == 14:
        validate_cnpj(only)
        return PixKey(value, "cnpj")
    if _PHONE.match(value) or (_PHONE.match(only) and len(only) in (10, 11, 12, 13)):
        return PixKey(value, "phone")
    raise PaymentError(
        "Pix key must be CPF, CNPJ, email, phone (+55...), or EVP UUID"
    )


@dataclass(frozen=True)
class BankAccount:
    bank_code: str
    agency: str
    account: str
    holder_name: str


def validate_bank_account(
    bank_code: str, agency: str, account: str, holder_name: str, player_name: str
) -> BankAccount:
    if not _BANK_CODE.match((bank_code or "").strip()):
        raise PaymentError("bank code must be 3 digits")
    if not _AGENCY.match(digits_only(agency or "")):
        raise PaymentError("agency must be 4-5 digits")
    if not _ACCOUNT.match((account or "").strip()):
        raise PaymentError("account must look like 12345-6")
    if not (holder_name or "").strip():
        raise PaymentError("account holder name is required")
    if normalize(holder_name) != normalize(player_name):
        raise PaymentError("account holder must be the player (own-name rule)")
    return BankAccount(
        bank_code=bank_code.strip(),
        agency=digits_only(agency),
        account=account.strip(),
        holder_name=holder_name.strip(),
    )


def mask_pix_key(raw: str) -> str:
    value = (raw or "").strip()
    if "@" in value:
        user, _, domain = value.partition("@")
        return f"{user[:2]}***@{domain}"
    only = digits_only(value)
    if len(only) in (11, 14):
        return f"***{only[-4:]}"
    if len(value) > 8:
        return f"{value[:3]}***{value[-3:]}"
    return "***"


def check_deposit_method(method: str) -> str:
    name = (method or "").strip().lower()
    if name in PIX_METHODS or name in CRYPTO_METHODS:
        return name
    if name in REJECTED_METHODS or not name:
        raise PaymentError(
            f"method {name or 'empty'} is prohibited "
            "(Portaria 615/2024: Pix/TED/debit/prepaid or crypto only, "
            "no credit, no cash, no boleto, no Pix Credito)"
        )
    raise PaymentError(f"unknown deposit method: {name}")


def process_deposit(books, exclusions, limits, player_id, amount_minor, method,
                    deposit_today_minor=0, deposit_id=None, metadata=None):
    """Validate then post a demo deposit, idempotent on ``deposit_id``.

    The caller supplies the id. Keying on a running total made a retry a new
    posting, which a double-click (or any client retry) turned into free
    money. A replay now returns the original outcome instead of an error.
    """
    if amount_minor <= 0:
        raise PaymentError("deposit amount must be positive")
    if not deposit_id:
        raise PaymentError("deposit_id is required (idempotency)")
    check_deposit_method(method)
    exclusions.assert_playable(player_id)
    breached = limits.breached(deposit_today=deposit_today_minor + amount_minor)
    if breached:
        raise PaymentError(f"limit breached: {', '.join(breached)}")
    key = f"demo:deposit:{player_id}:{deposit_id}"
    try:
        return books.deposit(key, player_id, amount_minor, metadata=metadata)
    except DuplicatePosting:
        existing = next((p for p in books.postings if p.key == key), None)
        return existing if existing is not None else False


def process_withdrawal(books, exclusions, player_id, amount_minor, registered_pix_key,
                       payout_id):
    """Payout only to the Pix key on file, then run the two-step wallet payout.

    The destination comes from the stored profile, never from the request
    body: an own-name check whose holder name is client-supplied is not an
    own-name check at all. Pix is instant, so request + settle post
    back-to-back, but as two postings, keeping the PSP leg observable.
    """
    if amount_minor <= 0:
        raise PaymentError("withdrawal amount must be positive")
    if not payout_id:
        raise PaymentError("payout_id is required for idempotency")
    if not registered_pix_key:
        raise PaymentError("no Pix key on file for this player")
    key = classify_pix_key(registered_pix_key)
    exclusions.assert_playable(player_id)
    with books.lock:
        if amount_minor > books.available(player_id):
            raise PaymentError("withdrawal exceeds available balance")
        try:
            request_posting = books.withdraw(
                f"demo:wd:{player_id}:{payout_id}", player_id, amount_minor)
        except DuplicatePosting:
            return None  # replay: caller reports the original receipt
        paid_posting = books.settle_withdrawal(
            f"demo:wdp:{player_id}:{payout_id}", player_id, amount_minor)
    books.assert_balanced()
    return {
        "payout_id": payout_id,
        "amount_minor": amount_minor,
        "pix_kind": key.kind,
        "pix_masked": mask_pix_key(key.raw),
        "eta": "seconds (Pix instant, demo stub)",
        "status": "paid (demo — no real money moved)",
        "request_seq": request_posting.seq,
        "paid_seq": paid_posting.seq,
    }
