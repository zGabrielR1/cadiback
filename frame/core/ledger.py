from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

OBSERVE = "observe"
FILL = "fill"
GENESIS = "0" * 64

WRITE_ONCE = "write_once"
FILL_ONCE = "fill_once"


class LedgerError(RuntimeError):
    pass


class IntegrityError(LedgerError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record_hash(record: dict[str, Any]) -> str:
    material = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass
class VerifyReport:
    records: int
    head: str
    broken_at: int | None = None
    reason: str | None = None
    observations: int = 0
    fills: int = 0
    rejected: int = 0

    @property
    def intact(self) -> bool:
        return self.broken_at is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "records": self.records,
            "head": self.head,
            "broken_at": self.broken_at,
            "reason": self.reason,
            "observations": self.observations,
            "fills": self.fills,
            "rejected": self.rejected,
            "intact": self.intact,
        }


class IntegrityLedger:
    """Append-only, hash-chained JSONL with write-once observations and fill-once closes.

    A ledger that can be restated is not evidence. Observation fields are recorded
    exactly once; close fields may be filled exactly once and are never rewritten.
    """

    def __init__(self, path: str, clock=_utc_now) -> None:
        self.path = path
        self._clock = clock
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8"):
                pass

    def _iter(self) -> Iterator[dict[str, Any]]:
        with open(self.path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def _append(self, payload: dict[str, Any]) -> dict[str, Any]:
        existing = list(self._iter())
        prev = existing[-1]["hash"] if existing else GENESIS
        record = dict(payload)
        record["seq"] = len(existing)
        record["ts"] = self._clock()
        record["prev"] = prev
        record["hash"] = _record_hash({k: v for k, v in record.items() if k != "hash"})
        line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        directory = os.path.dirname(os.path.abspath(self.path))
        handle_fd, temp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(handle_fd, "w", encoding="utf-8") as temp:
                with open(self.path, "r", encoding="utf-8") as current:
                    while True:
                        chunk = current.read(65536)
                        if not chunk:
                            break
                        temp.write(chunk)
                temp.write(line)
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temp_path, self.path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
        return record

    def _state(self) -> tuple[dict[str, dict[str, Any]], int, int]:
        recorded: dict[str, dict[str, Any]] = {}
        fills = 0
        observations = 0
        for record in self._iter():
            subject = record.get("subject", "")
            if record.get("kind") == OBSERVE:
                recorded.setdefault(subject, {})
                if record["field"] not in recorded[subject]:
                    recorded[subject][record["field"]] = record["value"]
                    observations += 1
            elif record.get("kind") == FILL:
                recorded.setdefault(subject, {})
                if record["field"] not in recorded[subject]:
                    recorded[subject][record["field"]] = record["value"]
                    fills += 1
        return recorded, observations, fills

    def observe(self, subject: str, field_name: str, value: Any) -> bool:
        if not subject or not field_name:
            raise LedgerError("observe needs subject and field")
        observed, _, _ = self._state()
        if field_name in observed.get(subject, {}):
            return False
        self._append(
            {
                "kind": OBSERVE,
                "subject": subject,
                "field": field_name,
                "value": value,
                "semantics": WRITE_ONCE,
            }
        )
        return True

    def fill(self, subject: str, field_name: str, value: Any, note: str | None = None) -> bool:
        if not subject or not field_name:
            raise LedgerError("fill needs subject and field")
        observed, _, _ = self._state()
        if field_name in observed.get(subject, {}):
            return False
        self._append(
            {
                "kind": FILL,
                "subject": subject,
                "field": field_name,
                "value": value,
                "note": note,
                "semantics": FILL_ONCE,
            }
        )
        return True

    def get(self, subject: str) -> dict[str, Any]:
        observed, _, _ = self._state()
        return dict(observed.get(subject, {}))

    def subjects(self) -> list[str]:
        observed, _, _ = self._state()
        return sorted(observed)

    def verify(self) -> VerifyReport:
        observed, observations, fills = self._state()
        prev = GENESIS
        count = 0
        for record in self._iter():
            expected = _record_hash({k: v for k, v in record.items() if k != "hash"})
            if record.get("prev") != prev:
                return VerifyReport(
                    records=count,
                    head=prev,
                    broken_at=record.get("seq"),
                    reason=f"prev mismatch at seq {record.get('seq')}",
                    observations=observations,
                    fills=fills,
                )
            if record.get("hash") != expected:
                return VerifyReport(
                    records=count,
                    head=prev,
                    broken_at=record.get("seq"),
                    reason=f"hash mismatch at seq {record.get('seq')}",
                    observations=observations,
                    fills=fills,
                )
            if record.get("seq") != count:
                return VerifyReport(
                    records=count,
                    head=prev,
                    broken_at=record.get("seq"),
                    reason=f"seq gap at {record.get('seq')}",
                    observations=observations,
                    fills=fills,
                )
            prev = record["hash"]
            count += 1
        return VerifyReport(records=count, head=prev, observations=observations, fills=fills)
