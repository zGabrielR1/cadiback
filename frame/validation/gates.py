from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

MAX_ODDS = 1000.0
MIN_ODDS = 1.01
MAX_STALENESS_SECONDS = 30
MAX_OVERROUND = 0.25
MIN_MARGIN = 0.01
MAX_MARGIN = 0.35


class GateError(RuntimeError):
    pass


@dataclass
class GateReport:
    subject: str
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def fail(self, reason: str) -> "GateReport":
        self.failures.append(reason)
        return self

    def require(self) -> None:
        if self.failures:
            raise GateError(f"{self.subject}: " + "; ".join(self.failures))


def require_fields(report: GateReport, record: dict[str, Any], fields: Sequence[str]) -> GateReport:
    for name in fields:
        if record.get(name) in (None, ""):
            report.fail(f"missing field {name}")
    return report


def check_freshness(
    report: GateReport, observed_at: datetime, max_age_seconds: int = MAX_STALENESS_SECONDS
) -> GateReport:
    now = datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        report.fail("observed_at is naive, cannot age it")
        return report
    age = (now - observed_at).total_seconds()
    if age < 0:
        report.fail(f"observed_at is in the future by {-age:.0f}s")
    elif age > max_age_seconds:
        report.fail(f"stale by {age:.0f}s (max {max_age_seconds}s)")
    return report


def check_odds(report: GateReport, prices: Sequence[float]) -> GateReport:
    if len(prices) < 2:
        report.fail(f"needs at least 2 prices, got {len(prices)}")
        return report
    for price in prices:
        if not MIN_ODDS <= price <= MAX_ODDS:
            report.fail(f"odds {price} outside [{MIN_ODDS},{MAX_ODDS}]")
    total = sum(1.0 / p for p in prices)
    book = total - 1.0
    if book < 0:
        report.fail(f"negative overround {book:.4f} (arb, not a margin book)")
    elif book > MAX_OVERROUND:
        report.fail(f"overround {book:.4f} above ceiling {MAX_OVERROUND}")
    return report


def check_margin(report: GateReport, prices: Sequence[float], min_margin: float = MIN_MARGIN, max_margin: float = MAX_MARGIN) -> GateReport:
    if len(prices) < 2:
        return report.fail("needs at least 2 prices to measure margin")
    book = sum(1.0 / p for p in prices) - 1.0
    if not min_margin <= book <= max_margin:
        report.fail(f"margin {book:.4f} outside [{min_margin},{max_margin}]")
    return report


def check_stake(report: GateReport, stake_minor: int, max_stake_minor: int) -> GateReport:
    if stake_minor <= 0:
        report.fail(f"stake must be positive, got {stake_minor}")
    if stake_minor > max_stake_minor:
        report.fail(f"stake {stake_minor} above limit {max_stake_minor}")
    return report


def check_duplicate(report: GateReport, seen: dict[str, str], key: str, payload: str) -> GateReport:
    if key in seen:
        if seen[key] == payload:
            report.fail(f"duplicate payload for {key}")
        else:
            report.fail(f"conflicting duplicate for {key}")
    return report


def check_covered(report: GateReport, accepted: int, offered: int) -> GateReport:
    if accepted > offered:
        report.fail(f"accepted {accepted} exceeds offered {offered}")
    if offered and accepted / offered < 0.99:
        report.fail(f"acceptance rate {accepted / offered:.3f} below 0.99")
    return report


def check_settlement(report: GateReport, stake_minor: int, payout_minor: int, max_odds: float) -> GateReport:
    if payout_minor < 0:
        report.fail(f"negative payout {payout_minor}")
    ceiling = stake_minor * max_odds + 1
    if payout_minor > ceiling:
        report.fail(f"payout {payout_minor} exceeds ceiling {ceiling}")
    return report
