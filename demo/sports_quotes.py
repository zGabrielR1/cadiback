"""Current-board validation for public sportsbook betting routes."""
from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation


class SportsQuoteError(ValueError):
    def __init__(self, message, code="market_unavailable", details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _line(value):
    if value is None:
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError()
        return result
    except (InvalidOperation, ValueError):
        raise SportsQuoteError("Linha de mercado inválida.") from None


def quote_legs(legs, board):
    if not isinstance(legs, list) or not 1 <= len(legs) <= 12:
        raise SportsQuoteError("Selecione entre 1 e 12 partidas.", "invalid_selection")
    fixtures = {str(f.get("key")): f for f in board.get("fixtures", [])}
    result, seen = [], set()
    for leg in legs:
        if not isinstance(leg, dict):
            raise SportsQuoteError("Seleção inválida.", "invalid_selection")
        key = str(leg.get("fixture_key", ""))
        if key in seen:
            raise SportsQuoteError("Use apenas uma seleção por partida. Combinações da mesma partida ainda não estão disponíveis.", "selection_conflict")
        seen.add(key)
        fixture = fixtures.get(key)
        if not fixture or re.search(r"FINAL|AET|\bFT\b|CANCEL|POSTPON|SUSPEND|ABANDON", str(fixture.get("status", "")), re.I):
            raise SportsQuoteError("A partida não está disponível para apostar.")
        kind = str(leg.get("market_kind", "1x2"))
        market = next((m for m in fixture.get("markets", []) if m.get("kind") == kind and _line(m.get("line")) == _line(leg.get("line"))), None)
        selection = leg.get("selection")
        if not market or selection not in market.get("selections", []):
            raise SportsQuoteError("O mercado ou a seleção saiu de oferta. Revise seu boletim.")
        index = market["selections"].index(selection)
        try:
            price = market["prices"][index]
            if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or not 1.01 <= price <= 1000:
                raise ValueError()
        except (IndexError, KeyError, ValueError, TypeError):
            raise SportsQuoteError("Cotação temporariamente indisponível.") from None
        result.append({"fixture_key": key, "market_kind": kind, "line": market.get("line"), "selection": selection, "price": price,
                       "home": fixture.get("home", ""), "away": fixture.get("away", ""), "competition": fixture.get("competition", "")})
    return {"legs": result, "total_price": round(math.prod(leg["price"] for leg in result), 2), "source": board.get("source", "")}


def require_same_prices(submitted, quote):
    for old, current in zip(submitted, quote["legs"]):
        try:
            price = float(old.get("price"))
        except (TypeError, ValueError):
            price = float("nan")
        if not math.isfinite(price) or abs(price - current["price"]) > 0.000001:
            raise SportsQuoteError("As cotações mudaram. Revise e aceite os novos preços antes de confirmar.", "odds_changed", quote)
