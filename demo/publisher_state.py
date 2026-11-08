"""Portable publisher state and wallet-transaction orchestration."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import wraps
import time

FIELDS = ('wallet_tokens', 'rgs_sessions', 'rgs_rounds', 'pragmatic_books')

# Publisher bearer tokens are bearer sessions for adjacent wallet movement.
# Wallet launch must explicitly refresh in-game; unresolved rows are evicted
# after this horizon instead of replaying for weeks.
PUBLISHER_TOKEN_TTL_SECONDS = 24 * 60 * 60


def _parse_instant(value):
    try:
        instant = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return instant if instant.tzinfo is not None else instant.replace(tzinfo=timezone.utc)


def token_expired(row, *, now=None, ttl_seconds=PUBLISHER_TOKEN_TTL_SECONDS):
    issued_at = _parse_instant(row.get('issued_at') if isinstance(row, dict) else None)
    if issued_at is None:
        return True
    instant = now if now is not None else datetime.now(timezone.utc)
    if isinstance(instant, (int, float)):
        instant = datetime.fromtimestamp(instant, tz=timezone.utc)
    return instant - issued_at >= timedelta(seconds=ttl_seconds)


def cleanup_state(tokens, sessions, rounds, pragmatic, *, now=None, ttl_seconds=PUBLISHER_TOKEN_TTL_SECONDS):
    """Drop expired tokens and orphaned sessions/rounds; returns the pruned copy."""
    preserved = []
    for token, row in (tokens or {}).items():
        if isinstance(row, dict) and not token_expired(row, now=now, ttl_seconds=ttl_seconds):
            preserved.append(token)
    live = set(preserved)
    live_sessions = {key: value for key, value in (sessions or {}).items() if value in live}
    live_rounds = {key: deepcopy(value) for key, value in (rounds or {}).items() if key in live_sessions}
    return {
        'tokens': {token: deepcopy(tokens[token]) for token in preserved},
        'sessions': live_sessions,
        'rounds': live_rounds,
        'pragmatic': deepcopy(pragmatic or {}),
    }


def prune_expired(demo, *, now=None, ttl_seconds=PUBLISHER_TOKEN_TTL_SECONDS):
    """Evict expired tokens and their bindings/rounds in place.

    Only top-level keys are popped: inner records keep their identity, so a
    caller holding e.g. the Pragmatic baseline dict across nested publisher
    calls cannot lose in-flight updates such as the sequence counter.
    Returns the counts evicted.
    """
    expired = {token for token, row in (demo.wallet_tokens or {}).items()
               if not isinstance(row, dict) or token_expired(row, now=now, ttl_seconds=ttl_seconds)}
    for token in expired:
        demo.wallet_tokens.pop(token, None)
        demo.pragmatic_books.pop(token, None)
    for key in list(demo.rgs_sessions):
        if demo.rgs_sessions[key] in expired:
            demo.rgs_sessions.pop(key, None)
    for key in list(demo.rgs_rounds):
        if key not in demo.rgs_sessions:
            demo.rgs_rounds.pop(key, None)
    return len(expired)


def decode_state(data):
    if not isinstance(data, dict) or set(data) - {'tokens', 'sessions', 'rounds', 'pragmatic'}:
        raise ValueError('invalid publisher state')
    tokens, pragmatic = data.get('tokens', {}), data.get('pragmatic', {})
    if not isinstance(tokens, dict) or not isinstance(pragmatic, dict):
        raise ValueError('invalid publisher mappings')
    for token, row in tokens.items():
        if not isinstance(token, str) or not token or not isinstance(row, dict) or any(
                not isinstance(row.get(name), str) or not row[name]
                for name in ('player', 'game_id', 'issued_at')):
            raise ValueError('invalid publisher token')
    for token, row in pragmatic.items():
        if not isinstance(token, str) or not token or not isinstance(row, dict) or any(
                type(row.get(name)) is not int or row[name] < 0 for name in ('stake', 'seq')) \
                or (row.get('last') is not None and type(row['last']) is not int):
            raise ValueError('invalid publisher balance state')
    decoded = []
    for name in ('sessions', 'rounds'):
        rows = data.get(name, [])
        if not isinstance(rows, list):
            raise ValueError('invalid publisher session list')
        result = {}
        for row in rows:
            if not isinstance(row, dict) or any(
                    not isinstance(row.get(key), str) or not row[key] for key in ('provider', 'session')):
                raise ValueError('invalid publisher session identity')
            key = (row['provider'], row['session'])
            if key in result:
                raise ValueError('duplicate publisher session')
            if name == 'sessions':
                if not isinstance(row.get('token'), str) or not row['token']:
                    raise ValueError('invalid publisher binding')
                result[key] = row['token']
            else:
                if any(type(row.get(field)) is not int or row[field] < 0 for field in ('stake', 'win')):
                    raise ValueError('invalid publisher round')
                result[key] = {'stake': row['stake'], 'win': row['win']}
        decoded.append(result)
    return deepcopy((tokens, *decoded, pragmatic))


def encode_state(demo):
    data = {
        'tokens': deepcopy(demo.wallet_tokens),
        'sessions': [{'provider': p, 'session': s, 'token': token}
                     for (p, s), token in sorted(demo.rgs_sessions.items())],
        'rounds': [{'provider': p, 'session': s, **row}
                   for (p, s), row in sorted(demo.rgs_rounds.items())],
        'pragmatic': deepcopy(demo.pragmatic_books),
    }
    decode_state(data)
    return data


@contextmanager
def publisher_operation(demo):
    # Publisher entry points take this lock before the wallet transaction.
    # wallet_credit has the publisher wrapper outside its wallet wrapper.
    with demo._publisher_lock:
        if demo._publisher_depth:
            yield
            return
        original = tuple(deepcopy(getattr(demo, field)) for field in FIELDS)
        demo._publisher_depth = 1
        try:
            with demo.books.lock:
                snapshot = None
                if demo.publisher_store is not None:
                    snapshot = demo.publisher_store.read_all()
                    original = decode_state(snapshot)
                    for field, value in zip(FIELDS, deepcopy(original)):
                        setattr(demo, field, value)
                yield
                if snapshot is not None:
                    updated = encode_state(demo)
                    if updated != snapshot:
                        snapshot.clear()
                        snapshot.update(updated)
                        demo.publisher_store.write_all(snapshot)
        except BaseException:
            for field, value in zip(FIELDS, original):
                setattr(demo, field, value)
            raise
        finally:
            demo._publisher_depth = 0


def publisher_method(method):
    @wraps(method)
    def run(self, *args, **kwargs):
        with publisher_operation(self):
            return deepcopy(method(self, *args, **kwargs))
    return run
