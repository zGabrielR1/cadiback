from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


class SchedulerError(RuntimeError):
    pass


@dataclass(frozen=True)
class Tier:
    name: str
    interval_seconds: int


CORE = Tier("core", 900)
EXTENDED = Tier("extended", 1800)
CUP = Tier("cup", 3600)
TIERS = {t.name: t for t in (CORE, EXTENDED, CUP)}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Scheduler:
    """Tiered loop with per-subject cooldowns and a daily cap. Quiet is a result, not a failure."""

    state_dir: str
    max_per_cycle: int = 2
    cooldown_seconds: int = 6 * 3600
    daily_limit: int = 6
    _clock = staticmethod(_utc_now)

    def _path(self, name: str) -> str:
        os.makedirs(self.state_dir, exist_ok=True)
        return os.path.join(self.state_dir, name)

    def _load(self, name: str, default: object) -> object:
        path = self._path(name)
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save(self, name: str, payload: object) -> None:
        path = self._path(name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)

    def today_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def notified_today(self) -> int:
        counts = self._load("notify_count.json", {})
        if not isinstance(counts, dict):
            return 0
        return int(counts.get(self.today_key(), 0))

    def cooled_down(self, subject: str) -> bool:
        stamps = self._load("notify_cooldown.json", {})
        if not isinstance(stamps, dict):
            return True
        last = stamps.get(subject)
        if not last:
            return True
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
        return age >= self.cooldown_seconds

    def gate(self, candidates: list[str], dry_run: bool = False) -> list[str]:
        chosen: list[str] = []
        if self.notified_today() >= self.daily_limit:
            return chosen
        for subject in candidates:
            if len(chosen) >= self.max_per_cycle:
                break
            if not self.cooled_down(subject):
                continue
            if self.notified_today() + len(chosen) >= self.daily_limit:
                break
            chosen.append(subject)
        if not dry_run:
            stamps = self._load("notify_cooldown.json", {})
            if not isinstance(stamps, dict):
                stamps = {}
            now = self._clock()
            for subject in chosen:
                stamps[subject] = now
            self._save("notify_cooldown.json", stamps)
            counts = self._load("notify_count.json", {})
            if not isinstance(counts, dict):
                counts = {}
            counts[self.today_key()] = self.notified_today() + len(chosen)
            self._save("notify_count.json", counts)
        return chosen

    def receipt(self, tier: str, screened: int, passed: int, notified: int, errors: list[str]) -> dict[str, object]:
        record = {
            "ts": self._clock(),
            "tier": tier,
            "screened": screened,
            "passed": passed,
            "notified": notified,
            "errors": errors,
        }
        self._save("latest.json", record)
        return record

    def last_receipt(self) -> dict[str, object] | None:
        data = self._load("latest.json", None)
        return data if isinstance(data, dict) else None
