from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Game:
    game_id: str
    provider: str
    title: str
    rtp: str
    volatility: str
    max_payline: int


@dataclass(frozen=True)
class RoundResult:
    round_id: str
    session_id: str
    game_id: str
    stake_minor: int
    payout_minor: int
    rng_outcome: str


class CasinoError(RuntimeError):
    pass


class CasinoAggregator(Protocol):
    def catalogue(self) -> list[Game]: ...
    def launch(self, player_id: str, game_id: str, locale: str, currency: str) -> str: ...
    def bet(self, session_id: str, round_id: str, stake_minor: int) -> RoundResult: ...
    def round_history(self, session_id: str, limit: int) -> list[RoundResult]: ...
    def wallet_credit(self, round_id: str, amount_minor: int) -> bool: ...


@dataclass
class CasinoStub:
    """Deterministic aggregator double. Reproduces the certification gate, not the fun."""

    games: list[Game] = field(
        default_factory=lambda: [
            # Row-level provenance (verified 2026-10-01, probes/vendor-catalog.json):
            # - Gates of Olympus: title confirmed on pragmaticplay.com/en/games/;
            #   RTP corrected 96.50 -> 96.51 per the official game page
            #   (.../games/gates-of-olympus-2500/, "Basic Game Info"). Volatility
            #   and max_payline below are fixture SHAPE, not provider facts.
            Game("pp:gates-of-olympus", "pragmatic_play", "Gates of Olympus", "96.51", "high", 20000),
            # - PG Soft 888: UNVERIFIED. pgsoft.com serves a Nuxt shell; the title
            #   list hydrates client-side, so no figure here is provider-confirmed.
            Game("pg:pgsoft-888", "pg_soft", "PG Soft 888", "96.00", "medium", 1000),
            # - Lightning Roulette: UNVERIFIED. evolution.com timed out twice from
            #   this host (bot-block or edge refusal); 97.00 is fixture shape.
            Game("ev:lightning-roulette", "evolution", "Lightning Roulette", "97.00", "low", 1),
        ]
    )
    certified: set[str] = field(default_factory=lambda: {"pp:gates-of-olympus", "pg:pgsoft-888"})
    sessions: dict[str, str] = field(default_factory=dict)
    rounds: dict[str, RoundResult] = field(default_factory=dict)
    credits: dict[str, int] = field(default_factory=dict)

    def catalogue(self) -> list[Game]:
        return list(self.games)

    def launch(self, player_id: str, game_id: str, locale: str, currency: str) -> str:
        known = {g.game_id for g in self.games}
        if game_id not in known:
            raise CasinoError(f"unknown game: {game_id}")
        if game_id not in self.certified:
            raise CasinoError(f"game {game_id} is not certified for launch")
        if currency != "BRL":
            raise CasinoError(f"currency {currency} not permitted")
        session_id = f"sess:{player_id}:{game_id}"
        self.sessions[session_id] = game_id
        return session_id

    def bet(self, session_id: str, round_id: str, stake_minor: int) -> RoundResult:
        if session_id not in self.sessions:
            raise CasinoError(f"unknown session: {session_id}")
        if round_id in self.rounds:
            raise CasinoError(f"round already settled: {round_id}")
        if stake_minor <= 0:
            raise CasinoError("stake must be positive")
        result = RoundResult(
            round_id=round_id,
            session_id=session_id,
            game_id=self.sessions[session_id],
            stake_minor=stake_minor,
            payout_minor=0,
            rng_outcome="stub",
        )
        self.rounds[round_id] = result
        return result

    def round_history(self, session_id: str, limit: int) -> list[RoundResult]:
        rows = [r for r in self.rounds.values() if r.session_id == session_id]
        return rows[-limit:] if limit > 0 else []

    def wallet_credit(self, round_id: str, amount_minor: int) -> bool:
        if round_id not in self.rounds:
            raise CasinoError(f"unknown round: {round_id}")
        if round_id in self.credits:
            return False
        self.credits[round_id] = amount_minor
        return True
