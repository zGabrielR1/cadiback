"""Signed player sessions (decision 0069). Stdlib only. DEMO.

Until now a player *was* whoever the request said: every player write carried
``player: <id>`` in its body and ``/api/player?id=`` read a profile, and the id
is derived from the CPF (``player-…``), which is a semi-public document. The
password protected the login form, not the money.

A session here is a signed, stateless token:

    ps1.<base64url(payload)>.<base64url(hmac-sha256)>

The payload names the player, the row's ``session_epoch``, the issue/expiry
instants and whether "remember me" was asked for. The signature covers the
exact ``ps1.<payload>`` text with a fixed context prefix, so a token minted by
another use of the same secret — or an edited payload — is refused.

Stateless is a deliberate trade, the same one the Better Auth bridge makes
(0066): there is no session table to port, a restart does not log players out,
and revocation is one integer on the player row. A password reset or an admin
reset bumps ``session_epoch`` and every token minted before it stops verifying:
the password change finally has something real to revoke (0068's open limit).
A single device cannot be logged out alone; the module does not pretend
otherwise.

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
import time
from dataclasses import dataclass

VERSION = "ps1"
# Domain separation: the signature is over this prefix plus the token body.
# A secret shared with another signer cannot mint a player session.
CONTEXT = b"operator.player-session.v1\n"

TTL_SECONDS = 12 * 60 * 60            # a normal login
REMEMBER_TTL_SECONDS = 30 * 24 * 60 * 60   # "lembrar de mim"
MAX_TTL_SECONDS = 365 * 24 * 60 * 60

# A key file in the data dir, used only when no environment secret exists.
KEY_FILE = "player_session.key"


class PlayerSessionError(ValueError):
    """A token is missing, malformed, forged, expired or revoked."""


@dataclass(frozen=True)
class PlayerSession:
    """One verified token. ``epoch`` is checked against the player row."""

    player_id: str
    epoch: int
    issued_at: int
    expires_at: int
    remember: bool = False

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
              remember: bool = False, now: float | None = None) -> str:
        player_id = str(player_id or "")
        if not player_id or len(player_id) > 128:
            raise PlayerSessionError("a session needs a player id")
        try:
            epoch = int(epoch)
        except (TypeError, ValueError):
            raise PlayerSessionError("session epoch must be an integer") from None
        if epoch < 0:
            raise PlayerSessionError("session epoch must not be negative")
        issued = int(time.time() if now is None else now)
        ttl = self.remember_ttl_seconds if remember else self.ttl_seconds
        payload = {
            "p": player_id,
            "e": epoch,
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
        if not token or len(token) > 2048:
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
                             remember=bool(payload.get("r")))


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
