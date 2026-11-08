"""Serialize durable crash state with its wallet transaction."""
from contextlib import contextmanager
from copy import deepcopy


@contextmanager
def crash_operation(demo):
    with demo._crash_lock:
        if demo.crash_store is None:
            original = deepcopy(demo.crash_pending)
            yield
            if demo.crash_pending != original:
                demo._save_crash_pending()
            return
        original = deepcopy(demo.crash_pending)
        try:
            # The wallet document is the common cross-process lock. Refresh
            # pending rounds only after acquiring it, then commit pending state,
            # postings, promotions and round history in the same transaction.
            with demo.books.lock:
                demo.crash_pending = dict(demo.crash_store.read_all())
                original = deepcopy(demo.crash_pending)
                yield
                if demo.crash_pending != original:
                    demo._save_crash_pending()
        except BaseException:
            # Also runs when commit fails after the operation returned.
            demo.crash_pending = original
            raise
