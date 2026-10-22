"""SQL-backed device allowlist. Updates never recreate a revoked row."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager

from sqlalchemy import delete, select, text, update

from demo.models import PlayerDevice
from demo.player_session import SessionRegistry


class DatabaseSessionRegistry(SessionRegistry):
    def __init__(self, factory, *, max_per_player=20, touch_seconds=600):
        self.factory = factory
        self.max_per_player = max(1, int(max_per_player))
        self.touch_seconds = max(0, int(touch_seconds))

    @staticmethod
    def _view(row):
        return {"id": row.session_id, **{
            key: getattr(row, key) for key in (
                "player", "epoch", "created", "seen", "expires", "remember",
                "user_agent", "ip")}}

    @contextmanager
    def _player_write(self, player):
        with self.factory.begin() as db:
            if db.get_bind().dialect.name == "postgresql":
                # A player with zero rows still needs a lock at first login.
                key = int.from_bytes(hashlib.sha256(
                    ("operator.devices:" + player).encode()).digest()[:8],
                    "big", signed=True)
                db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
            elif db.get_bind().dialect.name == "sqlite":
                db.execute(text("BEGIN IMMEDIATE"))
            yield db

    def record(self, session, *, user_agent="", ip="", now=None):
        instant = self._instant(now)
        row = PlayerDevice(
            session_id=session.session_id, player=session.player_id,
            epoch=session.epoch, created=session.issued_at, seen=instant,
            expires=session.expires_at, remember=session.remember,
            user_agent=str(user_agent or "")[:200], ip=str(ip or "")[:64])
        with self._player_write(session.player_id) as db:
            db.execute(delete(PlayerDevice).where(
                PlayerDevice.player == session.player_id,
                PlayerDevice.expires <= instant))
            mine = list(db.scalars(select(PlayerDevice).where(
                PlayerDevice.player == session.player_id).order_by(
                    PlayerDevice.created, PlayerDevice.session_id)))
            for old in mine[:max(0, len(mine) - self.max_per_player + 1)]:
                db.delete(old)
            db.add(row)
        return self._view(row)

    def lookup(self, session_id, *, now=None):
        instant = self._instant(now)
        with self.factory() as db:
            row = db.get(PlayerDevice, str(session_id or ""))
            return self._view(row) if row and row.expires > instant else None

    def touch(self, session, now=None):
        instant = self._instant(now)
        conditions = (
            PlayerDevice.session_id == session.session_id,
            PlayerDevice.player == session.player_id,
            PlayerDevice.epoch == session.epoch,
            PlayerDevice.expires == session.expires_at,
            PlayerDevice.expires > instant,
        )
        with self.factory() as db:
            row = db.scalar(select(PlayerDevice).where(*conditions))
            if row is None:
                return False
            if instant - row.seen < self.touch_seconds:
                return True
            changed = db.execute(update(PlayerDevice).where(
                *conditions, PlayerDevice.seen <= instant - self.touch_seconds
            ).values(seen=instant)).rowcount
            if not changed:
                # Another request may have touched it, or logout deleted it.
                alive = db.scalar(select(PlayerDevice.session_id).where(*conditions))
                db.commit()
                return alive is not None
            db.commit()
            return True

    def active(self, player_id, *, now=None):
        instant = self._instant(now)
        with self._player_write(player_id) as db:
            db.execute(delete(PlayerDevice).where(
                PlayerDevice.player == player_id, PlayerDevice.expires <= instant))
            return [self._view(row) for row in db.scalars(
                select(PlayerDevice).where(PlayerDevice.player == player_id)
                .order_by(PlayerDevice.created.desc(), PlayerDevice.session_id))]

    def revoke(self, player_id, session_id):
        with self._player_write(player_id) as db:
            return bool(db.execute(delete(PlayerDevice).where(
                PlayerDevice.player == player_id,
                PlayerDevice.session_id == str(session_id or ""))).rowcount)

    def revoke_others(self, player_id, keep_session_id):
        with self._player_write(player_id) as db:
            return db.execute(delete(PlayerDevice).where(
                PlayerDevice.player == player_id,
                PlayerDevice.session_id != str(keep_session_id or ""))).rowcount

    def revoke_player(self, player_id):
        with self._player_write(player_id) as db:
            return db.execute(delete(PlayerDevice).where(
                PlayerDevice.player == player_id)).rowcount

    def prune(self, *, now=None):
        with self.factory.begin() as db:
            return db.execute(delete(PlayerDevice).where(
                PlayerDevice.expires <= self._instant(now))).rowcount
