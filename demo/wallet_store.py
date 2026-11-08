"""Durable hobby-scale wallet snapshots on the existing identity table.

One locked document serializes balance checks and postings across processes.
The frame's posting rules remain the implementation; files are never imported
implicitly. SQLite uses BEGIN IMMEDIATE for the same semantics in tests.
"""
from copy import deepcopy
import json
from pathlib import Path
import threading

from sqlalchemy import select, text

from demo.models import IdentityDocument
from demo import db_context
from frame.wallet.books import Books, Posting
from demo.wallet_snapshot import validate_postings


class DocumentLock:
    def __init__(self, factory, name, initial, load=None):
        self.factory, self.name, self.initial, self.load = factory, name, initial, load
        self.mutex = threading.RLock()
        self.local = threading.local()

    @property
    def active(self):
        return getattr(self.local, "depth", 0) > 0

    @property
    def row(self):
        return self.local.row

    def __enter__(self):
        self.mutex.acquire()
        if self.active:
            self.local.depth += 1
            return self
        active = db_context.current(self.factory)
        self.local.owns = active is None
        db = active if active is not None else self.factory()
        self.local.db = db
        try:
            dialect = db.get_bind().dialect.name
            if dialect == "sqlite":
                if self.local.owns:
                    db.execute(text("BEGIN IMMEDIATE"))
                from sqlalchemy.dialects.sqlite import insert
            else:
                from sqlalchemy.dialects.postgresql import insert
            db.execute(insert(IdentityDocument).values(
                name=self.name, data=deepcopy(self.initial), revision=0
            ).on_conflict_do_nothing(index_elements=["name"]))
            row = db.scalar(select(IdentityDocument).where(
                IdentityDocument.name == self.name).with_for_update())
            self.local.row = row
            self.local.original = deepcopy(row.data)
            self.local.depth = 1
            if self.local.owns:
                db_context.bind(self.factory, db)
            if self.load:
                self.load(row.data)
            return self
        except BaseException:
            self.local.depth = 0
            if self.local.owns:
                db_context.unbind(self.factory)
                db.rollback()
                db.close()
            self.mutex.release()
            raise

    def __exit__(self, kind, value, traceback):
        self.local.depth -= 1
        try:
            if self.local.depth:
                return False
            db = self.local.db
            try:
                if kind:
                    if self.local.owns:
                        db.rollback()
                    if self.load:
                        self.load(self.local.original)
                elif self.local.owns:
                    db.commit()
            except BaseException:
                if self.local.owns:
                    db.rollback()
                if self.load:
                    self.load(self.local.original)
                raise
            finally:
                if self.local.owns:
                    db_context.unbind(self.factory)
                    db.close()
        finally:
            self.mutex.release()
        return False


class DatabaseBooks(Books):
    @property
    def postings(self):
        lock = getattr(self, "_lock", None)
        if isinstance(lock, DocumentLock) and not lock.active:
            with lock:
                return self._postings
        return self._postings

    @postings.setter
    def postings(self, value):
        self._postings = value

    @property
    def total(self):
        with self._lock:
            return sum(self.balances.values())

    def __init__(self, factory, path):
        super().__init__("")
        self.path = path  # diagnostic compatibility; never the source of truth
        with factory() as db:
            exists = db.get(IdentityDocument, "runtime:books") is not None
        if not exists and Path(path).exists() and Path(path).read_text().strip():
            raise ValueError("wallet files require an explicit validated import")
        self._lock = DocumentLock(factory, "runtime:books", {"postings": []}, self._load)
        with self._lock:
            pass

    def _load(self, data):
        rows = validate_postings(data.get("postings"))
        self.postings, self.balances, self.player_balances, self._keys = [], {}, {}, set()
        for raw in rows:
            posting = Posting(key=raw["key"], kind=raw["kind"], metadata=deepcopy(raw["metadata"]),
                              seq=raw["seq"], ts=raw["ts"],
                              legs=tuple((leg["account"], leg["amount"]) for leg in raw["legs"]))
            self._postings.append(posting)
            self._keys.add(posting.key)
            for account, amount in posting.legs:
                self.balances[account] = self.balances.get(account, 0) + amount
            self._apply_player(posting)

    def _write(self, posting):
        self._lock.row.data = {"postings": [p.as_dict() for p in self.postings] + [posting.as_dict()]}
        self._lock.row.revision += 1
        self._lock.local.db.flush()

    def available(self, player):
        with self._lock:
            return super().available(player)

    def bonus_available(self, player):
        with self._lock:
            return super().bonus_available(player)

    def balance(self, account):
        with self._lock:
            return super().balance(account)

    def snapshot(self):
        with self._lock:
            self.assert_balanced()
            return deepcopy(self._lock.row.data)


class DatabaseLog:
    def __init__(self, factory, name):
        self.lock = DocumentLock(factory, "runtime:" + name, {"rows": []})

    def read(self):
        with self.lock:
            return deepcopy(self.lock.row.data["rows"])

    def append(self, row):
        # A round retry must not erase the pending/settled pair, so only an
        # identical complete record is deduplicated.
        with self.lock:
            rows = self.lock.row.data["rows"]
            if row not in rows:
                self.lock.row.data = {"rows": rows + [deepcopy(row)]}
                self.lock.row.revision += 1
