"""Postgres models (decision 0049). One model per migration table.

This file and `supabase/migrations/20261015000000_operator_schema.sql` describe
the same fourteen tables; `DbSeamTest` fails if they drift apart (every model
table must appear as a CREATE TABLE in the migration). Column rules:

  * ids stay TEXT in their current shapes — no UUID migration;
  * money is BigInteger minor units — no floats near the ledger;
  * `JSON` renders JSONB on Postgres and TEXT-backed JSON on SQLite, so the
    suite runs on a scratch file with no credentials;
  * `books_postings.key` is the primary key: a retried POST becomes a
    constraint conflict, never a second posting.
"""
from __future__ import annotations

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, ForeignKey,
                        Integer, Sequence, func)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# Surrogate keys: BIGSERIAL on Postgres (64-bit, correct long-term), INTEGER
# on SQLite (its rowid alias — BIGINT primary keys do not auto-assign there,
# so create_all + autoincrement would insert NULL). Money columns stay
# BigInteger everywhere; only these ids use the variant.
SurrogateKey = BigInteger().with_variant(Integer(), "sqlite")


class Player(Base):
    __tablename__ = "players"

    player_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    email: Mapped[str] = mapped_column(unique=True)
    cpf_masked: Mapped[str] = mapped_column(default="")
    pw_hash: Mapped[str] = mapped_column()
    pw_salt: Mapped[str] = mapped_column()
    pix_kind: Mapped[str] = mapped_column(default="")
    pix_masked: Mapped[str] = mapped_column(default="")
    pix_raw: Mapped[str] = mapped_column(default="")
    bank: Mapped[dict] = mapped_column(JSON, default=dict)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(primary_key=True)
    pw_hash: Mapped[str] = mapped_column()
    pw_salt: Mapped[str] = mapped_column()
    role: Mapped[str] = mapped_column(default="viewer")


class Session(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(ForeignKey("users.username"))
    role: Mapped[str] = mapped_column(default="viewer")
    issued_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True))


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[object] = mapped_column(JSON)


class Promo(Base):
    __tablename__ = "promos"

    player_id: Mapped[str] = mapped_column(
        ForeignKey("players.player_id"), primary_key=True)
    state: Mapped[dict] = mapped_column(JSON, default=dict)


class Play(Base):
    __tablename__ = "plays"

    id: Mapped[int] = mapped_column(SurrogateKey, primary_key=True,
                                    autoincrement=True)
    game_id: Mapped[str] = mapped_column()
    player: Mapped[str] = mapped_column(default="")
    ts: Mapped[object] = mapped_column(DateTime(timezone=True),
                                       server_default=func.now())


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(SurrogateKey, primary_key=True,
                                    autoincrement=True)
    round_id: Mapped[str] = mapped_column(index=True)
    player: Mapped[str] = mapped_column()
    game_id: Mapped[str] = mapped_column()
    stake_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    payout_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    tier: Mapped[str] = mapped_column(default="")
    type: Mapped[str] = mapped_column(default="")
    ts: Mapped[object] = mapped_column(DateTime(timezone=True),
                                       server_default=func.now())


class BooksPosting(Base):
    __tablename__ = "books_postings"

    key: Mapped[str] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column()
    legs: Mapped[list] = mapped_column(JSON)
    seq: Mapped[int] = mapped_column(
        SurrogateKey,
        Sequence("books_postings_seq_seq", optional=True),
        unique=True)
    ts: Mapped[object] = mapped_column(DateTime(timezone=True),
                                       server_default=func.now())


class CrashPending(Base):
    __tablename__ = "crash_pending"

    token: Mapped[str] = mapped_column(primary_key=True)
    round_id: Mapped[str] = mapped_column()
    player: Mapped[str] = mapped_column()
    stake_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    bonus_part: Mapped[int] = mapped_column(BigInteger, default=0)
    started_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class AsaasCharge(Base):
    __tablename__ = "asaas_charges"

    deposit_id: Mapped[str] = mapped_column(primary_key=True)
    player: Mapped[str] = mapped_column()
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    provider_ref: Mapped[str] = mapped_column(default="")
    provider_status: Mapped[str] = mapped_column(default="")
    qr_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    posted: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_at: Mapped[object] = mapped_column(DateTime(timezone=True),
                                            nullable=True)


class Exclusion(Base):
    __tablename__ = "exclusions"

    player: Mapped[str] = mapped_column(primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class SchedReceipt(Base):
    __tablename__ = "sched_receipts"

    id: Mapped[int] = mapped_column(SurrogateKey, primary_key=True,
                                    autoincrement=True)
    ts: Mapped[object] = mapped_column(DateTime(timezone=True),
                                       server_default=func.now())
    tier: Mapped[str] = mapped_column(default="")
    screened: Mapped[int] = mapped_column(default=0)
    passed: Mapped[int] = mapped_column(default=0)
    notified: Mapped[int] = mapped_column(default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)


class SchedCounter(Base):
    __tablename__ = "sched_counters"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[object] = mapped_column(JSON)


class LedgerEntry(Base):
    __tablename__ = "ledger"

    id: Mapped[int] = mapped_column(SurrogateKey, primary_key=True,
                                    autoincrement=True)
    prev_hash: Mapped[str] = mapped_column(default="")
    hash: Mapped[str] = mapped_column()
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    ts: Mapped[object] = mapped_column(DateTime(timezone=True),
                                       server_default=func.now())
