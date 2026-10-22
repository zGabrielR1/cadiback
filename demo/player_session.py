"""Signed player sessions (decisions 0069, 0070). Stdlib only. DEMO.

Until 0069 a player *was* whoever the request said: every player write carried
``player: <id>`` in its body and ``/api/player?id=`` read a profile, and the id
is derived from the CPF (``player-…``), which is a semi-public document. The
password protected the login form, not the money.

A session here is a signed, stateless token:

    ps1.<base64url(payload)>.<base64url(hmac-sha256)>

The payload names the player, the row's ``session_epoch``, a session id, the
issue/expiry instants and whether "remember me" was asked for. The signature
covers the exact ``ps1.<payload>`` text with a fixed context prefix, so a token
minted by another use of the same secret — or an edited payload — is refused.

The signature is the proof; the ``SessionRegistry`` is the revocation list
(0070). A token whose session id has no live row is refused, which is what
makes "sair deste dispositivo" real without turning the token into a database
lookup: the row list is one small JSON file, read on the same pass as the
player row the host already reads. A password reset still bumps
``session_epoch`` and kills every device at once.

The clock and the token factory are injectable so the tests need neither sleep
nor a real secret.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass

VERSION = "ps1"
# Domain separation: the signature is over this prefix plus the token body.
# A secret shared with another signer cannot mint a player session.
CONTEXT = b"operator.player-session.v1\n"

TTL_SECONDS = 12 * 60 * 60            # a normal login
REMEMBER_TTL_SECONDS = 30 * 24 * 60 * 60   # "lembrar de mim"
MAX_TTL_SECONDS = 365 * 24 * 60 * 60

# A session id is public (it names a row in the list the player sees); the
# signature is what makes a token usable, so the id alone is not a credential.
MAX_SESSION_ID = 64

# A key file in the data dir, used only when no environment secret exists.
KEY_FILE = "player_session.key"


def new_session_id() -> str:
    """A fresh, unguessable row id: 16 bytes as 22 url-safe characters."""
    return secrets.token_urlsafe(16)


class PlayerSessionError(ValueError):
    """A token is missing, malformed, forged, expired or revoked."""


@dataclass(frozen=True)
class PlayerSession:
    """One verified token. ``epoch`` is checked against the player row and
    ``session_id`` against the live-session registry."""

    player_id: str
    epoch: int
    issued_at: int
    expires_at: int
    remember: bool = False
    session_id: str = ""

    def remaining(self, now: float | None = None) -> float:
        instant = time.time() if now is None else float(now)
        return max(0.0, self.expires_at - instant)


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    padded = text + "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, ValueError, UnicodeEncodeError) as exc:
        raise PlayerSessionError("token de sessão malformado") from exc


class PlayerSessions:
    """Mint and verify player tokens. The host owns the policy around them."""

    def __init__(self, secret: str, *, ttl_seconds: int = TTL_SECONDS,
                 remember_ttl_seconds: int = REMEMBER_TTL_SECONDS) -> None:
        if not isinstance(secret, str) or not secret:
            raise PlayerSessionError("player session secret is not configured")
        for name, value in (("ttl_seconds", ttl_seconds),
                            ("remember_ttl_seconds", remember_ttl_seconds)):
            if isinstance(value, bool) or not isinstance(value, int) or \
                    not 1 <= value <= MAX_TTL_SECONDS:
                raise PlayerSessionError(f"{name} is outside the supported range")
        self._secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds
        self.remember_ttl_seconds = remember_ttl_seconds

    # -- minting -----------------------------------------------------
    def issue(self, player_id: str, *, epoch: int = 0,
              remember: bool = False, now: float | None = None,
              session_id: str | None = None) -> str:
        player_id = str(player_id or "")
        if not player_id or len(player_id) > 128:
            raise PlayerSessionError("a session needs a player id")
        try:
            epoch = int(epoch)
        except (TypeError, ValueError):
            raise PlayerSessionError("session epoch must be an integer") from None
        if epoch < 0:
            raise PlayerSessionError("session epoch must not be negative")
        sid = str(session_id or new_session_id()).strip()
        if not sid or len(sid) > MAX_SESSION_ID:
            raise PlayerSessionError("a session needs a valid id")
        issued = int(time.time() if now is None else now)
        ttl = self.remember_ttl_seconds if remember else self.ttl_seconds
        payload = {
            "p": player_id,
            "e": epoch,
            "s": sid,
            "iat": issued,
            "exp": issued + ttl,
            "r": bool(remember),
        }
        body = f"{VERSION}.{_b64e(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8'))}"
        return f"{body}.{self._sign(body)}"

    def _sign(self, body: str) -> str:
        digest = hmac.new(self._secret, CONTEXT + body.encode("ascii"),
                          hashlib.sha256).digest()
        return _b64e(digest)

    # -- verification ------------------------------------------------
    def verify(self, token: str, *, now: float | None = None) -> PlayerSession:
        token = str(token or "").strip()
        if not token or len(token) > 2048 or not token.isascii():
            raise PlayerSessionError("sessão do jogador ausente")
        parts = token.split(".")
        if len(parts) != 3 or parts[0] != VERSION:
            raise PlayerSessionError("token de sessão malformado")
        body = f"{parts[0]}.{parts[1]}"
        expected = self._sign(body)
        if not hmac.compare_digest(expected, parts[2]):
            raise PlayerSessionError("assinatura de sessão inválida")
        try:
            payload = json.loads(_b64d(parts[1]).decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise PlayerSessionError("token de sessão malformado") from exc
        if not isinstance(payload, dict):
            raise PlayerSessionError("token de sessão malformado")
        player_id = payload.get("p")
        if not isinstance(player_id, str) or not player_id or len(player_id) > 128:
            raise PlayerSessionError("token de sessão malformado")
        session_id = payload.get("s")
        # a token minted before 0070 has no session id: it cannot be revoked
        # one device at a time, so it is not accepted at all (one re-login)
        if not isinstance(session_id, str) or not session_id or \
                len(session_id) > MAX_SESSION_ID:
            raise PlayerSessionError("token de sessão sem identificador")
        try:
            epoch = int(payload.get("e"))
            issued = int(payload.get("iat"))
            expires = int(payload.get("exp"))
        except (TypeError, ValueError):
            raise PlayerSessionError("token de sessão malformado") from None
        if epoch < 0 or issued <= 0 or expires <= issued:
            raise PlayerSessionError("token de sessão malformado")
        if expires - issued > MAX_TTL_SECONDS:
            raise PlayerSessionError("token de sessão malformado")
        instant = time.time() if now is None else float(now)
        # 300 s of slack on the issue instant only: a browser clock is never
        # consulted, but a host whose clock jumps must not mint unusable links.
        if issued > instant + 300:
            raise PlayerSessionError("token de sessão emitido no futuro")
        if instant >= expires:
            raise PlayerSessionError("sessão do jogador expirada")
        return PlayerSession(player_id=player_id, epoch=epoch,
                             issued_at=issued, expires_at=expires,
                             remember=bool(payload.get("r")),
                             session_id=session_id)


# -- live sessions (decision 0070) -----------------------------------

class SessionRegistry:
    """Which minted tokens are still allowed to exist.

    One row per token: the player, the epoch, when it was created, last seen
    and expires, and the device that opened it. Deleting a row logs that one
    device out; the token's signature still verifies, but the host refuses it
    because the row is gone.

    The file is small and read on the same pass as the player row the host
    already reads. Writes are rare — a mint, a logout, a revoke, or a
    ``touch`` at most once per ``touch_seconds`` — so the stateless fast path
    (a request that only reads) does not write at all.
    """

    FILE = "player_sessions.json"

    def __init__(self, path: str, *, max_per_player: int = 20,
                 touch_seconds: int = 600) -> None:
        self.path = path
        self.lock = threading.RLock()
        self.max_per_player = max(1, int(max_per_player))
        self.touch_seconds = max(0, int(touch_seconds))
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if not os.path.exists(path):
            self._write({})

    # -- storage -----------------------------------------------------
    def _read(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return {}
        rows = data.get("sessions") if isinstance(data, dict) else None
        return rows if isinstance(rows, dict) else {}

    def _write(self, rows: dict) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"sessions": rows}, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    @staticmethod
    def _instant(now: float | None) -> int:
        return int(time.time() if now is None else now)

    @staticmethod
    def _expires(row: dict) -> int:
        try:
            return int(row.get("expires") or 0)
        except (TypeError, ValueError):
            return 0

    def _drop_expired(self, rows: dict, instant: int) -> int:
        dead = [sid for sid, row in rows.items()
                if not isinstance(row, dict) or
                self._expires(row) <= instant]
        for sid in dead:
            rows.pop(sid, None)
        return len(dead)

    # -- lifecycle ---------------------------------------------------
    def record(self, session: PlayerSession, *, user_agent: str = "",
               ip: str = "", now: float | None = None) -> dict:
        """Register a freshly minted token. Oldest rows fall off at the cap."""
        instant = self._instant(now)
        row = {
            "player": session.player_id,
            "epoch": int(session.epoch),
            "created": int(session.issued_at),
            "seen": instant,
            "expires": int(session.expires_at),
            "remember": bool(session.remember),
            "user_agent": str(user_agent or "")[:200],
            "ip": str(ip or "")[:64],
        }
        with self.lock:
            rows = self._read()
            self._drop_expired(rows, instant)
            mine = sorted(
                ((sid, entry) for sid, entry in rows.items()
                 if isinstance(entry, dict) and
                 entry.get("player") == session.player_id),
                key=lambda item: int(item[1].get("created") or 0))
            while len(mine) >= self.max_per_player:
                rows.pop(mine.pop(0)[0], None)
            rows[session.session_id] = row
            self._write(rows)
        return {"id": session.session_id, **row}

    def lookup(self, session_id: str, *, now: float | None = None) -> dict | None:
        """The live row for an id, or None when it was revoked/expired."""
        instant = self._instant(now)
        with self.lock:
            rows = self._read()
            row = rows.get(str(session_id or ""))
            if not isinstance(row, dict):
                return None
            if self._expires(row) <= instant:
                rows.pop(str(session_id), None)
                self._write(rows)
                return None
            return {"id": str(session_id), **row}

    def touch(self, session: PlayerSession,
              now: float | None = None) -> bool:
        """Note activity, at most once per ``touch_seconds``. False = gone."""
        instant = self._instant(now)
        with self.lock:
            rows = self._read()
            row = rows.get(session.session_id)
            if not isinstance(row, dict):
                return False
            if row.get("player") != session.player_id or \
                    row.get("epoch") != session.epoch or \
                    self._expires(row) != session.expires_at:
                return False
            if self._expires(row) <= instant:
                rows.pop(session.session_id, None)
                self._write(rows)
                return False
            try:
                seen = int(row.get("seen") or 0)
            except (TypeError, ValueError):
                seen = 0
            if instant - seen >= self.touch_seconds:
                row["seen"] = instant
                rows[session.session_id] = row
                self._write(rows)
            return True

    def active(self, player_id: str, *, now: float | None = None) -> list[dict]:
        """Live rows for one player, newest first. Expired rows are pruned."""
        instant = self._instant(now)
        with self.lock:
            rows = self._read()
            if self._drop_expired(rows, instant):
                self._write(rows)
            mine = [{"id": sid, **row} for sid, row in rows.items()
                    if isinstance(row, dict) and
                    row.get("player") == player_id]
        return sorted(mine, key=lambda row: -int(row.get("created") or 0))

    def revoke(self, player_id: str, session_id: str) -> bool:
        """Delete one row, but only if it belongs to ``player_id``."""
        session_id = str(session_id or "")
        with self.lock:
            rows = self._read()
            row = rows.get(session_id)
            if not isinstance(row, dict) or row.get("player") != player_id:
                return False
            rows.pop(session_id, None)
            self._write(rows)
            return True

    def revoke_others(self, player_id: str, keep_session_id: str) -> int:
        keep = str(keep_session_id or "")
        with self.lock:
            rows = self._read()
            dead = [sid for sid, row in rows.items()
                    if isinstance(row, dict) and
                    row.get("player") == player_id and sid != keep]
            for sid in dead:
                rows.pop(sid, None)
            if dead:
                self._write(rows)
            return len(dead)

    def revoke_player(self, player_id: str) -> int:
        """Every device for one player (a password change, a reset)."""
        with self.lock:
            rows = self._read()
            dead = [sid for sid, row in rows.items()
                    if isinstance(row, dict) and
                    row.get("player") == player_id]
            for sid in dead:
                rows.pop(sid, None)
            if dead:
                self._write(rows)
            return len(dead)

    def prune(self, *, now: float | None = None) -> int:
        instant = self._instant(now)
        with self.lock:
            rows = self._read()
            dropped = self._drop_expired(rows, instant)
            if dropped:
                self._write(rows)
            return dropped


# -- secret resolution ----------------------------------------------

def derive_secret(source: str) -> str:
    """A sub-key for player sessions from an existing high-entropy secret.

    Reusing ``BETTER_AUTH_SECRET`` is what keeps this change free of a new
    owner step, but the two uses must not share a key: HKDF-style derivation
    with a fixed context makes this a distinct key, and a token minted here can
    never be accepted as a Better Auth cookie (or the reverse).
    """
    if not source:
        raise PlayerSessionError("cannot derive from an empty secret")
    return hmac.new(source.encode("utf-8"),
                    b"operator.player-session.derive.v1",
                    hashlib.sha256).hexdigest()


def _read_key_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def _write_key_file(path: str, key: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(key)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass  # Windows: the ACL is inherited; the file never leaves the host
    os.replace(tmp, path)


def resolve_secret(env: dict[str, str] | None = None,
                   data_dir: str | None = None,
                   secret: str | None = None) -> str:
    """The signing key, in order: explicit, env, derived, persisted.

    ``PLAYER_SESSION_SECRET`` is the proper production value. When it is
    absent the deploy still works: ``BETTER_AUTH_SECRET`` (already carried to
    Render for 0066) is derived into a player-only key. A local run with
    neither writes ``data/player_session.key`` once, so a restart keeps the
    sessions it issued; that file is the last resort, not the recommendation.
    """
    if secret:
        return str(secret)
    source = dict(env or {})
    explicit = (source.get("PLAYER_SESSION_SECRET") or "").strip()
    if explicit:
        return explicit
    betterauth = (source.get("BETTER_AUTH_SECRET") or "").strip()
    if betterauth:
        return derive_secret(betterauth)
    if not data_dir:
        raise PlayerSessionError("no player session secret and no data directory")
    path = os.path.join(data_dir, KEY_FILE)
    key = _read_key_file(path)
    if not key:
        key = secrets.token_urlsafe(48)
        _write_key_file(path, key)
    return key


def resolve_player_sessions(env: dict[str, str] | None = None,
                            data_dir: str | None = None,
                            secret: str | None = None,
                            **policy) -> PlayerSessions:
    """The module's one constructor, explicit so tests stay hermetic."""
    return PlayerSessions(resolve_secret(env, data_dir, secret), **policy)
