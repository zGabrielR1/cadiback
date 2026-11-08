"""Share the wallet's transaction with related stores on the current thread."""
from contextlib import contextmanager
import threading

_local = threading.local()


def current(factory):
    return getattr(_local, 'sessions', {}).get(id(factory))


def bind(factory, session):
    if not hasattr(_local, 'sessions'):
        _local.sessions = {}
    _local.sessions[id(factory)] = session


def unbind(factory):
    _local.sessions.pop(id(factory), None)


@contextmanager
def session_scope(factory, write=False):
    active = current(factory)
    if active is not None:
        yield active
    else:
        with (factory.begin() if write else factory()) as session:
            yield session
