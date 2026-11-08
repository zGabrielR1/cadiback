"""Validate portable wallet postings without a database connection."""
from frame.wallet.books import BalanceError


def validate_postings(rows):
    if not isinstance(rows, list):
        raise ValueError("invalid wallet snapshot")
    keys = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or type(row.get("seq")) is not int or row.get("seq") != index or not isinstance(row.get("key"), str) \
                or not row["key"] or row["key"] in keys or not isinstance(row.get("metadata"), dict) \
                or not isinstance(row.get("kind"), str) or not isinstance(row.get("ts"), str):
            raise ValueError("invalid wallet posting identity")
        legs = row.get("legs")
        if not isinstance(legs, list) or not legs or any(
            not isinstance(leg, dict) or not isinstance(leg.get("account"), str)
            or type(leg.get("amount")) is not int for leg in legs):
            raise ValueError("invalid wallet legs")
        if sum(leg["amount"] for leg in legs) != 0:
            raise BalanceError("wallet posting does not balance")
        keys.add(row["key"])
    return rows

