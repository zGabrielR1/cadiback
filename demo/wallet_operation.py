"""Keep a durable operation's postings and receipt in one transaction."""
from functools import wraps


def durable_wallet_operation(operation):
    @wraps(operation)
    def run(self, *args, **kwargs):
        if self.round_log is None:
            return operation(self, *args, **kwargs)
        with self.books.lock:
            return operation(self, *args, **kwargs)
    return run
