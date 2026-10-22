"""Durable identity snapshots with optimistic concurrency (decision 0071).

Only used with an explicitly injected SQLAlchemy session factory. Local files
are never imported implicitly: stale files must not resurrect a deleted account
or a revoked token. The separate import command performs the one-time cutover.
"""
from __future__ import annotations

from copy import deepcopy

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from demo.models import IdentityDocument


class IdentityConflict(ValueError):
    def __init__(self):
        super().__init__("a conta mudou em outra solicitação; tente novamente")


class Snapshot(dict):
    def __init__(self, data, revision):
        super().__init__(deepcopy(data))
        self.revision = revision


class IdentityStore:
    """Same read_all/write_all surface as Store, with stale-write rejection.

    Each document has one revision; replacing a stale snapshot fails rather
    than erasing another request's change. This deliberately favors integrity
    over concurrent account-edit throughput for this single-instance platform.
    """

    def __init__(self, factory, name: str, path: str):
        self.factory, self.name, self.path = factory, name, path

    def read_all(self):
        with self.factory() as db:
            row = db.get(IdentityDocument, self.name)
            return Snapshot(row.data if row else {}, row.revision if row else None)

    def write_all(self, data):
        if not isinstance(data, Snapshot):
            raise ValueError("identity writes require a freshly read snapshot")
        revision = data.revision
        try:
            with self.factory.begin() as db:
                if revision is None:
                    db.add(IdentityDocument(name=self.name, data=dict(data), revision=0))
                else:
                    changed = db.execute(update(IdentityDocument).where(
                        IdentityDocument.name == self.name,
                        IdentityDocument.revision == revision,
                    ).values(data=dict(data), revision=revision + 1)).rowcount
                    if changed != 1:
                        raise IdentityConflict()
        except IntegrityError:
            raise IdentityConflict() from None
        data.revision = 0 if revision is None else revision + 1
