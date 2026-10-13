from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

BRAZIL = "BR"
MIN_RETENTION_YEARS = 5
CERTIFICATION_DEADLINE_DAYS = 90
REPORTING_FREQUENCY_PER_DAY = 3

STATUS_CERTIFIED = "certified"
STATUS_PENDING = "pending"
STATUS_REJECTED = "rejected"
SUBMITTED = "submitted"
NOT_SUBMITTED = "not_submitted"


class ComplianceError(RuntimeError):
    pass


class CertificationError(ComplianceError):
    pass


class ExclusionError(ComplianceError):
    pass


class ReportingError(ComplianceError):
    pass


@dataclass(frozen=True)
class GameCertification:
    game_id: str
    provider: str
    title: str
    rng_reference: str
    certificate_id: str
    lab: str
    issued_for: str
    status: str
    sigap_submission: str
    certified_on: str
    rtp: str

    @property
    def launchable(self) -> bool:
        return (
            self.status == STATUS_CERTIFIED
            and self.issued_for == BRAZIL
            and bool(self.certificate_id)
            and self.sigap_submission == SUBMITTED
        )

    def blocking_reasons(self) -> list[str]:
        reasons: list[str] = []
        if self.status != STATUS_CERTIFIED:
            reasons.append(f"status={self.status}")
        if self.issued_for != BRAZIL:
            reasons.append(f"certificate issued for {self.issued_for}, not {BRAZIL}")
        if not self.certificate_id:
            reasons.append("no certificate id")
        if self.sigap_submission != SUBMITTED:
            reasons.append(f"sigap submission={self.sigap_submission}")
        return reasons


class GameRegistry:
    """A game may not go live until it holds a Brazil-issued certificate and is in SIGAP."""

    def __init__(self) -> None:
        self._games: dict[str, GameCertification] = {}

    def register(self, cert: GameCertification) -> None:
        if not cert.game_id:
            raise CertificationError("game needs an id")
        self._games[cert.game_id] = cert

    def get(self, game_id: str) -> GameCertification:
        if game_id not in self._games:
            raise CertificationError(f"unknown game: {game_id}")
        return self._games[game_id]

    def assert_launchable(self, game_id: str) -> GameCertification:
        cert = self.get(game_id)
        if not cert.launchable:
            raise CertificationError(
                f"game {game_id} ({cert.title}) not launchable: {'; '.join(cert.blocking_reasons())}"
            )
        return cert

    def launchable_ids(self) -> list[str]:
        return sorted(g for g, c in self._games.items() if c.launchable)

    def blocked(self) -> list[tuple[str, list[str]]]:
        return [(g, c.blocking_reasons()) for g, c in sorted(self._games.items()) if not c.launchable]

    def all(self) -> list[GameCertification]:
        return [self._games[k] for k in sorted(self._games)]


@dataclass
class ExclusionRegistry:
    """Self-exclusion expires on its own date and survives a restart.

    A control advertised as "respected everywhere" that quietly lifts when
    the expiry passes, or dies with the process, is not a control.
    """

    governmental: set[str] = field(default_factory=set)
    self_declared: dict[str, str] = field(default_factory=dict)

    def block(self, player_id: str) -> None:
        self.governmental.add(player_id)

    def self_exclude(self, player_id: str, until: str) -> None:
        self.self_declared[player_id] = str(until)[:10]

    def lift(self, player_id: str) -> bool:
        return self.self_declared.pop(player_id, None) is not None

    def active(self, player_id: str, today: date | None = None) -> bool:
        until = self.self_declared.get(player_id)
        if not until:
            return False
        now = today or date.today()
        try:
            return now <= date.fromisoformat(until)
        except ValueError:
            return True  # unparseable expiry: fail closed, stay excluded

    def reasons(self, player_id: str, today: date | None = None) -> list[str]:
        found: list[str] = []
        if player_id in self.governmental:
            found.append("governmental exclusion list")
        until = self.self_declared.get(player_id)
        if until:
            try:
                expired = (today or date.today()) > date.fromisoformat(until)
            except ValueError:
                expired = False
            if expired:
                found.append(f"self-exclusion expired on {until}")
            else:
                found.append(f"self-excluded until {until}")
        return found

    def assert_playable(self, player_id: str, today: date | None = None) -> None:
        blocking = [r for r in self.reasons(player_id, today)
                    if not r.startswith("self-exclusion expired")]
        if blocking:
            raise ExclusionError(
                f"player {player_id} may not transact: {'; '.join(blocking)}")

    def as_dict(self) -> dict:
        return {"governmental": sorted(self.governmental),
                "self_declared": dict(sorted(self.self_declared.items()))}

    @classmethod
    def from_dict(cls, data: dict) -> "ExclusionRegistry":
        return cls(governmental=set(data.get("governmental", [])),
                   self_declared=dict(data.get("self_declared", {})))


@dataclass
class Limits:
    deposit_daily: int | None = None
    loss_daily: int | None = None
    session_minutes: int | None = None

    def breached(self, deposit_today: int = 0, loss_today: int = 0) -> list[str]:
        """A limit is inclusive: landing exactly on the cap is allowed.

        `>` would reject R$50.000,00 while accepting R$49.999,99, which is
        both wrong and unexplainable to a player.
        """
        found: list[str] = []
        if self.deposit_daily is not None and deposit_today > self.deposit_daily:
            found.append("deposit limit")
        if self.loss_daily is not None and loss_today > self.loss_daily:
            found.append("loss limit")
        return found


class SigapReporter:
    """Emits the regulator-shaped aggregate. Transport is a seam, not a guess."""

    def __init__(self) -> None:
        self.windows: list[dict[str, object]] = []

    def build_window(
        self,
        window_start: datetime,
        window_end: datetime,
        handle: int,
        payout: int,
        deposits: int,
        withdrawals: int,
        players: int,
        by_product: dict[str, int] | None = None,
    ) -> dict[str, object]:
        if window_end <= window_start:
            raise ReportingError("window end must be after window start")
        if min(handle, payout, deposits, withdrawals, players) < 0:
            raise ReportingError("report quantities must be non-negative")
        ggr = handle - payout
        envelope = {
            "window_start": window_start.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "window_end": window_end.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "currency": "BRL",
            "handle": handle,
            "payout": payout,
            "ggr": ggr,
            "deposits": deposits,
            "withdrawals": withdrawals,
            "distinct_players": players,
            "by_product": by_product or {},
            "retention_until": (date.today() + timedelta(days=365 * MIN_RETENTION_YEARS)).isoformat(),
        }
        self.windows.append(envelope)
        return envelope

    def cadence_ok(self, window_start: datetime, window_end: datetime) -> bool:
        hours = (window_end - window_start).total_seconds() / 3600
        return 1 <= hours <= 24 / REPORTING_FREQUENCY_PER_DAY + 0.01


def certification_deadline(authorisation_date: date) -> date:
    return authorisation_date + timedelta(days=CERTIFICATION_DEADLINE_DAYS)
