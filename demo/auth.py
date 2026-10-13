"""Painel administrativo credentials & sessions. Stdlib only. DEMO.

Default operator account ``admin``/``admin`` is seeded on first boot —
the owner asked for it and said they will change it later. Passwords are
stored salted + SHA-256 and compared in constant time; the users file
never carries plaintext.

Sessions are bearer tokens with a TTL that persist to disk, so a server
restart does not forcibly log out every panel user — only sessions whose
TTL the boot sweep considers expired are silently dropped.

Two roles: ``admin`` sees the dashboard AND manages credentials;
``viewer`` sees the dashboard only. Every refusal carries a message safe
to show the client.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone

SESSION_TTL_HOURS = 12
MIN_PASSWORD_LEN = 4
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,32}$")
ROLES = ("admin", "viewer")


class AuthError(RuntimeError):
    """Authorization refusal with a message safe to show the client."""


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256(
        (salt + "\x00" + password).encode("utf-8")
    ).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserStore:
    """JSON file of {username: {salt, hash, role, created_at, updated_at}}.

    Writes are atomic (tmp + replace) and every mutation happens under
    one lock, so two admin requests cannot interleave a read-modify-write
    and lose each other's change.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.lock = threading.Lock()
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        data = self._read()
        if not any(
            isinstance(u, dict) and u.get("role") == "admin"
            for u in data.values()
        ):
            # first boot (or the last admin was removed): seed the
            # default operator account the owner asked for
            data["admin"] = self._record("admin", "admin")
            self._write(data)

    # -- storage -----------------------------------------------------
    def _read(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False,
                      sort_keys=True, indent=2)
        os.replace(tmp, self.path)

    def _record(self, password: str, role: str) -> dict:
        now = _now().isoformat(timespec="seconds")
        salt = secrets.token_hex(16)
        return {"salt": salt, "hash": _hash(password, salt),
                "role": role, "created_at": now, "updated_at": now}

    @staticmethod
    def _check_password(password: str) -> str:
        password = str(password or "")
        if len(password) < MIN_PASSWORD_LEN:
            raise AuthError(
                f"a senha precisa de ao menos {MIN_PASSWORD_LEN} caracteres")
        return password

    @staticmethod
    def public_user(username: str, record: dict) -> dict:
        """What the API may expose: no salt, no hash, ever."""
        return {
            "username": username,
            "role": str(record.get("role", "viewer")),
            "created_at": str(record.get("created_at", "")),
            "updated_at": str(record.get("updated_at", "")),
        }

    # -- auth --------------------------------------------------------
    def authenticate(self, username: str, password: str) -> str:
        """Return the role, or raise AuthError. Unknown user and wrong
        password are the same message, and an unknown user still burns a
        comparable hash so the two cannot be told apart by timing."""
        username = str(username or "").strip().lower()
        password = str(password or "")
        with self.lock:
            data = self._read()
            record = data.get(username)
            if not isinstance(record, dict):
                _hash(password, "0" * 32)
                raise AuthError("usuário ou senha inválidos")
            if not hmac.compare_digest(
                _hash(password, str(record.get("salt", ""))),
                str(record.get("hash", "")),
            ):
                raise AuthError("usuário ou senha inválidos")
            role = str(record.get("role", "viewer"))
        if role not in ROLES:
            raise AuthError("usuário ou senha inválidos")
        return role

    # -- credential management (admin) -------------------------------
    def create(self, username: str, password: str, role: str) -> dict:
        username = str(username or "").strip().lower()
        if not USERNAME_RE.match(username):
            raise AuthError("usuário: 3-32 caracteres (a-z, 0-9, . _ -)")
        if role not in ROLES:
            raise AuthError("papel inválido (admin ou viewer)")
        password = self._check_password(password)
        with self.lock:
            data = self._read()
            if username in data:
                raise AuthError("usuário já existe")
            record = self._record(password, role)
            data[username] = record
            self._write(data)
        return self.public_user(username, record)

    def set_password(self, username: str, password: str) -> None:
        username = str(username or "").strip().lower()
        password = self._check_password(password)
        now = _now().isoformat(timespec="seconds")
        with self.lock:
            data = self._read()
            record = data.get(username)
            if not isinstance(record, dict):
                raise AuthError("usuário não existe")
            salt = secrets.token_hex(16)
            record["salt"] = salt
            record["hash"] = _hash(password, salt)
            record["updated_at"] = now
            self._write(data)

    def delete(self, username: str, by: str) -> None:
        username = str(username or "").strip().lower()
        with self.lock:
            data = self._read()
            if username not in data:
                raise AuthError("usuário não existe")
            if username == str(by or "").strip().lower():
                raise AuthError("não é possível remover o próprio usuário")
            admins = sum(
                1 for u in data.values()
                if isinstance(u, dict) and u.get("role") == "admin"
            )
            if data[username].get("role") == "admin" and admins <= 1:
                raise AuthError("não é possível remover o último administrador")
            del data[username]
            self._write(data)

    def list_users(self) -> list[dict]:
        with self.lock:
            data = self._read()
        return sorted(
            (self.public_user(name, rec) for name, rec in data.items()
             if isinstance(rec, dict)),
            key=lambda u: (u["role"] != "admin", u["username"]),
        )


class SessionBook:
    """In-memory bearer tokens with a TTL, persisted via SessionStore."""

    def __init__(self, ttl_hours: int = SESSION_TTL_HOURS) -> None:
        self.ttl = timedelta(hours=ttl_hours)
        self._lock = threading.Lock()
        self._sessions: dict[str, dict] = {}

    def _sweep(self, now: datetime) -> None:
        expired = []
        for token, session in self._sessions.items():
            try:
                ends = datetime.fromisoformat(session["expires_at"])
            except (KeyError, TypeError, ValueError):
                expired.append(token)
                continue
            if ends <= now:
                expired.append(token)
        for token in expired:
            self._sessions.pop(token, None)

    def issue(self, username: str, role: str) -> str:
        token = secrets.token_urlsafe(24)
        now = _now()
        with self._lock:
            self._sweep(now)
            self._sessions[token] = {
                "username": username,
                "role": role,
                "issued_at": now.isoformat(timespec="seconds"),
                "expires_at": (now + self.ttl).isoformat(timespec="seconds"),
            }
        return token

    def check(self, token: str) -> dict:
        token = str(token or "")
        if not token:
            raise AuthError("autenticação necessária")
        now = _now()
        with self._lock:
            self._sweep(now)
            session = self._sessions.get(token)
            if session is None:
                raise AuthError("sessão inválida ou expirada")
            return dict(session)

    def revoke(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(str(token or ""), None)

    def revoke_user(self, username: str) -> None:
        """A password change must kill every live session for that user —
        otherwise the old credential keeps working until the TTL.

        The demo persists session state to disk (SessionStore), so callers that
        mutate the session book — password change, admin reset, admin delete —
        should call Demo._save_sessions() after revoking, otherwise the next
        boot would resurrect the just-revoked token from the stale file.
        """
        username = str(username or "")
        with self._lock:
            stale = [t for t, s in self._sessions.items()
                     if s.get("username") == username]
            for token in stale:
                self._sessions.pop(token, None)


class SessionStore:
    """Lightweight JSON persistence for SessionBook. Kept separate from
    SessionBook itself so the in-memory book stays a pure map of
    token -> session and can be rebuilt from disk on boot without
    the persist layer knowing anything about TTLs or issuance.

    Stored as {token: {username, role, issued_at, expires_at}}.
    Anything whose expires_at is in the past at boot is silently dropped.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.lock = threading.Lock()
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    def load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        now = _now()
        out: dict[str, dict] = {}
        for token, session in data.items():
            if not isinstance(session, dict):
                continue
            try:
                ends = datetime.fromisoformat(
                    str(session.get("expires_at", "")))
            except (ValueError, TypeError):
                continue
            if ends <= now:
                continue
            out[str(token)] = {
                "username": str(session.get("username", "")),
                "role": str(session.get("role", "viewer")),
                "issued_at": str(session.get("issued_at", "")),
                "expires_at": str(session.get("expires_at", "")),
            }
        return out

    def save(self, sessions: dict) -> None:
        with self.lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(sessions, handle, ensure_ascii=False,
                              sort_keys=True, indent=2)
            os.replace(tmp, self.path)
