# VENDORED from foundry 0.1.0 — do not edit; regenerate with scripts/vendor.py
"""Brazilian identity documents — normalise, validate, mask.

CPF and CNPJ check-digit arithmetic is small, exact and copied into hosts far
too often. It is here as plumbing, with no opinion about who stores the value
or whether a document is required: the host decides that, this module refuses
a number that cannot be valid before it reaches a provider or a database.

Only the 11-digit CPF and the 14-digit CNPJ are covered; a check-digit match is
a structural check, not proof that the Receita Federal issued the number.
"""
from __future__ import annotations


class DocumentError(ValueError):
    """A document cannot be valid. Safe to show to a person."""


def digits_only(value: object) -> str:
    """ASCII digits in ``value``, in order. Everything else is dropped."""
    if value is None:
        return ""
    return "".join(ch for ch in str(value) if "0" <= ch <= "9")


def validate_cpf(value: object) -> str:
    """Return the normalised 11 digits, or raise :class:`DocumentError`."""
    number = digits_only(value)
    if len(number) != 11:
        raise DocumentError("CPF must have 11 digits")
    if len(set(number)) == 1:
        raise DocumentError("CPF cannot repeat the same digit")
    first = sum(int(d) * w for d, w in zip(number[:9], range(10, 1, -1))) % 11
    first = 0 if first < 2 else 11 - first
    second = sum(int(d) * w for d, w in zip(number[:10], range(11, 1, -1))) % 11
    second = 0 if second < 2 else 11 - second
    if int(number[9]) != first or int(number[10]) != second:
        raise DocumentError("CPF check digits do not match")
    return number


def is_valid_cpf(value: object) -> bool:
    try:
        validate_cpf(value)
    except DocumentError:
        return False
    return True


def mask_cpf(value: object) -> str:
    """``***.***.***-25`` for a complete CPF, ``***`` otherwise."""
    number = digits_only(value)
    if len(number) != 11:
        return "***"
    return f"***.***.***-{number[-2:]}"


def validate_cnpj(value: object) -> str:
    """Return the normalised 14 digits, or raise :class:`DocumentError`."""
    number = digits_only(value)
    if len(number) != 14:
        raise DocumentError("CNPJ must have 14 digits")
    if len(set(number)) == 1:
        raise DocumentError("CNPJ cannot repeat the same digit")
    weights1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    first = sum(int(d) * w for d, w in zip(number[:12], weights1)) % 11
    first = 0 if first < 2 else 11 - first
    weights2 = (6,) + weights1
    second = sum(int(d) * w for d, w in zip(number[:13], weights2)) % 11
    second = 0 if second < 2 else 11 - second
    if int(number[12]) != first or int(number[13]) != second:
        raise DocumentError("CNPJ check digits do not match")
    return number


def is_valid_cnpj(value: object) -> bool:
    try:
        validate_cnpj(value)
    except DocumentError:
        return False
    return True


def mask_cnpj(value: object) -> str:
    """``**.***.***/****-81`` for a complete CNPJ, ``***`` otherwise."""
    number = digits_only(value)
    if len(number) != 14:
        return "***"
    return f"**.***.***/****-{number[-2:]}"
