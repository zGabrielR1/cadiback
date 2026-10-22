"""Postgres seam (decision 0049). Engine + sessions, wall-e's shape.

`DATABASE_URL` set to a `postgresql…` URL means Postgres (Supabase in prod).
Anything else — unset, empty, or a `sqlite…` URL — means the caller keeps
files; this module never decides the fallback, it only reports what is
configured. Dev and the test suite run the same models on a scratch SQLite
file, so the seam is provable with no credentials and no network.
"""
from __future__ import annotations

import os

from foundry.envfile import load_env, read_env_file

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPABASE_ENV_FILE = os.path.join(_REPO_ROOT, ".env.supabase")
LOCAL_ENV_FILE = os.path.join(_REPO_ROOT, ".env.local")


def db_env(env_file: str = SUPABASE_ENV_FILE, environ=None) -> dict[str, str]:
    """The database settings: the file, then the real environment on top.

    Same shape as `mail_env`/`turnstile_env` in server.py: `.env.supabase`
    holds the Supabase URL/keys plus `DATABASE_URL`, and an exported variable
    always wins — which is how the deploy supplies them without a file.
    """
    values = {}
    if env_file == SUPABASE_ENV_FILE:
        values.update(read_env_file(os.path.join(
            os.path.dirname(env_file), "envs", os.path.basename(env_file))))
    values.update(load_env(env_file, {}))
    if env_file == SUPABASE_ENV_FILE:
        values.update(read_env_file(os.path.join(
            os.path.dirname(LOCAL_ENV_FILE), "envs", os.path.basename(LOCAL_ENV_FILE))))
        values.update(read_env_file(LOCAL_ENV_FILE))
    values.update(os.environ if environ is None else environ)
    return values


def database_url(env: dict[str, str] | None = None) -> str:
    """The SQLAlchemy URL, or "" when the backend should keep files."""
    source = env if env is not None else db_env()
    return (source.get("DATABASE_URL") or "").strip()


def using_postgres(env: dict[str, str] | None = None) -> bool:
    """True only for a real Postgres URL. SQLite stays a dev/test explicit."""
    url = database_url(env)
    return url.startswith("postgresql") or url.startswith("postgres")


def make_engine(db_url: str):
    """One engine. Same signatures as wall-e's `db.py`, deliberately."""
    from sqlalchemy import create_engine

    if db_url.startswith("postgres://"):
        db_url = "postgresql+psycopg://" + db_url[len("postgres://"):]
    elif db_url.startswith("postgresql://"):
        db_url = "postgresql+psycopg://" + db_url[len("postgresql://"):]
    connect_args = ({"check_same_thread": False} if db_url.startswith("sqlite")
                    else {"connect_timeout": 10})
    return create_engine(db_url, connect_args=connect_args,
                         pool_pre_ping=True, future=True)


def make_session_factory(engine):
    """Sessions that do not expire objects on commit (read-after-write)."""
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False,
                        future=True)
