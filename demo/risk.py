"""In-house risk/fraud detection. Stdlib only. Our side, our rules.

Operates on round dicts (as stored in `demo/data/rounds.jsonl`) plus wallet
turnover — no vendor data needed. Every check is a pure function returning
flag strings; `evaluate_player` bundles them. Thresholds are constructor
arguments so tests pin them and production tunes them without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _parse_ts(value: str) -> datetime:
    stamp = datetime.fromisoformat(str(value))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


@dataclass
class RiskPolicy:
    """ Knobs. Defaults are demo-tight so tests trip them fast."""

    max_rounds_per_10min: int = 30
    stake_spike_multiple: float = 10.0
    loss_chase_streak: int = 5
    min_handle_for_rtp_minor: int = 50000  # R$500 of tested handle
    rtp_tolerance: float = 0.08  # realized RTP may drift ±8pp from expected
    max_withdrawals_per_hour: int = 5


@dataclass
class RiskReport:
    player: str
    flags: list[str] = field(default_factory=list)
    stats: dict[str, float] = field(default_factory=dict)

    @property
    def flagged(self) -> bool:
        return bool(self.flags)


def check_velocity(rounds: list[dict], policy: RiskPolicy) -> list[str]:
    """Too many spins in any trailing 10-minute window."""
    if len(rounds) < 2:
        return []
    stamps = sorted(_parse_ts(r["ts"]) for r in rounds if r.get("ts"))
    window = max(2, policy.max_rounds_per_10min)
    for start in range(len(stamps)):
        end = start
        while (end < len(stamps)
               and (stamps[end] - stamps[start]).total_seconds() <= 600):
            end += 1
        if end - start > window:
            return [f"velocity: {end - start} rounds in 10min "
                    f"(max {policy.max_rounds_per_10min})"]
    return []


def check_stake_spike(rounds: list[dict], policy: RiskPolicy) -> list[str]:
    """Latest stake dwarfs the player's own median (bot / compromised account)."""
    stakes = sorted(int(r.get("stake_minor", 0)) for r in rounds
                    if int(r.get("stake_minor", 0)) > 0)
    if len(stakes) < 5:
        return []
    median = stakes[len(stakes) // 2]
    latest = int(rounds[-1].get("stake_minor", 0))
    if median > 0 and latest >= median * policy.stake_spike_multiple:
        return [f"stake-spike: {latest} vs median {median} "
                f"(x{policy.stake_spike_multiple})"]
    return []


def check_loss_chase(rounds: list[dict], policy: RiskPolicy) -> list[str]:
    """Consecutive losses with rising stakes (harm + chargeback precursor)."""
    streak = 0
    for row in reversed(rounds):
        if int(row.get("payout_minor", 0)) > 0:
            break
        streak += 1
    if streak < policy.loss_chase_streak:
        return []
    stakes = [int(r.get("stake_minor", 0)) for r in rounds[-streak:]]
    if stakes[-1] > stakes[0]:
        return [f"loss-chase: {streak} winless rounds with rising stake "
                f"({stakes[0]} -> {stakes[-1]})"]
    return []


def check_rtp_deviation(rounds: list[dict], expected_rtp: float,
                        policy: RiskPolicy) -> list[str]:
    """Realized payout ratio far from the math model after enough handle.

    In testing this catches payout bugs (double-credit, wrong multiplier);
    in production it catches misconfigured or tampered games.
    """
    handle = sum(int(r.get("stake_minor", 0)) for r in rounds)
    if handle < policy.min_handle_for_rtp_minor:
        return []
    payout = sum(int(r.get("payout_minor", 0)) for r in rounds)
    realized = payout / handle if handle else 0.0
    if abs(realized - expected_rtp) > policy.rtp_tolerance:
        return [f"rtp-deviation: realized {realized:.3f} vs expected "
                f"{expected_rtp:.3f} over {handle} minor"]
    return []


def check_duplicate_round(round_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    for round_id in round_ids:
        if round_id in seen:
            return [f"duplicate-round: {round_id} settled twice"]
        seen.add(round_id)
    return []


def evaluate_player(player: str, rounds: list[dict], expected_rtp: float,
                    policy: RiskPolicy | None = None) -> RiskReport:
    policy = policy or RiskPolicy()
    mine = [r for r in rounds if r.get("player") == player]
    # sort on parsed time, not the raw string: "…Z" and "…+00:00" are the same
    # instant but not the same string, and a naive row has no offset at all
    mine.sort(key=lambda r: _parse_ts(r.get("ts") or "1970-01-01T00:00:00+00:00"))
    flags: list[str] = []
    flags += check_velocity(mine, policy)
    flags += check_stake_spike(mine, policy)
    flags += check_loss_chase(mine, policy)
    flags += check_rtp_deviation(mine, expected_rtp, policy)
    flags += check_duplicate_round([str(r.get("round_id")) for r in mine])
    handle = float(sum(int(r.get("stake_minor", 0)) for r in mine))
    payout = float(sum(int(r.get("payout_minor", 0)) for r in mine))
    return RiskReport(player=player, flags=flags, stats={
        "rounds": float(len(mine)), "handle_minor": handle,
        "payout_minor": payout,
        "realized_rtp": (payout / handle) if handle else 0.0})
