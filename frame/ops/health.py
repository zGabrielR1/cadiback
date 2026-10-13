from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..core.ledger import IntegrityLedger
from ..wallet.books import Books
from .scheduler import Scheduler

OK = "ok"
DEGRADED = "degraded"
DOWN = "down"


@dataclass(frozen=True)
class HealthReport:
    status: str
    checks: tuple[tuple[str, bool, str], ...]

    @property
    def healthy(self) -> bool:
        return self.status == OK

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in self.checks],
        }


def check_receipt(scheduler: Scheduler, max_age_seconds: int) -> tuple[bool, str]:
    receipt = scheduler.last_receipt()
    if receipt is None:
        return False, "no receipt yet; first tick has not run"
    try:
        stamp = datetime.fromisoformat(str(receipt["ts"]))
    except (KeyError, ValueError, TypeError):
        return False, "receipt timestamp unreadable"
    if stamp.tzinfo is None:
        return False, "receipt timestamp naive"
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    if age < 0:
        return False, f"receipt clock is {-age:.0f}s in the future"
    if age > max_age_seconds:
        return False, f"receipt stale: {age:.0f}s old (max {max_age_seconds}s)"
    return True, f"receipt fresh: {age:.0f}s old"


def check_ledger(path: str) -> tuple[bool, str]:
    report = IntegrityLedger(path).verify()
    if report.intact:
        return True, f"{report.records} records, {report.observations} observations, {report.fills} fills"
    return False, f"broken at seq {report.broken_at}: {report.reason}"


def check_books(path: str) -> tuple[bool, str]:
    books = Books(path)
    try:
        books.assert_balanced()
    except Exception as exc:
        return False, str(exc)
    return True, f"{len(books.postings)} postings balance to zero"


def health(scheduler: Scheduler, ledger_path: str, books_path: str, max_age_seconds: int = 1200) -> HealthReport:
    checks = (
        ("receipt", *check_receipt(scheduler, max_age_seconds)),
        ("ledger", *check_ledger(ledger_path)),
        ("books", *check_books(books_path)),
    )
    failed = [name for name, ok, _ in checks if not ok]
    status = OK if not failed else (DEGRADED if len(failed) == 1 else DOWN)
    return HealthReport(status=status, checks=checks)
