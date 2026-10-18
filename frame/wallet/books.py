from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from ..core.money import gross_return

PLAYER_BALANCE = "player:balance"
PLAYER_BONUS = "player:bonus"
BONUS_ISSUED = "bonus:issued"
OPERATOR_CASH = "operator:cash"
PAYABLE_PLAYER = "payable:player"
BET_STAKED = "bet:staked"
GGR_REVENUE = "ggr:revenue"
BONUS_REVENUE = "bonus:revenue"
ADJUSTMENT = "adjustment:operator"

LIABILITY_ACCOUNTS = frozenset({PLAYER_BALANCE, PLAYER_BONUS, PAYABLE_PLAYER, BONUS_ISSUED})
CLEARING_ACCOUNTS = frozenset({BET_STAKED, OPERATOR_CASH, PAYABLE_PLAYER, GGR_REVENUE, BONUS_REVENUE, ADJUSTMENT})


class WalletError(RuntimeError):
    pass


class BalanceError(WalletError):
    pass


class DuplicatePosting(WalletError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Posting:
    key: str
    kind: str
    metadata: dict[str, object]
    seq: int
    ts: str
    legs: tuple[tuple[str, int], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "key": self.key,
            "kind": self.kind,
            "metadata": self.metadata,
            "legs": [{"account": a, "amount": n} for a, n in self.legs],
        }


@dataclass
class Books:
    """Double-entry books where every posting balances to zero and every posting is idempotent.

    Thread-safe: `post()` holds one lock across the duplicate check, the
    balance guards used by callers, the append, and the in-memory apply. The
    server serves requests on threads, so an unlocked check-then-act silently
    lost postings and let balances go negative while the books still summed to
    zero — a failure `assert_balanced()` structurally cannot see.
    """

    path: str
    postings: list[Posting] = field(default_factory=list)
    balances: dict[str, int] = field(default_factory=dict)
    player_balances: dict[str, dict[str, int]] = field(default_factory=dict)
    _keys: set[str] = field(default_factory=set)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False,
                                   compare=False)
    _clock = staticmethod(_utc_now)

    def __post_init__(self) -> None:
        if self.path:
            directory = os.path.dirname(os.path.abspath(self.path))
            if directory:
                os.makedirs(directory, exist_ok=True)
            if os.path.exists(self.path):
                self._replay()
            else:
                with open(self.path, "w", encoding="utf-8"):
                    pass

    @property
    def lock(self) -> threading.RLock:
        """Callers that guard a balance check against a posting take this."""
        return self._lock

    def _replay(self) -> None:
        self.postings = []
        self.balances = {}
        self.player_balances = {}
        self._keys = set()
        with open(self.path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                posting = Posting(
                    key=raw["key"],
                    kind=raw["kind"],
                    metadata=raw.get("metadata", {}),
                    seq=raw["seq"],
                    ts=raw["ts"],
                    legs=tuple((leg["account"], int(leg["amount"])) for leg in raw["legs"]),
                )
                self.postings.append(posting)
                self._keys.add(posting.key)
                for account, amount in posting.legs:
                    self.balances[account] = self.balances.get(account, 0) + amount
                self._apply_player(posting)

    def _write(self, posting: Posting) -> None:
        """Append one line and fsync. O(1) per posting: the previous
        read-whole-file/rewrite approach lost writes under concurrency."""
        line = json.dumps(posting.as_dict(), ensure_ascii=False, sort_keys=True) + "\n"
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def post(
        self,
        key: str,
        kind: str,
        legs: Sequence[tuple[str, int]],
        metadata: dict[str, object] | None = None,
    ) -> Posting:
        normalised = [(account, int(amount)) for account, amount in legs]
        if not normalised:
            raise WalletError(f"posting {kind} has no legs")
        if sum(amount for _, amount in normalised) != 0:
            raise BalanceError(f"posting {kind} does not balance: {normalised}")
        with self._lock:
            if key in self._keys:
                raise DuplicatePosting(f"idempotency key already posted: {key}")
            posting = Posting(
                key=key,
                kind=kind,
                metadata=metadata or {},
                seq=len(self.postings),
                ts=self._clock(),
                legs=tuple(normalised),
            )
            self._write(posting)
            self.postings.append(posting)
            self._keys.add(key)
            for account, amount in posting.legs:
                self.balances[account] = self.balances.get(account, 0) + amount
            self._apply_player(posting)
            return posting

    def _apply_player(self, posting: Posting) -> None:
        player = str(posting.metadata.get("player", ""))
        if not player:
            return
        bucket = self.player_balances.setdefault(player, {})
        for account, amount in posting.legs:
            bucket[account] = bucket.get(account, 0) + amount

    def balance(self, account: str) -> int:
        return self.balances.get(account, 0)

    @property
    def total(self) -> int:
        return sum(self.balances.values())

    def assert_balanced(self) -> None:
        if self.total != 0:
            raise BalanceError(f"books do not balance: total={self.total} {self.balances}")

    def available(self, player: str) -> int:
        return self.player_balances.get(player, {}).get(PLAYER_BALANCE, 0)

    def bonus_available(self, player: str) -> int:
        return self.player_balances.get(player, {}).get(PLAYER_BONUS, 0)

    def deposit(self, key: str, player: str, amount: int,
                metadata: dict[str, object] | None = None) -> Posting:
        if amount <= 0:
            raise WalletError("deposit amount must be positive")
        meta: dict[str, object] = {"player": player}
        if metadata:
            meta.update(metadata)
        return self.post(
            key,
            "deposit",
            [(PLAYER_BALANCE, amount), (OPERATOR_CASH, -amount)],
            meta,
        )

    def withdraw(self, key: str, player: str, amount: int) -> Posting:
        if amount <= 0:
            raise WalletError("withdrawal amount must be positive")
        with self._lock:
            if amount > self.available(player):
                raise WalletError("withdrawal exceeds available balance")
            return self.post(
                key,
                "withdraw",
                [(PLAYER_BALANCE, -amount), (PAYABLE_PLAYER, amount)],
                {"player": player},
            )

    def settle_withdrawal(self, key: str, player: str, amount: int) -> Posting:
        if amount <= 0:
            raise WalletError("payout amount must be positive")
        return self.post(
            key,
            "withdrawal_paid",
            [(PAYABLE_PLAYER, -amount), (OPERATOR_CASH, amount)],
            {"player": player},
        )

    def grant_bonus(self, key: str, player: str, amount: int) -> Posting:
        if amount <= 0:
            raise WalletError("bonus amount must be positive")
        return self.post(
            key,
            "bonus_grant",
            [(PLAYER_BONUS, amount), (BONUS_ISSUED, -amount)],
            {"player": player},
        )

    def place_bet(
        self,
        key: str,
        player: str,
        stake: int,
        decimal_odds: float,
        bonus_part: int = 0,
    ) -> Posting:
        if stake <= 0:
            raise WalletError("stake must be positive")
        if bonus_part < 0 or bonus_part > stake:
            raise WalletError("bonus_part must be within [0, stake]")
        cash_part = stake - bonus_part
        with self._lock:
            if cash_part > self.available(player):
                raise WalletError("insufficient cash balance")
            if bonus_part > 0 and bonus_part > self.bonus_available(player):
                raise WalletError("insufficient bonus balance")
            legs = [(BET_STAKED, stake)]
            if cash_part:
                legs.append((PLAYER_BALANCE, -cash_part))
            if bonus_part:
                legs.append((PLAYER_BONUS, -bonus_part))
            return self.post(
                key,
                "bet_placed",
                legs,
                {"player": player, "stake": stake,
                 "odds": str(decimal_odds), "bonus_part": bonus_part},
            )

    def settle_bet_win(
        self,
        key: str,
        player: str,
        stake: int,
        decimal_odds: float,
        bonus_part: int = 0,
    ) -> Posting:
        """Pay a win. The bonus-funded portion of the stake pays back into
        `player:bonus`, never into withdrawable cash: bonus money must not
        become cash before its wagering requirement is met."""
        if bonus_part < 0 or bonus_part > stake:
            raise WalletError("bonus_part must be within [0, stake]")
        payout = gross_return(stake, decimal_odds)
        bonus_payout = gross_return(bonus_part, decimal_odds)
        cash_payout = payout - bonus_payout
        revenue = stake - payout
        legs = [(BET_STAKED, -stake), (PLAYER_BALANCE, cash_payout)]
        if bonus_part:
            legs.append((PLAYER_BONUS, bonus_payout))
        legs.append((GGR_REVENUE, revenue))
        return self.post(
            key,
            "bet_settled_win",
            legs,
            {"player": player, "stake": stake, "odds": str(decimal_odds),
             "payout": payout, "bonus_part": bonus_part},
        )

    def settle_bet_loss(self, key: str, player: str, stake: int) -> Posting:
        return self.post(
            key,
            "bet_settled_loss",
            [(BET_STAKED, -stake), (GGR_REVENUE, stake)],
            {"player": player, "stake": stake},
        )

    def settle_casino(
        self,
        key: str,
        player: str,
        stake: int,
        payout: int,
        bonus_part: int = 0,
    ) -> Posting:
        """Settle a casino round with an arbitrary payout (integer minor units).

        Odds-based settlement (`settle_bet_win`) cannot express a return smaller
        than the stake, but a publisher slot outcome often is: a round can pay
        0.42x and still be a win. Here the payout is the exact gross return, and
        revenue is whatever is left of the stake, so the round balances for any
        payout. The bonus-funded share of the stake pays back into
        `player:bonus`, never into withdrawable cash.
        """
        if stake <= 0:
            raise WalletError("stake must be positive")
        if payout < 0:
            raise WalletError("payout must be non-negative")
        if bonus_part < 0 or bonus_part > stake:
            raise WalletError("bonus_part must be within [0, stake]")
        bonus_payout = (payout * bonus_part) // stake
        cash_payout = payout - bonus_payout
        legs = [(BET_STAKED, -stake)]
        if cash_payout:
            legs.append((PLAYER_BALANCE, cash_payout))
        if bonus_payout:
            legs.append((PLAYER_BONUS, bonus_payout))
        legs.append((GGR_REVENUE, stake - payout))
        return self.post(
            key,
            "bet_settled_casino",
            legs,
            {"player": player, "stake": stake, "payout": payout,
             "bonus_part": bonus_part},
        )

    def settle_bet_push(self, key: str, player: str, stake: int, bonus_part: int = 0) -> Posting:
        cash_part = stake - bonus_part
        legs = [(BET_STAKED, -stake)]
        if cash_part:
            legs.append((PLAYER_BALANCE, cash_part))
        if bonus_part:
            legs.append((BONUS_REVENUE, bonus_part))
        return self.post(
            key,
            "bet_settled_push",
            legs,
            {"player": player, "stake": stake, "bonus_part": bonus_part},
        )

    def net(self, key: str, player: str, amount: int, reason: str) -> Posting:
        return self.post(
            key,
            "adjustment",
            [(PLAYER_BALANCE, amount), (ADJUSTMENT, -amount)],
            {"player": player, "reason": reason},
        )

    def ggr(self) -> int:
        return self.balance(GGR_REVENUE)

    def turnover(self) -> int:
        return sum(p.metadata.get("stake", 0) for p in self.postings if p.kind == "bet_placed")
