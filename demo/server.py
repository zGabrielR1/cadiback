"""Demo platform server. Stdlib only. DEMO — no real money moves.

Run:  python -m demo.server  (from operator/, serves on 127.0.0.1:8765)
Then: open http://127.0.0.1:8765 in a browser.

Layout: player onboarding (name + CPF + Pix + bank) | cashier
(Pix/TED/debit deposit, Pix payout) | slot (certified titles only) |
history + compliance strip. Every spin and every payout round-trips the real
``frame`` wallet, ledger gates, and BR cert gate — the PSP and the reels are
stubs, the books are not.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from frame.compliance.sigap import (
    BRAZIL,
    CertificationError,
    ExclusionError,
    ExclusionRegistry,
    GameCertification,
    GameRegistry,
    Limits,
    SigapReporter,
)
from frame.core.money import to_cents
from frame.ops.health import health
from frame.ops.scheduler import Scheduler
from frame.wallet.books import (
    GGR_REVENUE,
    OPERATOR_CASH,
    PAYABLE_PLAYER,
    PLAYER_BALANCE,
    PLAYER_BONUS,
    Books,
    DuplicatePosting,
    WalletError,
)

from .payments import (
    classify_pix_key,
    mask_pix_key,
    process_deposit,
    process_withdrawal,
    validate_bank_account,
    validate_cpf,
)
from frame.core.ids import normalize, slug
from .auth import AuthError, SessionBook, SessionStore, UserStore
from .slot import DEMO_RTP_STR, spin, tiers_for
from .casino import ROULETTE_GAME_ID, roulette_spin
from .arcade import (ARCADE_GAME_IDS, CRASH_GAME_ID, CRASH_GROWTH_PER_SEC,
                     CRASH_LIVE_MAX, MINES_GAME_ID, PLINKO_GAME_ID,
                     arcade_round, crash_bust_multiplier,
                     crash_elapsed_for, crash_live_round,
                     crash_multiplier_at, theoretical_rtp as
                     arcade_theoretical_rtp)
from . import odds_engine, provider_demos, sports_data
from . import game_proxy
from . import rgs_proxy
from .risk import RiskPolicy, evaluate_player
from .vendor import AggregatorError, VendorAggregator, VendorConfig


def external_demo_url(env: dict[str, str] | None = None) -> str | None:
    """Official provider free-play page, if the operator configured one.

    This is a wallet-isolated iframe: the third party serves its own demo,
    no stake or payout touches our books. Paste an official provider demo
    URL (not a copy, not a re-upload) or leave unset.
    """
    source = env if env is not None else os.environ
    url = (source.get("DEMO_IFRAME_URL") or "").strip()
    if not url or not url.startswith("https://"):
        return None
    return url

ROOT = os.path.dirname(os.path.abspath(__file__))
# Data dir: overridable so a deployment can point the ledger and profiles at a
# mounted volume (the PaaS filesystem is otherwise wiped on every deploy).
DATA = os.environ.get("OPERATOR_DATA_DIR") or os.path.join(ROOT, "data")
WEB_OUT = os.path.join(os.path.dirname(ROOT), "web", "out")

MIME = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".svg": "image/svg+xml", ".gif": "image/gif",
        ".ico": "image/x-icon", ".json": "application/json", ".webmanifest": "application/manifest+json",
        ".woff2": "font/woff2", ".txt": "text/plain", ".map": "application/json"}


def _safe_relative(url_path: str) -> str | None:
    """Normalize a URL path into a relative path that cannot escape its base.

    Rejects anything drive-absolute (`/C:/win.ini`), UNC/backslash forms, and
    any `..` segment. A bare substring test for `..` is both insufficient
    (os.path.join discards the base for drive-absolute paths) and over-broad
    (it would reject a legitimate `a..b` filename).
    """
    rel = url_path.replace("\\", "/").lstrip("/")
    if not rel:
        return "index.html"
    if rel.endswith("/"):
        rel += "index.html"
    if ":" in rel or rel.startswith("//"):
        return None
    parts = rel.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    return "/".join(parts)


def static_file(url_path: str) -> tuple[str, str] | None:
    """Serve the Next.js export (web/out) when built; else the zero-build
    index.html. Returns (abs_path, content_type) or None."""
    rel = _safe_relative(url_path)
    if rel is None:
        return None
    for base in (WEB_OUT, ROOT):
        root = os.path.abspath(base)
        candidate = os.path.abspath(os.path.join(root, *rel.split("/")))
        if os.path.commonpath([candidate, root]) != root:
            continue
        if os.path.isfile(candidate):
            ext = os.path.splitext(candidate)[1].lower()
            return candidate, MIME.get(ext, "application/octet-stream")
    return None
BOOKS_PATH = os.path.join(DATA, "books.jsonl")
PLAYERS_PATH = os.path.join(ROOT, "data", "players.json")
ROUNDS_PATH = os.path.join(DATA, "rounds.jsonl")
LEDGER_PATH = os.path.join(DATA, "ledger.jsonl")

STAKE_STEPS = (200, 500, 1000, 2500)  # centavos: R$2/5/10/25
HEARTBEAT_SECONDS = 30

# Promotions (demo): real mechanics through the double-entry wallet.
# Welcome bonus: 100% of the first deposit, capped, released by turnover.
# Cashback: 10% of the day's net loss, capped, one claim per UTC day.
WELCOME_CAP_MINOR = 50000           # R$500
WELCOME_MIN_DEPOSIT_MINOR = 2000    # first deposit must be >= R$20
WELCOME_WAGERING = 20               # turnover target: 20x the granted bonus
CASHBACK_RATE_PERCENT = 10          # 10% of the day's net loss
CASHBACK_CAP_MINOR = 20000          # R$200 per day
CASHBACK_MIN_MINOR = 100            # claim needs at least R$1 of loss
CASHBACK_WAGERING = 1               # turnover target: 1x the cashback

# Merchandising category per demo title. Deliberately NOT on GameCertification:
# `frame/compliance` certifies games, it does not decide how a lobby sorts them.
# The sidebar used to filter on a field the API never sent, so every branch
# returned the same list and every category looked identical.
DEMO_CATEGORY = {
    "demo:neon-gems": "Slots",
    "demo:fortune-ledger": "Slots",
    "demo:royale-roulette": "Mesa",
    "demo:roulette-europeia": "Mesa",
    "demo:crimson-dragons": "Slots",
    "demo:gold-vault": "Slots",
    "demo:crash-nitro": "Crash",
    "demo:plinko-drops": "Crash",
    "demo:minas": "Crash",
    "demo:dados": "Originais",
}


def demo_registry() -> GameRegistry:
    registry = GameRegistry()
    registry.register(
        GameCertification(
            game_id="demo:neon-gems",
            provider="demo_studio",
            title="Neon Gems",
            rng_reference="demo-sha256-v1",
            certificate_id="BR-DEMO-0001",
            lab="DEMO-LAB",
            issued_for=BRAZIL,
            status="certified",
            sigap_submission="submitted",
            certified_on="2026-10-01",
            rtp="95.90",
        )
    )
    registry.register(
        GameCertification(
            game_id="demo:fortune-ledger",
            provider="demo_studio",
            title="Fortune Ledger",
            rng_reference="demo-sha256-v1",
            certificate_id="BR-DEMO-0002",
            lab="DEMO-LAB",
            issued_for=BRAZIL,
            status="certified",
            sigap_submission="submitted",
            certified_on="2026-10-01",
            rtp="95.90",
        )
    )
    registry.register(
        GameCertification(
            game_id="demo:royale-roulette",
            provider="demo_studio",
            title="Royale Roulette (uncertified)",
            rng_reference="demo-sha256-v1",
            certificate_id="",
            lab="DEMO-LAB",
            issued_for="MT",
            status="pending",
            sigap_submission="not_submitted",
            certified_on="",
            rtp="97.00",
        )
    )
    registry.register(
        GameCertification(
            game_id="demo:roulette-europeia",
            provider="demo_studio",
            title="Roleta Europeia",
            rng_reference="demo-sha256-v1",
            certificate_id="BR-DEMO-0003",
            lab="DEMO-LAB",
            issued_for=BRAZIL,
            status="certified",
            sigap_submission="submitted",
            certified_on="2026-10-09",
            rtp="97.30",
        )
    )
    registry.register(
        GameCertification(
            game_id="demo:crimson-dragons",
            provider="demo_studio",
            title="Crimson Dragons",
            rng_reference="demo-sha256-v1",
            certificate_id="BR-DEMO-0004",
            lab="DEMO-LAB",
            issued_for=BRAZIL,
            status="certified",
            sigap_submission="submitted",
            certified_on="2026-10-09",
            rtp="94.95",
        )
    )
    registry.register(
        GameCertification(
            game_id="demo:gold-vault",
            provider="demo_studio",
            title="Gold Vault",
            rng_reference="demo-sha256-v1",
            certificate_id="BR-DEMO-0005",
            lab="DEMO-LAB",
            issued_for=BRAZIL,
            status="certified",
            sigap_submission="submitted",
            certified_on="2026-10-09",
            rtp="96.60",
        )
    )
    registry.register(
        GameCertification(
            game_id="demo:crash-nitro",
            provider="demo_studio",
            title="Crash Nitro",
            rng_reference="demo-sha256-v1",
            certificate_id="BR-DEMO-0006",
            lab="DEMO-LAB",
            issued_for=BRAZIL,
            status="certified",
            sigap_submission="submitted",
            certified_on="2026-10-12",
            rtp="97.00",
        )
    )
    registry.register(
        GameCertification(
            game_id="demo:plinko-drops",
            provider="demo_studio",
            title="Plinko Drops",
            rng_reference="demo-sha256-v1",
            certificate_id="BR-DEMO-0007",
            lab="DEMO-LAB",
            issued_for=BRAZIL,
            status="certified",
            sigap_submission="submitted",
            certified_on="2026-10-12",
            rtp="97.16",
        )
    )
    registry.register(
        GameCertification(
            game_id="demo:minas",
            provider="demo_studio",
            title="Minas",
            rng_reference="demo-sha256-v1",
            certificate_id="BR-DEMO-0008",
            lab="DEMO-LAB",
            issued_for=BRAZIL,
            status="certified",
            sigap_submission="submitted",
            certified_on="2026-10-12",
            rtp="97.00",
        )
    )
    registry.register(
        GameCertification(
            game_id="demo:dados",
            provider="demo_studio",
            title="Dados Relâmpago",
            rng_reference="demo-sha256-v1",
            certificate_id="BR-DEMO-0009",
            lab="DEMO-LAB",
            issued_for=BRAZIL,
            status="certified",
            sigap_submission="submitted",
            certified_on="2026-10-12",
            rtp="97.00",
        )
    )
    return registry


def fixture_catalog(path: str) -> dict:
    """Serve a captured public-title sample as non-launchable vendor rows.

    The file carries facts (provider, title, source URL) and explicitly no
    invented RTP. Whatever the file claims, every row leaves here with
    `launchable: False`: no file on disk can launch a title, only a registered
    BR certificate can. Uncategorized by design — a sample is not a taxonomy.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        return {"status": f"fixture error: {exc}", "games": []}
    rows = payload.get("titles") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {"status": "fixture error: no titles list", "games": []}
    games = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("game_id") or not row.get("title"):
            continue
        games.append({
            "game_id": str(row["game_id"]),
            "provider": str(row.get("provider") or "unknown"),
            "title": str(row["title"]),
            "rtp": row.get("rtp"),
            "source_url": row.get("source_url"),
            "launchable": False,
            "category": None,
            "note": "amostra pública sem certificado BR — não lançável",
        })
    scope = ""
    if isinstance(payload, dict) and isinstance(payload.get("provenance"), dict):
        scope = str(payload["provenance"].get("scope") or "sample")
    return {"status": f"fixture: {len(games)} public titles ({scope}) — "
                      "none launchable before BR certs",
            "games": games}


def _mask_name(name: str) -> str:
    """Recent-wins ticker label: first name + last initial,
    like a real casino floor — never the full name."""
    parts = str(name or "").split()
    if len(parts) <= 1:
        return parts[0] if parts else "jogador"
    return f"{parts[0]} {parts[-1][0]}."


class Store:
    """Tiny JSON store for demo profiles. Money lives in Books, not here."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{}")

    def read_all(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as handle:
            try:
                return json.load(handle)
            except json.JSONDecodeError:
                return {}

    def write_all(self, data: dict) -> None:
        with self.lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)


class Demo:
    def __init__(self, data_dir: str = DATA) -> None:
        os.makedirs(data_dir, exist_ok=True)
        self.books = Books(os.path.join(data_dir, "books.jsonl"))
        self.players = Store(os.path.join(data_dir, "players.json"))
        # painel administrativo: credentials + bearer sessions (auth.py)
        self.users = UserStore(os.path.join(data_dir, "users.json"))
        self.session_path = os.path.join(data_dir, "sessions.json")
        self.sessions = SessionBook()
        self._load_sessions()
        self.registry = demo_registry()
        self.exclusions = ExclusionRegistry()
        self.limits = Limits(deposit_daily=5000000)  # R$50.000/day demo cap
        self.reporter = SigapReporter()
        self.scheduler = Scheduler(os.path.join(data_dir, "sched"))
        self.deposits_today: dict[str, int] = {}
        self.deposit_days: dict[str, dict[str, object]] = {}
        self.pix_keys: dict[str, str] = {}
        self.store = self.players
        self.plays_path = os.path.join(data_dir, "plays.jsonl")
        self.rounds_path = os.path.join(data_dir, "rounds.jsonl")
        self.ledger_path = os.path.join(data_dir, "ledger.jsonl")
        self.promos = Store(os.path.join(data_dir, "promos.json"))
        self.wallet_tokens: dict[str, dict] = {}
        # RGS session id -> our wallet token, per provider: only the
        # first call carries our token, later ones name the session
        self.rgs_sessions: dict[tuple[str, str], str] = {}
        # rounds in flight, keyed by (provider, RGS session id)
        self.rgs_rounds: dict[tuple[str, str], dict] = {}
        self.orphan_rounds: list[dict] = []
        # crash "live" rounds in flight, keyed by the public token: the
        # secret draw seed (round_id) and the secret bust are held server
        # side and only revealed when the round settles
        self.crash_path = os.path.join(data_dir, "crash_pending.json")
        self._crash_lock = threading.Lock()
        self.crash_pending: dict[str, dict] = {}
        self._load_crash_pending()
        self.started_at = datetime.now(timezone.utc)
        self._load_exclusions()
        if not self.scheduler.last_receipt():
            self.scheduler.receipt("boot", 0, 0, 0, [])  # one honest baseline
        try:
            self.vendor: VendorAggregator | None = VendorAggregator(
                VendorConfig.from_env())
        except AggregatorError:
            self.vendor = None
        self._load_pix_keys()  # a restart must not widen who can receive money

    def _load_sessions(self) -> None:
        """Rebuild bearer sessions from disk so a restart does not forcibly
        log out every panel user.

        Restoring purely is deliberate: SessionBook.issue would bump timing
        and recompute expires_at, so a restart must not refresh tokens or
        extend lingering ones — keep the persisted absolute times. A token
        whose TTL the boot sweep considers expired is silently dropped here
        and will not be reissued, and SessionBook._sweep also runs on every
        issue/check, so a token that expires while the process is up still
        goes away.
        """
        store = SessionStore(self.session_path)
        for token, session in store.load().items():
            self.sessions._sessions[token] = {
                "username": session["username"],
                "role": session["role"],
                "issued_at": session["issued_at"],
                "expires_at": session["expires_at"],
            }
        self.sessions._sweep(self._now_for_sessions())  # drop anything already past TTL
        self._save_sessions()

    def _save_sessions(self) -> None:
        store = SessionStore(self.session_path)
        store.save(dict(self.sessions._sessions))

    @staticmethod
    def _now_for_sessions() -> datetime:
        return datetime.now(timezone.utc)

    def _load_pix_keys(self) -> None:
        """Rebuild the payout allowlist from the store."""
        self.pix_keys = {pid: row["pix_raw"] for pid, row
                         in self.players.read_all().items()
                         if row.get("pix_raw")}

    def _exclusions_path(self) -> str:
        return os.path.join(os.path.dirname(self.players.path), "exclusions.json")

    def _load_exclusions(self) -> None:
        """Self-exclusion must outlive the process: a control that resets on
        restart is not a control."""
        path = self._exclusions_path()
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                self.exclusions = ExclusionRegistry.from_dict(json.load(handle))
        except (ValueError, OSError):
            pass  # unreadable state: start empty, never crash the server

    def _save_exclusions(self) -> None:
        path = self._exclusions_path()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(self.exclusions.as_dict(), handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def self_exclude(self, player_id: str, until: str) -> dict:
        self.exclusions.self_exclude(player_id, until)
        self._save_exclusions()
        return {"player": player_id, "until": str(until)[:10],
                "active": self.exclusions.active(player_id)}

    def lift_exclusion(self, player_id: str) -> dict:
        lifted = self.exclusions.lift(player_id)
        self._save_exclusions()
        return {"player": player_id, "lifted": lifted,
                "active": self.exclusions.active(player_id)}

    # -- players ------------------------------------------------------
    def upsert_player(self, payload: dict) -> dict:
        name = (payload.get("name") or "").strip()
        if len(name) < 2:
            raise ValueError("player name is required")
        cpf = validate_cpf(payload.get("cpf") or "")
        pix = classify_pix_key(payload.get("pix_key") or "")
        bank = payload.get("bank") or {}
        validate_bank_account(
            bank.get("bank_code"), bank.get("agency"),
            bank.get("account"), bank.get("holder_name"), name,
        )
        player_id = "player-" + slug("wallet", cpf)[:24]  # one wallet per person
        data = self.players.read_all()
        data[player_id] = {
            "player_id": player_id,
            "name": name,
            "cpf_masked": "***" + cpf[-4:],
            "pix_kind": pix.kind,
            "pix_masked": mask_pix_key(pix.raw),
            "pix_raw": pix.raw,  # sole payout destination for this wallet
            "bank": {
                "bank_code": bank.get("bank_code"),
                "agency": bank.get("agency"),
                "account": bank.get("account"),
            },
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.players.write_all(data)
        self.pix_keys[player_id] = pix.raw
        profile = dict(data[player_id])
        profile["available_minor"] = self.books.available(player_id)
        return profile

    def profile(self, player_id: str) -> dict:
        data = self.players.read_all()
        if player_id not in data:
            raise KeyError(f"unknown player: {player_id}")
        profile = dict(data[player_id])
        profile["available_minor"] = self.books.available(player_id)
        profile["bonus_minor"] = self.books.bonus_available(player_id)
        profile["bonus"] = self._bonus_view(player_id)
        return profile

    # -- promotions -----------------------------------------------------
    # Real mechanics, small numbers: every claim posts a `bonus_grant`
    # through the double-entry wallet, every stake splits cash/bonus under
    # the books lock, and bonus funds convert to withdrawable cash only
    # after the wagering target is met (or when no requirement owns them).
    def _promo_state(self, player_id: str) -> dict:
        data = self.promos.read_all()
        row = data.get(player_id)
        return dict(row) if isinstance(row, dict) else {}

    def _save_promo_state(self, player_id: str, state: dict) -> None:
        data = self.promos.read_all()
        data[player_id] = state
        self.promos.write_all(data)

    def _deposit_amounts(self, player_id: str) -> list[int]:
        """Deposit amounts straight from the journal: the books are the
        source of truth for money, the promo store only records claims."""
        amounts = []
        for posting in self.books.postings:
            if posting.kind == "deposit" and posting.metadata.get("player") == player_id:
                amounts.append(sum(n for a, n in posting.legs if a == PLAYER_BALANCE))
        return amounts

    def _active_event(self, state: dict) -> dict | None:
        event = state.get("bonus_event")
        if isinstance(event, dict) and not event.get("converted"):
            return event
        return None

    def _today_net_loss(self, player_id: str) -> int:
        day = datetime.now(timezone.utc).date().isoformat()
        stake = payout = 0
        for row in self.history(player_id, limit=10000):
            if not str(row.get("ts", "")).startswith(day):
                continue
            stake += int(row.get("stake_minor") or 0)
            payout += int(row.get("payout_minor") or 0)
        return max(0, stake - payout)

    def _maybe_convert(self, player_id: str, reason: str,
                       state: dict | None = None) -> int:
        """Release bonus funds to withdrawable cash when the rules allow
        it: wagering target met, or no active requirement owns the money
        (e.g. a win credited after the event already converted). Returns
        the centavos converted; 0 means the funds stay in `player:bonus`.
        Caller holds books.lock."""
        if state is None:
            state = self._promo_state(player_id)
        bonus = self.books.bonus_available(player_id)
        event = state.get("bonus_event")
        if self._active_event(state) is not None:
            target = int(event.get("target") or 0)
            wagered = int(event.get("wagered") or 0)
            if wagered < target:
                return 0  # requirement not met: hold the bonus
            converted = 0
            if bonus > 0:
                try:
                    self.books.post(
                        f"demo:bonusconv:{player_id}:{reason}", "bonus_convert",
                        [(PLAYER_BONUS, -bonus), (PLAYER_BALANCE, bonus)],
                        {"player": player_id, "reason": reason})
                    converted = bonus
                except DuplicatePosting:
                    # the money moved earlier; only the state write was lost
                    converted = bonus
            event["converted"] = True
            event["converted_minor"] = converted
            self._save_promo_state(player_id, state)
            return converted
        if bonus > 0:
            # orphaned bonus (credited with no requirement on file): it can
            # only be released, never held hostage by a finished event
            try:
                self.books.post(
                    f"demo:bonusconv:{player_id}:{reason}", "bonus_convert",
                    [(PLAYER_BALANCE, bonus), (PLAYER_BONUS, -bonus)],
                    {"player": player_id, "reason": reason})
            except DuplicatePosting:
                pass
            return bonus
        return 0

    def _record_wager(self, player_id: str, stake: int, reason: str) -> int:
        """Count turnover against the active bonus and release it once the
        target is met. Caller holds books.lock."""
        state = self._promo_state(player_id)
        event = self._active_event(state)
        if event is None:
            return 0
        event["wagered"] = int(event.get("wagered") or 0) + stake
        converted = self._maybe_convert(player_id, reason, state)
        if not event.get("converted"):
            self._save_promo_state(player_id, state)
        return converted

    def _stake_split(self, player_id: str, stake: int) -> int:
        """Cash-first split: bonus is staked only after cash runs out.
        Caller must hold books.lock so the split cannot race another
        thread's withdrawal or bet (TOCTOU on the split is how balances
        went negative in the audit)."""
        cash = self.books.available(player_id)
        bonus = self.books.bonus_available(player_id)
        cash_part = min(cash, stake)
        bonus_part = stake - cash_part
        if bonus_part > bonus:
            raise ValueError(
                f"saldo insuficiente: disponível {cash + bonus} centavos "
                f"para aposta de {stake}")
        return bonus_part

    def claim_bonus(self, payload: dict) -> dict:
        player_id = payload["player"]
        kind = payload.get("kind")
        if kind not in ("welcome", "cashback"):
            raise ValueError("kind must be 'welcome' or 'cashback'")
        if player_id not in self.players.read_all():
            raise KeyError(f"unknown player: {player_id}")
        self.exclusions.assert_playable(player_id)
        with self.books.lock:
            state = self._promo_state(player_id)
            bonus = self.books.bonus_available(player_id)
            active = self._active_event(state)
            if active is not None and bonus > 0:
                raise ValueError(
                    "bônus ativo: conclua o giro antes de resgatar outra "
                    "promoção")
            if active is not None:
                # the funds are gone but the requirement never finished:
                # close the dead event so it cannot block claims forever
                active["converted"] = True
                active["converted_minor"] = 0
            now = datetime.now(timezone.utc)
            day = now.date().isoformat()
            if kind == "welcome":
                if state.get("welcome_claimed"):
                    raise ValueError("bônus de boas-vindas já resgatado")
                deposits = self._deposit_amounts(player_id)
                if not deposits:
                    raise ValueError(
                        "faça um depósito para liberar o bônus de "
                        "boas-vindas")
                if deposits[0] < WELCOME_MIN_DEPOSIT_MINOR:
                    raise ValueError(
                        "depósito mínimo de R$20 no primeiro depósito para "
                        "resgatar o bônus")
                granted = min(deposits[0], WELCOME_CAP_MINOR)
                key = f"demo:bonus:{player_id}:welcome"
            else:  # cashback
                days = list(state.get("cashback_days") or [])
                if day in days:
                    raise ValueError("cashback já resgatado hoje")
                loss = self._today_net_loss(player_id)
                granted = min(loss * CASHBACK_RATE_PERCENT // 100,
                              CASHBACK_CAP_MINOR)
                if granted < CASHBACK_MIN_MINOR:
                    raise ValueError(
                        "sem perdas líquidas hoje para cashback")
                key = f"demo:bonus:{player_id}:cashback:{day}"
                days.append(day)
                state["cashback_days"] = days
            replayed = False
            try:
                self.books.grant_bonus(key, player_id, granted)
            except DuplicatePosting:
                # a grant posted but the state write was lost: repair it
                replayed = True
            state["bonus_event"] = {
                "kind": kind, "granted": granted,
                "target": granted * (WELCOME_WAGERING if kind == "welcome"
                                     else CASHBACK_WAGERING),
                "wagered": 0, "converted": False,
                "claimed_at": now.isoformat(timespec="seconds"),
            }
            if kind == "welcome":
                state["welcome_claimed"] = True
            self._save_promo_state(player_id, state)
            self.books.assert_balanced()
        return {
            "kind": kind, "granted_minor": granted,
            "target_minor": granted * (WELCOME_WAGERING if kind == "welcome"
                                       else CASHBACK_WAGERING),
            "bonus_minor": self.books.bonus_available(player_id),
            "available_minor": self.books.available(player_id),
            "replayed": replayed,
        }

    def _bonus_view(self, player_id: str) -> dict:
        state = self._promo_state(player_id)
        event = state.get("bonus_event")
        if not isinstance(event, dict):
            event = None
        bonus = self.books.bonus_available(player_id)
        active = self._active_event(state) is not None
        deposits = self._deposit_amounts(player_id)
        cashback_days = list(state.get("cashback_days") or [])
        day = datetime.now(timezone.utc).date().isoformat()
        loss_today = self._today_net_loss(player_id)
        cashback = min(loss_today * CASHBACK_RATE_PERCENT // 100,
                       CASHBACK_CAP_MINOR)
        blocked = active and bonus > 0
        view = {
            "welcome_claimed": bool(state.get("welcome_claimed")),
            "can_claim_welcome": (
                not state.get("welcome_claimed") and bool(deposits)
                and deposits[0] >= WELCOME_MIN_DEPOSIT_MINOR and not blocked),
            "first_deposit_minor": deposits[0] if deposits else 0,
            "cashback_available_minor": cashback,
            "cashback_claimed_today": day in cashback_days,
            "can_claim_cashback": (
                cashback >= CASHBACK_MIN_MINOR and day not in cashback_days
                and not blocked),
            "active": active,
            "event": None,
        }
        if event is not None:
            target = int(event.get("target") or 0)
            wagered = int(event.get("wagered") or 0)
            view["event"] = {
                "kind": event.get("kind"),
                "granted_minor": int(event.get("granted") or 0),
                "wagered_minor": wagered,
                "target_minor": target,
                "percent": min(100, wagered * 100 // target) if target else 100,
                "converted": bool(event.get("converted")),
            }
        return view

    # -- cashier ------------------------------------------------------
    def _deposited_today(self, player_id: str) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        row = self.deposit_days.get(player_id, {})
        if row.get("day") != today:
            return 0
        return int(row.get("total", 0))

    def _record_deposit(self, player_id: str, amount: int) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        row = self.deposit_days.setdefault(player_id, {"day": today, "total": 0})
        if row.get("day") != today:
            row["day"] = today
            row["total"] = 0
        row["total"] = int(row.get("total", 0)) + amount

    @staticmethod
    def _minor(amount: int) -> int:
        """Browser amounts arrive in centavos. Anything else is a bug, not a
        conversion: `to_cents` would turn 1000000 into R$10.000,00."""
        value = int(amount)
        if value <= 0:
            raise ValueError("amount_minor must be positive")
        if value > 10_000_000:  # R$100.000 ceiling on a demo rail
            raise ValueError(f"amount_minor out of range: {value}")
        return value

    def deposit(self, payload: dict) -> dict:
        player_id = payload["player"]
        amount = self._minor(payload["amount_minor"])
        method = payload.get("method", "pix")
        deposit_id = payload.get("deposit_id") or uuid.uuid4().hex
        with self.books.lock:
            key = f"demo:deposit:{player_id}:{deposit_id}"
            if any(p.key == key for p in self.books.postings):
                return {"seq": None, "replayed": True,
                        "available_minor": self.books.available(player_id)}
            today = self._deposited_today(player_id)
            breached = self.limits.breached(deposit_today=today + amount)
            if breached:
                raise ValueError(f"limit breached: {', '.join(breached)}")
            posting = process_deposit(
                self.books, self.exclusions, self.limits,
                player_id, amount, method,
                deposit_today_minor=today, deposit_id=deposit_id,
            )
            self._record_deposit(player_id, amount)
        return {"seq": posting.seq, "replayed": False,
                "available_minor": self.books.available(player_id)}

    def withdraw(self, payload: dict) -> dict:
        player_id = payload["player"]
        profile = self.players.read_all().get(player_id)
        if not profile:
            raise ValueError(f"unknown player: {player_id}")
        stored_key = self.pix_keys.get(player_id) or profile.get("pix_raw")
        if not stored_key:
            raise ValueError("no Pix key registered for this player")
        supplied = (payload.get("pix_key") or "").strip()
        if supplied and normalize(supplied) != normalize(stored_key):
            raise ValueError(
                "payout Pix key must match the key on file "
                "(own-name rule: funds leave only to the registered key)")
        receipt = process_withdrawal(
            self.books, self.exclusions, player_id,
            self._minor(payload["amount_minor"]), stored_key,
            payload.get("payout_id") or uuid.uuid4().hex[:12],
        )
        if receipt is None:
            raise ValueError("duplicate payout_id: already withdrawn")
        receipt["available_minor"] = self.books.available(player_id)
        return receipt

    # -- slot ---------------------------------------------------------
    def spin(self, payload: dict) -> dict:
        player_id = payload["player"]
        game_id = payload["game_id"]
        stake = int(payload["stake_minor"])
        if stake not in STAKE_STEPS:
            raise ValueError(f"stake must be one of {STAKE_STEPS} centavos")
        cert = self.registry.assert_launchable(game_id)  # BR cert gate
        self.exclusions.assert_playable(player_id)
        round_id = payload.get("round_id") or uuid.uuid4().hex[:12]
        if game_id == ROULETTE_GAME_ID:
            # table game: the ball is drawn from the same
            # sha256 discipline, but a table game needs a
            # selection — no selection, no bet (400)
            result = roulette_spin(game_id, round_id,
                                   payload.get("selection"))
            bet_key = f"demo:bet:{round_id}"
            with self.books.lock:
                bonus_part = self._stake_split(player_id, stake)
                self.books.place_bet(bet_key, player_id, stake, result.multiplier
                                     if result.is_win else "2.00",
                                     bonus_part=bonus_part)
                if result.is_win:
                    self.books.settle_bet_win(
                        f"demo:stl:{round_id}", player_id, stake,
                        result.multiplier, bonus_part=bonus_part)
                    payout = int(round(stake * float(result.multiplier)))
                else:
                    self.books.settle_bet_loss(f"demo:stl:{round_id}", player_id,
                                               stake)
                    payout = 0
                self.books.assert_balanced()
                self._record_wager(player_id, stake, f"spin:{round_id}")
        elif game_id in ARCADE_GAME_IDS:
            # arcade originals (crash/plinko/mines): the engine names the
            # exact minor-unit payout — including partial returns below the
            # stake, which the odds-based path cannot express — so the round
            # settles through place_bet + settle_casino. Crash and mines
            # need a selection (target / mines+cells); plinko needs none.
            result = arcade_round(game_id, round_id,
                                  payload.get("selection"), stake)
            bet_key = f"demo:bet:{round_id}"
            with self.books.lock:
                bonus_part = self._stake_split(player_id, stake)
                self.books.place_bet(bet_key, player_id, stake,
                                     result.multiplier
                                     if result.is_win else "2.00",
                                     bonus_part=bonus_part)
                self.books.settle_casino(
                    f"demo:stl:{round_id}", player_id, stake,
                    result.payout_minor, bonus_part=bonus_part)
                payout = result.payout_minor
                self.books.assert_balanced()
                self._record_wager(player_id, stake, f"spin:{round_id}")
        else:
            result = spin(game_id, round_id)
            bet_key = f"demo:bet:{round_id}"
            with self.books.lock:
                bonus_part = self._stake_split(player_id, stake)
                self.books.place_bet(bet_key, player_id, stake, result.multiplier
                                     if result.is_win else "2.00",
                                     bonus_part=bonus_part)
                if result.is_win:
                    self.books.settle_bet_win(
                        f"demo:stl:{round_id}", player_id, stake,
                        result.multiplier, bonus_part=bonus_part)
                    payout = int(round(stake * float(result.multiplier)))
                else:
                    self.books.settle_bet_loss(f"demo:stl:{round_id}", player_id,
                                               stake)
                    payout = 0
                self.books.assert_balanced()
                self._record_wager(player_id, stake, f"spin:{round_id}")
        row = {
            "round_id": round_id, "player": player_id, "game_id": game_id,
            "title": cert.title, "stake_minor": stake,
            "tier": result.tier, "multiplier": result.multiplier,
            "symbols": list(result.symbols), "payout_minor": payout,
            "unit": round(result.unit, 6),  # the actual draw, for audit
            "available_minor": self.books.available(player_id),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self._append_round(row)
        return row

    # -- crash: live (manual cash-out) ---------------------------------

    def _load_crash_pending(self) -> None:
        """Reload live crash rounds after a restart — and void them.

        A round left pending at boot was debited (its stake sits in
        `bet:staked`) but never settled, and we cannot know whether the
        player had cashed out before the process died. The only honest
        outcome is to return the stake: a cancelled round, recorded in
        the ledger, so no money is left stranded.
        """
        try:
            with open(self.crash_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        for token, row in data.items():
            if not isinstance(row, dict):
                continue
            try:
                self._void_crash(token, row)
            except Exception:
                pass  # a torn file must never stop the server booting
        self.crash_pending = {}
        self._save_crash_pending()

    def _save_crash_pending(self) -> None:
        """Persist the in-flight rounds atomically. Best-effort: the
        in-memory dict still drives the sweep if the write fails."""
        try:
            tmp = self.crash_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(self.crash_pending, handle, ensure_ascii=False)
            os.replace(tmp, self.crash_path)
        except OSError:
            pass

    def _void_crash(self, token: str, row: dict) -> None:
        """Refund a debited live round that cannot be completed."""
        player_id = str(row.get("player", ""))
        stake = int(row.get("stake_minor", 0) or 0)
        if not player_id or stake <= 0:
            return
        bet_key = f"demo:crash:{token}"
        if not any(p.key == bet_key for p in self.books.postings):
            return  # nothing was ever staked: nothing to return
        with self.books.lock:
            self.books.settle_casino(
                f"demo:cstl:{token}", player_id, stake, stake,
                bonus_part=int(row.get("bonus_part") or 0))
            self.books.assert_balanced()
        self._append_round({
            "round_id": str(row.get("round_id", token)), "player": player_id,
            "game_id": CRASH_GAME_ID,
            "title": str(row.get("title", "Crash Nitro")),
            "stake_minor": stake, "tier": "voo cancelado",
            "multiplier": "1.00", "symbols": ["cancelado"],
            "payout_minor": stake,
            "available_minor": self.books.available(player_id),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })

    def sweep_crash(self) -> int:
        """Settle live crash rounds the client abandoned (tab closed, or
        the request never came back). Past the bust point the round is a
        loss. Called from the periodic settle paths (POST /api/settle,
        /api/sports, /api/bet) and the heartbeat thread."""
        with self._crash_lock:
            return self._sweep_crash_locked()

    def _sweep_crash_locked(self) -> int:
        now = time.time()
        settled = 0
        for token, row in list(self.crash_pending.items()):
            point = crash_bust_multiplier(CRASH_GAME_ID, str(row["round_id"]))
            if now - float(row["started_at"]) >= crash_elapsed_for(point) + 1.0:
                self._settle_crash(token, row, now - float(row["started_at"]))
                settled += 1
        return settled

    def crash_start(self, payload: dict) -> dict:
        """Open a live crash round: draw the secret bust, debit the stake,
        and hand the client a handle plus the curve, so it can animate the
        climb locally. The bust is never sent until the round settles."""
        player_id = payload["player"]
        stake = int(payload["stake_minor"])
        if stake not in STAKE_STEPS:
            raise ValueError(f"stake must be one of {STAKE_STEPS} centavos")
        cert = self.registry.assert_launchable(CRASH_GAME_ID)  # BR cert gate
        self.exclusions.assert_playable(player_id)
        with self._crash_lock:
            self._sweep_crash_locked()
            if any(r.get("player") == player_id
                   for r in self.crash_pending.values()):
                raise ValueError("você já tem um voo em andamento")
            token = uuid.uuid4().hex[:16]            # public handle
            row = {
                "token": token,
                "round_id": uuid.uuid4().hex[:12],    # secret draw seed
                "player": player_id, "game_id": CRASH_GAME_ID,
                "title": cert.title, "stake_minor": stake,
                "bonus_part": 0, "started_at": time.time(),
            }
            self.crash_pending[token] = row
            try:
                with self.books.lock:
                    bonus_part = self._stake_split(player_id, stake)
                    self.books.place_bet(f"demo:crash:{token}", player_id,
                                         stake, "2.00", bonus_part=bonus_part)
                    self.books.assert_balanced()
            except Exception:
                self.crash_pending.pop(token, None)
                raise
            row["bonus_part"] = bonus_part
            self._save_crash_pending()
        try:
            with self.books.lock:
                self._record_wager(player_id, stake, f"crash:{token}")
        except Exception:
            pass  # turnover accounting is best-effort; the round stands
        return {
            "token": token, "started_at": row["started_at"],
            "server_now": time.time(), "growth": CRASH_GROWTH_PER_SEC,
            "max_multiplier": CRASH_LIVE_MAX, "stake_minor": stake,
            "title": cert.title,
        }

    def crash_status(self, payload: dict) -> dict:
        """Poll one live round. While it flies only the current multiplier
        is returned; once the bust is reached the round settles and the
        secret bust is finally revealed."""
        token = str(payload.get("token") or "")
        with self._crash_lock:
            row = self.crash_pending.get(token)
            if row is None:
                return {"status": "unknown"}
            elapsed = time.time() - float(row["started_at"])
            point = crash_bust_multiplier(CRASH_GAME_ID, str(row["round_id"]))
            if elapsed > crash_elapsed_for(point):
                return self._settle_crash(token, row, elapsed)
            return {"status": "flying",
                    "multiplier": round(min(crash_multiplier_at(elapsed),
                                            CRASH_LIVE_MAX), 4),
                    "elapsed": round(elapsed, 3)}

    def crash_cashout(self, payload: dict) -> dict:
        """Cash out the live round now: pay stake x the multiplier the
        server's clock shows at this instant, or a loss if the curve had
        already busted."""
        token = str(payload.get("token") or "")
        with self._crash_lock:
            row = self.crash_pending.get(token)
            if row is None:
                raise ValueError("voo não encontrado (já finalizado?)")
            elapsed = time.time() - float(row["started_at"])
            return self._settle_crash(token, row, elapsed)

    def _settle_crash(self, token: str, row: dict, elapsed: float) -> dict:
        """Settle one live round. Caller holds ``_crash_lock``."""
        result = crash_live_round(CRASH_GAME_ID, str(row["round_id"]), elapsed,
                                  int(row["stake_minor"]))
        player_id = str(row["player"])
        with self.books.lock:
            self.books.settle_casino(
                f"demo:cstl:{token}", player_id, int(row["stake_minor"]),
                result.payout_minor,
                bonus_part=int(row.get("bonus_part") or 0))
            self.books.assert_balanced()
            self._maybe_convert(player_id, f"crash:{token}")
        final = {
            "round_id": str(row["round_id"]), "player": player_id,
            "game_id": CRASH_GAME_ID,
            "title": str(row.get("title", "Crash Nitro")),
            "stake_minor": int(row["stake_minor"]), "tier": result.tier,
            "multiplier": result.multiplier, "symbols": list(result.symbols),
            "payout_minor": result.payout_minor, "unit": round(result.unit, 6),
            "available_minor": self.books.available(player_id),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self._append_round(final)
        self.crash_pending.pop(token, None)
        self._save_crash_pending()
        bust = crash_bust_multiplier(CRASH_GAME_ID, str(row["round_id"]))
        return {
            "status": "cashed" if result.is_win else "busted",
            "win": result.is_win,
            "multiplier": float(result.multiplier) if result.is_win else 0.0,
            "bust": round(bust, 2), "payout_minor": result.payout_minor,
            "tier": result.tier, "round_id": final["round_id"],
            "stake_minor": final["stake_minor"],
            "available_minor": final["available_minor"],
        }

    def bet(self, payload: dict) -> dict:
        player_id = payload["player"]
        legs = payload.get("legs")
        if legs is not None:
            if not isinstance(legs, list) or not (1 <= len(legs) <= 12):
                raise ValueError("legs must be a list of 1..12 picks")
            validated = []
            total_price = 1.0
            for leg in legs:
                fk = str(leg.get("fixture_key", "")).strip()
                sel = str(leg.get("selection", "")).strip()
                if not fk or not sel:
                    raise ValueError("each leg needs fixture_key and selection")
                try:
                    p = float(leg["price"])
                except (KeyError, TypeError, ValueError):
                    raise ValueError("each leg price must be numeric") from None
                if not (1.01 <= p <= 1000.0):
                    raise ValueError("leg price out of range (1.01..1000)")
                total_price *= p
                validated.append({**leg, "price": p})
            fixture_key = "express:" + "+".join(str(l["fixture_key"]) for l in validated)
            selection = " / ".join(str(l["selection"]) for l in validated)
            market_kind = "Express" if len(validated) > 1 else str(validated[0].get("market_kind", "1x2"))
            price = round(total_price, 2)
            payload = {
                **payload,
                "fixture_key": fixture_key, "selection": selection,
                "price": price, "market_kind": market_kind,
                "home": validated[0].get("home", "?"),
                "away": f"{len(validated)} seleções" if len(validated) > 1 else validated[0].get("away", "?"),
            }
        else:
            fixture_key = str(payload.get("fixture_key", "")).strip()
            selection = str(payload.get("selection", "")).strip()
            if not fixture_key or not selection:
                raise ValueError("fixture_key and selection are required")
            try:
                price = float(payload["price"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("price must be numeric") from None
            if not (1.01 <= price <= 1000.0):
                raise ValueError("price out of range (1.01..1000)")
        stake = self._minor(int(payload["stake_minor"]))
        self.exclusions.assert_playable(player_id)
        bet_id = payload.get("bet_id") or uuid.uuid4().hex[:12]
        wallet_key = f"demo:spbet:{player_id}:{bet_id}"
        with self.books.lock:
            if any(p.key == wallet_key for p in self.books.postings):
                raise ValueError("duplicate bet_id")
            digest = hashlib.sha256(
                f"{fixture_key}|{selection}|{bet_id}".encode("utf-8")
            ).hexdigest()
            unit = int(digest[:8], 16) / 0xFFFFFFFF
            bonus_part = self._stake_split(player_id, stake)
            self.books.place_bet(wallet_key, player_id, stake, f"{price:.2f}",
                                 bonus_part=bonus_part)
            self.books.assert_balanced()
            self._record_wager(player_id, stake, f"bet:{bet_id}")
        row = {
            "round_id": bet_id, "player": player_id, "game_id": fixture_key,
            "title": f"{payload.get('home','?')} × {payload.get('away','?')} — {payload.get('market_kind','')}: {selection}",
            "stake_minor": stake, "tier": "pendente", "multiplier": f"{price:.2f}",
            "symbols": [], "payout_minor": 0,
            "unit": round(unit, 6),
            "available_minor": self.books.available(player_id),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "type": "sports", "price": round(price, 2), "selection": selection,
        }
        self._append_round(row)
        return row

    def settle_pending(self, settle_delay_seconds: int = 45) -> list[dict]:
        """Settle open sports bets once their simulated result is due.

        Mirrors a real feed: the bet's stake sits in `bet:staked` from
        placement; settlement posts win/loss exactly once per bet_id and
        appends a final row (same round_id) to the rounds log. Callers:
        every /api/sports refresh, every /api/bet, and POST /api/settle.
        Also drains any abandoned live crash round (sweep_crash).
        """
        self.sweep_crash()
        rows = []
        try:
            with open(self.rounds_path, "r", encoding="utf-8") as handle:
                rows = [json.loads(l) for l in handle if l.strip()]
        except FileNotFoundError:
            return []
        settled_ids = {
            r["round_id"] for r in rows
            if r.get("type") == "sports" and r.get("tier") != "pendente"
        }
        out = []
        now = datetime.now(timezone.utc)
        for r in rows:
            if r.get("type") != "sports" or r.get("tier") != "pendente":
                continue
            if r["round_id"] in settled_ids:
                continue
            try:
                ts = datetime.fromisoformat(str(r["ts"]).replace("Z", "+00:00"))
            except ValueError:
                continue
            if (now - ts).total_seconds() < settle_delay_seconds:
                continue
            price = float(r["price"])
            win = float(r["unit"]) < (1.0 / price)
            stake = int(r["stake_minor"])
            player_id = r["player"]
            with self.books.lock:
                # the stake's bonus portion is whatever the journal recorded
                # at placement: a restart must not forget it
                bonus_part = 0
                bet_key = f"demo:spbet:{player_id}:{r['round_id']}"
                for posting in self.books.postings:
                    if posting.key == bet_key:
                        bonus_part = int(
                            posting.metadata.get("bonus_part") or 0)
                        break
                if win:
                    self.books.settle_bet_win(
                        f"demo:spstl:{player_id}:{r['round_id']}", player_id,
                        stake, f"{price:.2f}", bonus_part=bonus_part)
                    payout = int(round(stake * price))
                    tier = "vitoria"
                else:
                    self.books.settle_bet_loss(
                        f"demo:spstl:{player_id}:{r['round_id']}", player_id, stake)
                    payout = 0
                    tier = "derrota"
                self.books.assert_balanced()
                # a bonus-staked win pays part of its payout back into
                # player:bonus; release it only if no requirement owns it
                self._maybe_convert(player_id, f"stl:{r['round_id']}")
            final = dict(r)
            final.update(
                tier=tier, payout_minor=payout,
                available_minor=self.books.available(player_id),
                ts=now.isoformat(timespec="seconds"),
            )
            if self._append_round(final):
                out.append(final)
                settled_ids.add(r["round_id"])
        return out

    def _append_round(self, row: dict) -> bool:
        """Append the round record. Failure is reported, never swallowed:
        a settled bet whose record was lost can never be retried, because the
        wallet already refuses the duplicate posting."""
        try:
            with open(self.rounds_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            return True
        except OSError as exc:
            self.orphan_rounds.append({**row, "record_error": str(exc)})
            return False

    def catalog(self) -> list[dict]:
        out = []
        for cert in self.registry.all():
            # arcade originals render their own panels with their own
            # tables (targets/slots/mines vary per round), so they carry
            # no static paytable; slots keep theirs.
            paytable = [] if cert.game_id in ARCADE_GAME_IDS else [
                {"name": t.name, "multiplier": t.multiplier,
                 "symbols": list(t.symbols)}
                for t in reversed(tiers_for(cert.game_id))
                if float(t.multiplier) > 0
            ]
            out.append({
                "game_id": cert.game_id, "provider": cert.provider,
                "title": cert.title, "rtp": cert.rtp,
                "certificate_id": cert.certificate_id or "—",
                "launchable": cert.launchable,
                "demo_rtp": DEMO_RTP_STR,
                "category": DEMO_CATEGORY.get(cert.game_id, "Originais"),
                "paytable": paytable,
            })
        return out

    def provider_demos(self) -> dict:
        """Publisher-hosted free-play demos: the vendor's own bytes, their
        hosting. Wallet-isolated and never launchable against our books, so
        nothing here can move a centavo. Facts come from
        `probes/provider-demos.json` through the https + host-allowlist loader.
        """
        return provider_demos.load()

    def vendor_catalog(self) -> dict:
        """Vendor titles are visible but never launchable until their real
        BR certificates are registered. One live aggregator, never two.

        Without credentials, `DEMO_VENDOR_FIXTURE` may point at a captured
        public-title sample (see probes/vendor-titles.json): provider names
        and source URLs only, no RTP invented, every row forced non-launchable.
        A misconfigured fixture degrades to an error status, never a 500.
        """
        if self.vendor is not None:
            try:
                games = self.vendor.catalogue()
            except AggregatorError as exc:
                return {"status": f"error: {exc}", "games": []}
            return {
                "status": f"ok ({self.vendor.config.vendor}, "
                          f"{len(games)} titles, none launchable before BR certs)",
                "games": [
                    {"game_id": g.get("game_id"), "provider": g.get("provider"),
                     "title": g.get("title"), "rtp": g.get("rtp"),
                     "launchable": False,
                     "category": g.get("category") or "Originais",
                     "note": "pending BR certificate registration"}
                    for g in games if isinstance(g, dict)
                ],
            }
        fixture_path = os.environ.get("DEMO_VENDOR_FIXTURE", "").strip()
        if fixture_path:
            return fixture_catalog(fixture_path)
        return {"status": "unconfigured (stub serves demo titles)",
                "games": []}
    def _all_rounds(self) -> list[dict]:
        """Parse every round once, quarantining torn lines.

        One truncated write used to raise JSONDecodeError out of both history
        and risk, killing the account page for every player with no repair.
        """
        if not os.path.exists(self.rounds_path):
            return []
        rows: list[dict] = []
        with open(self.rounds_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue  # torn tail line: skip, keep serving
                if isinstance(row, dict):
                    rows.append(row)
        return rows

    def history(self, player_id: str, limit: int = 20) -> list[dict]:
        latest: dict[str, dict] = {}
        order: list[str] = []
        for r in self._all_rounds():
            if r.get("player") != player_id:
                continue
            key = str(r.get("round_id", id(r)))
            if key not in latest:
                order.append(key)
            latest[key] = r
        return [latest[k] for k in order][-limit:]

    def record_play(self, body: dict) -> dict:
        """One open of a game. Presentation activity, never money:
        nothing here touches the books. Official iframe demos leave no
        round posting, but opening one still counts for the hot/cold
        board, so the lobby knows what players actually open."""
        gid = str(body.get("game_id", "")).strip()
        if not gid or len(gid) > 120:
            raise ValueError("game_id required")
        row = {
            "game_id": gid,
            "player": str(body.get("player", ""))[:64],
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        try:
            with open(self.plays_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass  # the board degrades; no money may depend on this file
        return {"recorded": True, "game_id": gid}

    def trending(self) -> dict:
        """Hot/cold board over the last 24h: an open (record_play) or a
        recorded round counts as one activity for the game. Hot lists the
        most active catalog games; cold lists catalog games with zero
        activity in the window. Only known catalog game_ids are counted —
        garbage lines never leak into the board."""
        now = datetime.now(timezone.utc)
        known = {g["game_id"] for g in self.catalog()}
        known.update(d.get("game_id") for d in self.provider_demos().get("demos", []))
        known.discard(None)

        def _recent(path: str):
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue  # torn tail line: skip, keep serving
                    try:
                        at = datetime.fromisoformat(
                            str(row.get("ts", "")).replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if now - at > timedelta(hours=24):
                        continue
                    gid = row.get("game_id")
                    if isinstance(gid, str) and gid in known:
                        yield gid

        opens: dict[str, int] = {}
        for gid in _recent(self.plays_path):
            opens[gid] = opens.get(gid, 0) + 1
        rounds: dict[str, int] = {}
        for gid in _recent(self.rounds_path):
            rounds[gid] = rounds.get(gid, 0) + 1
        active = set(opens) | set(rounds)
        ranked = sorted(
            active,
            key=lambda g: (opens.get(g, 0) + rounds.get(g, 0), rounds.get(g, 0)),
            reverse=True,
        )
        return {
            "window_hours": 24,
            "hot": [
                {"game_id": g, "opens": opens.get(g, 0), "rounds": rounds.get(g, 0)}
                for g in ranked[:8]
            ],
            "cold": sorted(known - active)[:8],
        }

    def news(self) -> dict:
        """News panel = real facts the server already knows. No static
        marketing copy: every item derives from the live catalog, the
        last fixture capture, today's activity board, or today's ledger."""
        items = []
        demos = self.provider_demos().get("demos", [])
        if demos:
            providers = sorted({d.get("provider", "?") for d in demos})
            items.append({
                "tag": "CASSINO",
                "title": f"{len(demos)} jogos oficiais de {len(providers)} provedor(es) incorporados direto no site",
            })
        live = sports_data.load_live()
        if live:
            items.append({
                "tag": "ESPORTE",
                "title": f"Fixtures esportivos capturados em {live.get('fetched_at', 'data desconhecida')}",
            })
        titles: dict[str, str] = {}
        for g in self.catalog():
            titles[g["game_id"]] = str(g.get("title", g["game_id"]))
        for d in self.provider_demos().get("demos", []):
            d.setdefault("title", d.get("game_id", "?"))
            titles[d["game_id"]] = str(d["title"])
        board = self.trending()
        if board["hot"]:
            top = board["hot"][0]
            items.append({
                "tag": "ALTA",
                "title": f"Mais jogado (24h): {titles.get(top['game_id'], top['game_id'])} — {top['opens']} abre(s), {top['rounds']} rodada(s)",
            })
        torneios = self.tournaments()
        wins = next((b["rows"] for b in torneios["boards"] if b["key"] == "biggest_win" and b["rows"]), [])
        if wins:
            amount = f"{wins[0]['value_minor'] / 100:,.2f}".replace(",", "\u00a7").replace(".", ",").replace("\u00a7", ".")
            items.append({"tag": "PRÊMIO", "title": f"Maior ganho de hoje: R$ {amount}"})
        items.append({
            "tag": "PROMOÇÕES",
            "title": "Bônus de boas-vindas e cashback diário ativos — aba Promoções",
        })
        return {"items": items}

    def jackpot(self) -> dict:
        """Progressive pool, honestly tied to volume: a fixed seed pool
        plus 1% of today's recorded stakes from the round ledger. The
        lobby ticker no longer walks at random — it moves when real
        rounds land."""
        today = datetime.now(timezone.utc).date().isoformat()
        volume = 0
        for row in self._all_rounds():
            if not str(row.get("ts", "")).startswith(today):
                continue
            try:
                volume += int(row.get("stake_minor", 0) or 0)
            except (TypeError, ValueError):
                continue
        share = volume // 100
        return {
            "pool_minor": 284719450 + share,
            "share_percent": 1,
            "volume_today_minor": volume,
            "note": "1% das apostas do dia alimenta o pote progressivo simulado",
        }

    def chat(self, body: dict) -> dict:
        """Triage bot with canned intents — an honest simulation of a
        support widget. Replies are assembled from real catalog facts
        and the real promo mechanics; nothing is persisted."""
        msg = str(body.get("message", "")).lower()
        demos = self.provider_demos().get("demos", [])
        n_providers = len({d.get("provider") for d in demos})
        if any(k in msg for k in ("saque", "sacar", "retirada", "sacar via")):
            return {"bot": "casa-demo", "reply": "Saques demo chamam Caixa → Sacar: o dinheiro vai na hora para a chave PIX que consta na sua conta, cujo titular precisa ser você mesmo."}
        if any(k in msg for k in ("deposito", "depósito", "pix", "carga", "carregar")):
            return {"bot": "casa-demo", "reply": "Depósito demo via PIX cai na hora: Caixa → Depositar → valor → confirmar. Se for o primeiro, use no mínimo R$20 para liberar o bônus de boas-vindas."}
        if any(k in msg for k in ("bonus", "bônus", "promo", "cashback", "boas-vindas")):
            return {"bot": "casa-demo", "reply": "Promoções ativas de verdade: bônus de boas-vindas (100% do 1º depósito até R$500, rollover 20x) e cashback diário de 10% até R$200. O progresso ao vivo fica na aba Promoções."}
        if any(k in msg for k in ("limite", "exclusao", "exclusão", "autoexclusao", "jogo seguro")):
            return {"bot": "casa-demo", "reply": "Em Minha Conta → Responsabilidade você configura limites de depósito diário e pode se autoexcluir quando quiser."}
        if any(k in msg for k in ("jogo", "slot", "aviator", "crash", "roleta", "roulette", "mesa", "pragmatic", "spribe", "hacksaw", "play'n", "evolution", "book of")):
            return {"bot": "casa-demo", "reply": f"Catálogo com {len(demos)} jogos oficiais de {n_providers} provedor(es), incorporados direto no site com saldo virtual. Filtre por categoria nos chips acima."}
        if any(k in msg for k in ("ola", "olá", "oi ", "oi", "bom dia", "boa tarde", "boa noite", "hey", "eai", "e aí")):
            return {"bot": "casa-demo", "reply": "Olá! Pergunte-me sobre depósitos, saques, bônus, limites ou jogos."}
        return {"bot": "casa-demo", "reply": "Posso ajudar com depósitos, saques, bônus e promoções, limites/autoexclusão e o catálogo de jogos. O que deseja saber?"}

    def tournaments(self) -> dict:
        """No organized tournaments exist in the demo — what exists is the
        day's round ledger. This is a leaderboard over today's (UTC)
        rounds: biggest single payout and most active wallet, both
        computed from the same append-only store the history view reads.
        Rows say what they are; no fabricated prize pool."""
        today = datetime.now(timezone.utc).date().isoformat()
        names: dict[str, str] = {}
        for pid, row in self.players.read_all().items():
            if isinstance(row, dict):
                names[pid] = str(row.get("name", "") or pid)
        best_wins: dict[str, int] = {}
        rounds_today: dict[str, int] = {}
        for row in self._all_rounds():
            if not str(row.get("ts", "")).startswith(today):
                continue
            pid = str(row.get("player", ""))
            if not pid:
                continue
            rounds_today[pid] = rounds_today.get(pid, 0) + 1
            payout = row.get("payout_minor", 0)
            try:
                payout = int(payout)
            except (TypeError, ValueError):
                continue
            if payout > 0:
                best_wins[pid] = max(best_wins.get(pid, 0), payout)
        top_wins = sorted(best_wins.items(), key=lambda kv: kv[1], reverse=True)[:3]
        top_active = sorted(rounds_today.items(), key=lambda kv: kv[1], reverse=True)[:3]
        return {
            "day": today,
            "note": "Calculado das rodadas reais de hoje (cassino in-house + apostas esportivas). Torneios organizados não existem no demo.",
            "boards": [
                {
                    "key": "biggest_win",
                    "title": "Maior Ganho (hoje)",
                    "rows": [
                        {"label": names.get(pid, pid), "value_minor": v}
                        for pid, v in top_wins
                    ],
                },
                {
                    "key": "most_active",
                    "title": "Mais Rodadas (hoje)",
                    "rows": [
                        {"label": names.get(pid, pid), "value": n}
                        for pid, n in top_active
                    ],
                },
            ],
        }

    def live(self) -> dict:
        """Real-time casino pulse — every figure from files the
        server already keeps. Who is opening games right now
        (15-minute window on the plays log), the newest
        recorded wins (round ledger, names masked like a
        casino floor ticker), and the current jackpot pool.
        No fabricated crowd: an empty lobby reports zero."""
        now = datetime.now(timezone.utc)
        window = timedelta(minutes=15)
        opens: dict[str, int] = {}
        players: set[str] = set()
        if os.path.exists(self.plays_path):
            with open(self.plays_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                        at = datetime.fromisoformat(
                            str(row.get("ts", "")).replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        continue  # torn line: skip, never crash the pulse
                    if now - at > window:
                        continue
                    gid = row.get("game_id")
                    if isinstance(gid, str) and gid:
                        opens[gid] = opens.get(gid, 0) + 1
                        if row.get("player"):
                            players.add(str(row["player"]))
        titles: dict[str, str] = {}
        for g in self.catalog():
            titles[g["game_id"]] = str(g.get("title", g["game_id"]))
        for d in self.provider_demos().get("demos", []):
            titles[d["game_id"]] = str(d.get("title") or d["game_id"])
        names: dict[str, str] = {}
        for pid, row in self.players.read_all().items():
            if isinstance(row, dict):
                names[pid] = str(row.get("name", "") or pid)
        wins: list[dict] = []
        for row in reversed(self._all_rounds()):
            try:
                payout = int(row.get("payout_minor") or 0)
            except (TypeError, ValueError):
                continue
            if payout <= 0:
                continue
            pid = str(row.get("player", ""))
            gid = str(row.get("game_id", ""))
            wins.append({
                "label": _mask_name(names.get(pid, pid)),
                "game_id": gid,
                "title": titles.get(gid, gid),
                "payout_minor": payout,
                "ts": str(row.get("ts", "")),
            })
            if len(wins) >= 10:
                break
        return {
            "generated_at": now.isoformat(timespec="seconds"),
            "window_minutes": 15,
            "active_players": len(players),
            "active_games": [
                {"game_id": g, "title": titles.get(g, g), "opens": n}
                for g, n in sorted(opens.items(),
                                   key=lambda kv: kv[1], reverse=True)
            ],
            "latest_wins": wins,
            "jackpot_pool_minor": self.jackpot()["pool_minor"],
        }

    # ---- painel administrativo: credentials & sessions ----
    def auth_login(self, body: dict) -> dict:
        """Exchange credentials for a bearer session. A failed attempt
        pays a fixed delay so the panel cannot be brute-forced in a
        tight loop."""
        username = str(body.get("username", "")).strip().lower()
        try:
            role = self.users.authenticate(username, body.get("password", ""))
        except AuthError:
            time.sleep(0.25)
            raise
        token = self.sessions.issue(username, role)
        return {"token": token, "username": username, "role": role}

    def auth_me(self, token: str) -> dict:
        return self.sessions.check(token)

    def auth_logout(self, token: str) -> dict:
        self.sessions.check(token)
        self.sessions.revoke(token)
        return {"logged_out": True}

    def auth_change_password(self, token: str, body: dict) -> dict:
        session = self.sessions.check(token)
        # the current password must still work before a new one lands
        self.users.authenticate(session["username"],
                                str(body.get("current", "")))
        self.users.set_password(session["username"], body.get("new", ""))
        # every session for this user dies (including this one), then the
        # caller reissues: a password change must kill old credentials
        self.sessions.revoke_user(session["username"])
        fresh = self.sessions.issue(session["username"], session["role"])
        # persist the new session set so the next boot keeps this admin
        # logged in (restart no longer boots everyone out)
        self._save_sessions()
        return {"token": fresh, "username": session["username"],
                "role": session["role"], "changed": True}

    def _require_admin(self, token: str) -> dict:
        session = self.sessions.check(token)
        if session.get("role") != "admin":
            raise AuthError("perfil sem permissão para gerenciar usuários")
        return session

    def admin_users(self, token: str) -> dict:
        """List panel accounts (never salt/hash)."""
        self._require_admin(token)
        return {"users": self.users.list_users()}

    def admin_create_user(self, token: str, body: dict) -> dict:
        self._require_admin(token)
        user = self.users.create(str(body.get("username", "")),
                                 body.get("password", ""),
                                 str(body.get("role", "viewer")))
        return {"created": user}

    def admin_reset_password(self, token: str, body: dict) -> dict:
        admin = self._require_admin(token)
        target = str(body.get("username", "")).strip().lower()
        self.users.set_password(target, body.get("new", ""))
        # the old credential must stop working immediately
        self.sessions.revoke_user(target)
        self._save_sessions()
        return {"reset": target, "by": admin["username"]}

    def admin_delete_user(self, token: str, body: dict) -> dict:
        admin = self._require_admin(token)
        target = str(body.get("username", "")).strip().lower()
        self.users.delete(target, by=admin["username"])
        self.sessions.revoke_user(target)
        self._save_sessions()
        return {"deleted": target}

    def admin_player_dashboard(self, token: str, player_id: str) -> dict:
        """Per-player drill-down for the painel: a human-facing summary of
        one account drawn from the same stores the rest of the demo uses.
        Nothing here is fabricated — balance from the books, history from
        the round ledger, turnover and RTP from the same settled rows the
        aggregate dashboard already counts."""
        admin = self._require_admin(token)
        data = self.players.read_all()
        if player_id not in data:
            raise AuthError("jogador não encontrado")
        profile = dict(data[player_id])
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        rounds = self.history(player_id, limit=10000)
        settled = [r for r in rounds if str(r.get("tier", "")) != "pendente"]
        stake_all = sum(int(r.get("stake_minor", 0) or 0) for r in settled)
        payout_all = sum(int(r.get("payout_minor", 0) or 0) for r in settled)
        stake_day = payout_day = 0
        for r in settled:
            if str(r.get("ts", ""))[:10] == today:
                stake_day += int(r.get("stake_minor", 0) or 0)
                payout_day += int(r.get("payout_minor", 0) or 0)
        with self.books.lock:
            deposits = 0
            for p in self.books.postings:
                if p.kind == "deposit" and p.metadata.get("player") == player_id:
                    deposits += sum(a for acc, a in p.legs if acc == PLAYER_BALANCE)
        risk = self.risk(player_id)
        wins = sum(1 for r in rounds if int(r.get("payout_minor", 0) or 0) > 0)
        return {
            "by": admin["username"],
            "viewed_at": now.isoformat(timespec="seconds"),
            "player": {
                "player_id": player_id,
                "name": str(profile.get("name", "")),
                "cpf_masked": str(profile.get("cpf_masked", "")),
                "pix_masked": str(profile.get("pix_masked", "")),
                "pix_kind": str(profile.get("pix_kind", "")),
                "updated_at": str(profile.get("updated_at", "")),
            },
            "balance": {
                "available_minor": self.books.available(player_id),
                "bonus_minor": self.books.bonus_available(player_id),
                "deposits_minor": deposits,
                "first_deposit_minor": (
                    int(self._deposit_amounts(player_id)[0])
                    if self._deposit_amounts(player_id)
                    else 0),
            },
            "activity": {
                "rounds_total": len(rounds),
                "rounds_today": sum(
                    1 for r in rounds
                    if str(r.get("ts", ""))[:10] == today),
                "wins_total": wins,
                "settled_stake_minor": stake_all,
                "settled_payout_minor": payout_all,
                "settled_rtp_percent": (
                    round(payout_all / stake_all * 100, 2)
                    if stake_all
                    else None),
                "settled_rtp_today_percent": (
                    round(payout_day / stake_day * 100, 2)
                    if stake_day
                    else None),
                "pending_sports": sum(
                    1 for r in rounds
                    if str(r.get("tier", "")) == "pendente"
                    and str(r.get("type", "")) == "sports"),
            },
            "flags": risk["flags"],
            "flagged": risk["flagged"],
            "latest": [
                {
                    "round_id": str(r.get("round_id", "")),
                    "game_id": str(r.get("game_id", "")),
                    "title": str(r.get("title", "")),
                    "stake_minor": int(r.get("stake_minor", 0) or 0),
                    "payout_minor": int(r.get("payout_minor", 0) or 0),
                    "tier": str(r.get("tier", "") or ""),
                    "type": str(r.get("type", "") or ""),
                    "market_kind": str(r.get("market_kind", "") or ""),
                    "selection": str(r.get("selection", "") or ""),
                    "ts": str(r.get("ts", "")),
                }
                for r in rounds[-12:]
            ],
        }

    def admin_dashboard(self, token: str) -> dict:
        """Painel administrativo: every figure derived from the stores the
        demo already keeps — round ledger, double-entry books, players
        file. An admin view is where a demo is most tempted to invent
        numbers, so nothing here is fabricated or extrapolated: RTP is a
        ratio of recorded stakes/payouts, leaderboards are ranked from
        real rows, and the day series is bucketed from row timestamps."""
        self.sessions.check(token)  # hidden from anonymous callers
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        names: dict[str, str] = {}
        for pid, row in self.players.read_all().items():
            if isinstance(row, dict):
                names[pid] = str(row.get("name", "") or pid)

        # latest row per round_id — a settled row replaces its pending
        # twin, exactly like history(), so nothing is counted twice
        latest: dict[str, dict] = {}
        order: list[str] = []
        for r in self._all_rounds():
            key = str(r.get("round_id", id(r)))
            if key not in latest:
                order.append(key)
            latest[key] = r
        rounds = [latest[k] for k in order]

        def as_int(value, default=0):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        series: dict[str, dict] = {}
        for offset in range(6, -1, -1):
            day = (now - timedelta(days=offset)).date().isoformat()
            series[day] = {"day": day, "stake_minor": 0,
                           "payout_minor": 0, "rounds": 0}

        stake_all = payout_all = 0
        stake_day = payout_day = 0
        rounds_today = pending_sports = 0
        net_by_player: dict[str, dict] = {}
        biggest: list[dict] = []
        for r in rounds:
            stake = as_int(r.get("stake_minor"))
            payout = as_int(r.get("payout_minor"))
            pending = str(r.get("tier", "")) == "pendente"
            sports = str(r.get("type", "")) == "sports"
            if pending and sports:
                pending_sports += 1
            day = str(r.get("ts", ""))[:10]
            is_today = day == today
            if is_today:
                rounds_today += 1
            if not pending:
                if day in series:
                    series[day]["stake_minor"] += stake
                    series[day]["payout_minor"] += payout
                    series[day]["rounds"] += 1
                if not sports:
                    # realized RTP compares like with like: settled
                    # in-house rounds only (odds-priced sports would
                    # dilute a ratio meant against the 95.90% model)
                    stake_all += stake
                    payout_all += payout
                    if is_today:
                        stake_day += stake
                        payout_day += payout
                # leaderboards count settled rounds only: a pending
                # stake is not a loss until it settles
                pid = str(r.get("player", ""))
                label = names.get(pid, pid) if pid else "(sem jogador)"
                entry = net_by_player.setdefault(pid or "(demo)",
                                                 {"label": label,
                                                  "net_minor": 0,
                                                  "rounds": 0,
                                                  "wins": 0})
                entry["rounds"] += 1
                entry["net_minor"] += payout - stake
                if payout > 0:
                    entry["wins"] += 1
                    biggest.append({"label": label, "payout_minor": payout,
                                    "game_id": str(r.get("game_id", "")),
                                    "day": day})

        ranked = sorted(net_by_player.items(),
                        key=lambda kv: kv[1]["net_minor"], reverse=True)
        top_winners = [dict(pid=k, **v) for k, v in ranked[:5]]
        biggest.sort(key=lambda w: w["payout_minor"], reverse=True)

        with self.books.lock:
            deposits = withdrawn = paid = 0
            for p in self.books.postings:
                if p.kind == "deposit":
                    deposits += sum(a for acc, a in p.legs
                                    if acc == PLAYER_BALANCE)
                elif p.kind == "withdraw":
                    withdrawn += -sum(a for acc, a in p.legs
                                      if acc == PLAYER_BALANCE)
                elif p.kind == "withdrawal_paid":
                    paid += -sum(a for acc, a in p.legs
                                 if acc == PAYABLE_PLAYER)
            operator_cash = self.books.balance(OPERATOR_CASH)
            player_liab = self.books.balance(PLAYER_BALANCE)
            bonus_liab = self.books.balance(PLAYER_BONUS)
            pending_withdrawals = self.books.balance(PAYABLE_PLAYER)
            ggr = self.books.balance(GGR_REVENUE)
            turnover = sum(p.metadata.get("stake", 0)
                           for p in self.books.postings
                           if p.kind == "bet_placed")

        flagged = 0
        for pid in self.players.read_all():
            if self.risk(pid)["flagged"]:
                flagged += 1

        jack = self.jackpot()
        health = self.health_report()
        return {
            "generated_at": now.isoformat(timespec="seconds"),
            "day": today,
            "note": ("Painel administrativo do demo — todo número deriva do "
                     "livro de rodadas, dos livros duplos e do cadastro de "
                     "jogadores; nada é simulado ou extrapolado."),
            "totals": {
                "players": len(self.players.read_all()),
                "rounds": len(rounds),
                "rounds_today": rounds_today,
                "deposits_minor": deposits,
                "withdrawals_minor": withdrawn,
                "withdrawals_paid_minor": paid,
                "withdrawals_pending_minor": pending_withdrawals,
                "ggr_minor": ggr,
                "operator_cash_minor": operator_cash,
                "player_liability_minor": player_liab,
                "bonus_liability_minor": bonus_liab,
            },
            "returns": {
                "rtp_percent": (round(payout_all / stake_all * 100, 2)
                                if stake_all else None),
                "rtp_today_percent": (round(payout_day / stake_day * 100, 2)
                                       if stake_day else None),
                "model_rtp_percent": round(float(DEMO_RTP_STR), 2),
                "turnover_minor": turnover,
                "turnover_today_minor": jack["volume_today_minor"],
            },
            "day_series": list(series.values()),
            "top_winners": top_winners,
            "biggest_wins": biggest[:5],
            "pending_sports": pending_sports,
            "risk": {"flagged_players": flagged},
            "jackpot": jack,
            "health": health["status"],
        }

    def sports_showcase(self) -> dict:
        """Sports window: real fixtures from ESPN, Superbet as the
        fallback source, deterministic slate as the last resort.
        Prices always come from the in-house deterministic model."""
        from frame.verticals.sports.espn_engine import EspnSportsEngine
        from frame.verticals.sports.superbet_engine import SuperbetSportsEngine
        sources = [
            (EspnSportsEngine, "espn", "ESPN scoreboard + in-house model",
             "fixtures reais via ESPN; cotações geradas pelo motor próprio "
             "(modelo determinístico); não é direito oficial"),
            (SuperbetSportsEngine, "superbet", "Superbet events + in-house model",
             "fixtures reais via Superbet; cotações geradas pelo motor "
             "próprio (modelo determinístico); não é direito oficial"),
        ]
        for factory, source, provider, note in sources:
            try:
                engine = factory()
                fixtures = []
                for fix in engine.fixtures():
                    markets = []
                    for m in engine.markets(fix.key):
                        markets.append({
                            "key": m.key, "kind": m.kind,
                            "selections": list(m.selections),
                            "prices": list(m.prices),
                            "provider": provider, "line": None,
                        })
                    fixtures.append({
                        "key": fix.key, "competition": fix.competition,
                        "home": fix.home, "away": fix.away,
                        "kickoff": fix.kickoff_date,
                        "status": _sports_status(fix.kickoff_date, fix.sport),
                        "markets": markets,
                    })
                if fixtures:
                    return {
                        "fixtures": fixtures, "source": source,
                        "provider": provider, "licensed_feed": False,
                        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "errors": [], "note": note,
                    }
            except Exception:
                continue
        return odds_engine.build()

    def risk(self, player_id: str) -> dict:
        """All rounds on file feed the in-house flags (velocity, spikes,
        loss-chase, RTP drift, duplicates)."""
        report = evaluate_player(player_id, self._all_rounds(),
                                 float(DEMO_RTP_STR) / 100.0,
                                 RiskPolicy())
        return {"flagged": report.flagged, "flags": report.flags,
                "stats": report.stats}

    # ---- publisher-game wallet: the operator side of the money path ----
    # A publisher demo runs its own client and RGS. A launch binds a session
    # token to one player; the stake and the win it reports settle through the
    # books, so the player's saldo is OUR saldo. An empty saldo blocks the
    # spin with a deposit message instead of letting the game play for free.
    WALLET_MIN_STAKE = 200  # R$2 — the smallest stake step

    def _wallet_session(self, token: str) -> dict:
        session = self.wallet_tokens.get(str(token or ""))
        if not session:
            raise KeyError("invalid or expired session token")
        return session

    def _wallet_view(self, player_id: str) -> dict:
        balance = self.books.available(player_id)
        bonus = self.books.bonus_available(player_id)
        can_play = (balance + bonus) >= self.WALLET_MIN_STAKE
        return {
            "balance_minor": balance, "bonus_minor": bonus,
            "min_stake_minor": self.WALLET_MIN_STAKE, "can_play": can_play,
            "message": "" if can_play else
                       "Saldo insuficiente — deposite para girar.",
        }

    def wallet_launch(self, payload: dict) -> dict:
        """Open a wallet session for one publisher game and report whether the
        player can afford the smallest stake."""
        player_id = payload["player"]
        game_id = str(payload.get("game_id") or "").strip()
        if player_id not in self.players.read_all():
            raise KeyError(f"unknown player: {player_id}")
        demos = {d["game_id"] for d in self.provider_demos().get("demos", [])}
        if game_id not in demos:
            raise ValueError(f"unknown publisher game: {game_id}")
        token = uuid.uuid4().hex
        self.wallet_tokens[token] = {
            "player": player_id, "game_id": game_id,
            "issued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        return {"token": token, "game_id": game_id,
                "issued_at": self.wallet_tokens[token]["issued_at"],
                **self._wallet_view(player_id)}

    def rgs_bind(self, provider: str, session_uuid: str, token: str) -> None:
        """Follow a session by the id the RGS handed back.

        Only the first call carries our token; everything after it
        is named by this id, so the money can still be tracked to
        the right wallet.
        """
        if provider and session_uuid and token:
            self.rgs_sessions[(provider, session_uuid)] = token

    def rgs_token(self, provider: str, session_uuid: str) -> str:
        """The wallet token behind an RGS session id, or ""."""
        return self.rgs_sessions.get((provider, session_uuid), "")

    def rgs_open_round(self, provider: str, session_uuid: str,
                       stake: int) -> dict:
        """Open the round a session is staking on, or add to it."""
        entry = self.rgs_rounds.setdefault(
            (provider, session_uuid), {"stake": 0, "win": 0})
        entry["stake"] += stake
        return entry

    def rgs_note_win(self, provider: str, session_uuid: str, win: int) -> dict:
        """Remember the win a round has accumulated so far."""
        entry = self.rgs_rounds.setdefault(
            (provider, session_uuid), {"stake": 0, "win": 0})
        if win > entry["win"]:
            entry["win"] = win
        return entry

    def rgs_close_round(self, provider: str, session_uuid: str) -> dict | None:
        """Take the finished round off the books of the running ones."""
        return self.rgs_rounds.pop((provider, session_uuid), None)

    def wallet_owner(self, token: str) -> dict | None:
        """The session behind a wallet token: player and game, or None.

        The interposition needs the player, which the client-facing
        view deliberately does not carry.
        """
        session = self.wallet_tokens.get(str(token or ""))
        return dict(session) if session else None

    def wallet_balance(self, player_id: str) -> int:
        """What the player can spend, in centavos, stake plus bonus."""
        view = self._wallet_view(player_id)
        return int(view["balance_minor"]) + int(view["bonus_minor"])

    def interposed_launch(self, game_id: str, token: str, origin: str) -> str:
        """The launch URL for a publisher we interpose at the RGS.

        The launcher keeps every parameter it was given — the game
        reads them off its own location — but its RGS base is
        pointed at us, so the money calls are the game's, decided
        by our wallet. It is served from our own origin: a
        publisher page reaching a local service is blocked by the
        browser (public page, private address), and same-origin
        removes that question entirely. Empty for a publisher
        without an RGS parameter, which needs the page proxy.

        The trailing slash matters: the launcher loads its assets
        relatively, and they have to land under this game path.
        """
        game = game_proxy.game_for(game_id)
        if not game:
            return ""
        provider = game.get("provider") or ""
        if provider not in rgs_proxy.UPSTREAMS:
            return ""
        from urllib.parse import parse_qsl, urlencode, urlsplit
        query = dict(parse_qsl(urlsplit(game.get("demo_url") or "").query))
        query["env"] = rgs_proxy.env_url(origin, provider)
        query["token"] = token
        return f"{origin}{game_proxy.GAME_PREFIX}/{game_id}/?{urlencode(query)}"

    def wallet_status(self, token: str) -> dict:
        session = self._wallet_session(token)
        return {"game_id": session["game_id"],
                **self._wallet_view(session["player"])}

    def wallet_view_for(self, token: str) -> dict | None:
        """The bridge's config: the player's real saldo for one token, or None."""
        session = self.wallet_tokens.get(str(token or ""))
        if not session:
            return None
        return {"token": token, **self._wallet_view(session["player"])}

    def wallet_debit(self, payload: dict) -> dict:
        """Take a stake for a publisher round. A shortfall is a refusal with a
        deposit message (400), never a free spin."""
        session = self._wallet_session(payload.get("token"))
        player_id = session["player"]
        stake = int(payload["stake_minor"])
        if stake not in STAKE_STEPS:
            raise ValueError(f"stake must be one of {STAKE_STEPS} centavos")
        self.exclusions.assert_playable(player_id)
        round_id = str(payload.get("round_id") or uuid.uuid4().hex[:12])
        key = f"demo:wdebit:{session['game_id']}:{round_id}"
        with self.books.lock:
            if any(p.key == key for p in self.books.postings):
                raise ValueError("duplicate round_id")
            bonus_part = self._stake_split(player_id, stake)
            self.books.place_bet(key, player_id, stake, "2.00",
                                 bonus_part=bonus_part)
            self.books.assert_balanced()
            self._record_wager(player_id, stake, f"wallet:{round_id}")
        return {"accepted": True, "round_id": round_id,
                **self._wallet_view(player_id)}

    def wallet_credit(self, payload: dict) -> dict:
        """Settle a publisher round with the payout it reports. The stake is
        read back from the matching debit, so a restart or a replay cannot
        settle against the wrong amount."""
        session = self._wallet_session(payload.get("token"))
        player_id = session["player"]
        round_id = str(payload["round_id"])
        payout = int(payload["payout_minor"])
        if payout < 0:
            raise ValueError("payout must be non-negative")
        stake = int(payload.get("stake_minor") or 0)
        game_id = session["game_id"]
        debit_key = f"demo:wdebit:{game_id}:{round_id}"
        with self.books.lock:
            bonus_part = 0
            for posting in self.books.postings:
                if posting.key == debit_key:
                    stake = int(posting.metadata.get("stake") or stake)
                    bonus_part = int(posting.metadata.get("bonus_part") or 0)
                    break
            self.books.settle_casino(
                f"demo:wcredit:{game_id}:{round_id}", player_id, stake,
                payout, bonus_part=bonus_part)
            self.books.assert_balanced()
            self._maybe_convert(player_id, f"wallet:{round_id}")
        title = game_id
        for d in self.provider_demos().get("demos", []):
            if d["game_id"] == game_id:
                title = d.get("title") or game_id
                break
        self._append_round({
            "round_id": round_id, "player": player_id, "game_id": game_id,
            "title": title, "stake_minor": stake, "tier": "publicado",
            "multiplier": (f"{payout / stake:.2f}" if stake else "0"),
            "symbols": [], "payout_minor": payout,
            "available_minor": self.books.available(player_id),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "type": "publisher",
        })
        return {"settled": True, "round_id": round_id, "payout_minor": payout,
                **self._wallet_view(player_id)}

    def wallet_round(self, payload: dict) -> dict:
        """Settle a round a publisher client reported over its own channel.

        Some publishers drive the money over a socket the page holds (Play'n
        GO's SignalR game hub), not over HTTP we can read. The injected
        bridge watches that socket in the page and reports each round here;
        settlement is the same idempotent write the interposed RGS uses, so a
        replayed round cannot charge or pay twice.
        """
        session = self._wallet_session(payload.get("token"))
        player_id = session["player"]
        round_id = str(payload.get("round_id") or "").strip()
        if not round_id:
            raise ValueError("round_id is required")
        try:
            stake = int(payload["stake_minor"])
            payout = int(payload.get("payout_minor") or 0)
        except (KeyError, TypeError):
            raise ValueError("stake_minor is required")
        if stake < 0 or payout < 0:
            raise ValueError("stake and payout must be non-negative")
        if stake > 10000000:
            raise ValueError("stake out of range")
        return self.settle_rgs_round(player_id, session["game_id"],
                                     f"px:{round_id}", stake, payout)

    def settle_rgs_round(self, player_id: str, game_id: str, round_id: str,
                         stake: int, win: int) -> dict:
        """Settle one round an interposed RGS reported.

        The stake leaves the wallet and the win comes back as one
        balanced posting, keyed by round_id: a replayed answer
        cannot charge or pay the player twice.
        """
        if player_id not in self.players.read_all():
            raise KeyError(f"unknown player: {player_id}")
        self.exclusions.assert_playable(player_id)
        key = f"rgs:{game_id}:{round_id}"
        with self.books.lock:
            if any(p.key.startswith(key) for p in self.books.postings):
                return {"settled": False, "replayed": True,
                        **self._wallet_view(player_id)}
            self.books.place_bet(f"{key}:bet", player_id, stake, "2.00")
            self.books.settle_casino(f"{key}:win", player_id, stake, win)
            self.books.assert_balanced()
            self._record_wager(player_id, stake, f"rgs:{round_id}")
        self._maybe_convert(player_id, f"rgs:{round_id}")
        title = game_id
        for demo in self.provider_demos().get("demos", []):
            if demo["game_id"] == game_id:
                title = demo.get("title") or game_id
                break
        self._append_round({
            "round_id": round_id, "player": player_id, "game_id": game_id,
            "title": title, "stake_minor": stake, "tier": "publicado",
            "multiplier": (f"{win / stake:.2f}" if stake else "0"),
            "symbols": [], "payout_minor": win,
            "available_minor": self.books.available(player_id),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "type": "publisher",
        })
        return {"settled": True, "round_id": round_id, "payout_minor": win,
                **self._wallet_view(player_id)}

    def health_report(self) -> dict:
        """Read-only. The previous version wrote a fresh receipt and then
        checked its freshness, so the main liveness check could never fail
        and every GET dirtied the scheduler state."""
        report = health(self.scheduler, self.ledger_path, self.books.path)
        return {"status": report.status, "checks": report.as_dict()["checks"]}


DEMO = Demo()


def _sports_status(kickoff: str, sport: str) -> str:
    duration = 195 if sport == "nfl" else 105
    try:
        started = datetime.fromisoformat(
            str(kickoff).replace("Z", "+00:00"))
    except ValueError:
        return "STATUS_SCHEDULED"
    now = datetime.now(timezone.utc)
    if now < started:
        return "STATUS_SCHEDULED"
    if (now - started).total_seconds() < duration * 60:
        return "IN_PROGRESS"
    return "STATUS_FINAL"


class Handler(BaseHTTPRequestHandler):
    server_version = "OperatorDemo/0.1"
    _head_only = False

    def log_message(self, *args):  # quieter logs
        pass

    def _send(self, code: int, payload, ctype="application/json",
              cache="no-store", headers: dict | None = None,
              charset: bool = True) -> None:
        body = payload if isinstance(payload, bytes) else (
            payload.encode("utf-8") if isinstance(payload, str)
            else json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        # 204/304 carry no body. A Content-Length on them either contradicts
        # the status or strands the client waiting for bytes that never come,
        # and a HEAD answer must carry the headers of the GET without them.
        bodyless = code in (204, 304) or self._head_only
        # A publisher that already declares its charset must not be told
        # twice: `text/javascript; charset=utf-8; charset=utf-8` is the kind
        # of answer that makes a strict client treat the body as text/plain.
        if charset and "charset=" not in ctype.lower():
            ctype = ctype + "; charset=utf-8"
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if not bodyless:
            self.send_header("Content-Length", str(len(body)))
        # small, cheap hardening: the demo never serves a sniffable
        # content-type guess, and fresh chunks beat any HTTP cache
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", cache)
        for key, value in (headers or {}).items():
            if isinstance(value, (list, tuple)):
                for item in value:
                    self.send_header(key, item)
            else:
                self.send_header(key, value)
        self.end_headers()
        if not bodyless:
            self.wfile.write(body)

    def _cookie(self, name: str) -> str:
        from urllib.parse import unquote as _unquote
        for part in (self.headers.get("Cookie") or "").split(";"):
            key, _, value = part.strip().partition("=")
            if key == name:
                return _unquote(value)
        return ""

    def _our_origin(self) -> str:
        """The public origin the browser actually sees.

        Behind a reverse proxy (the Cloudflare Worker in `deploy/`) the
        request Host is the internal backend host, so the proxy names the
        public origin through X-Forwarded-Proto/X-Forwarded-Host. The game
        proxy rewrites publisher URLs against this value, and a wrong scheme
        or host there breaks every asset the game asks for. Direct callers
        (no proxy) keep the Host-header behaviour.
        """
        proto = (self.headers.get("X-Forwarded-Proto") or "http")
        host = (self.headers.get("X-Forwarded-Host")
                or self.headers.get("Host") or "127.0.0.1:8765")
        proto = proto.split(",")[0].strip() or "http"
        host = host.split(",")[0].strip() or "127.0.0.1:8765"
        return f"{proto}://{host}"

    def _pass_redirect(self, status: int, up_headers: dict, game_id: str,
                       url: str, token: str = "") -> bool:
        """Hand a publisher redirect back to the browser, pointed at us.

        Following a launcher redirect server-side drops the session it mints
        from the browser's own URL (Spribe's `?user=&token=`), and the game
        reads those from `location`. Passing the redirect through — rewritten
        onto our origin — leaves the browser at a URL that still carries them.
        Our wallet token rides along as `wallet_token`, so the document we end
        up serving is still bound to the player.
        """
        if status not in game_proxy.REDIRECT_STATUSES:
            return False
        location = up_headers.get("Location") or up_headers.get("location")
        if not location:
            return False
        from urllib.parse import urljoin, urlparse as _urlparse
        target = _urlparse(urljoin(url, location))
        if not game_proxy.allowed_host(target.netloc or ""):
            return False
        where = (f"{self._our_origin()}{game_proxy.GAME_PREFIX}/{game_id}"
                 f"/_abs/{target.netloc}{target.path or '/'}")
        params = target.query
        if token:
            params = f"{params}&wallet_token={token}" if params else f"wallet_token={token}"
        if params:
            where += "?" + params
        self._send(status, b"", "text/plain", cache="no-store",
                   headers={"Location": where}, charset=False)
        return True

    def _serve_game(self, parsed, body: bytes | None) -> None:
        """Proxy one publisher-game request through our wallet (decision 0022).

        The game is served same-origin so its calls reach us; the balance it
        shows is replaced with the player's saldo, and a mapped bet settles the
        stake/win through the books.
        """
        import re as _re
        from urllib.parse import parse_qs
        path = parsed.path
        if path == game_proxy.BRIDGE_PATH:
            self._send(200, game_proxy.bridge_script(), "text/javascript")
            return
        parts = game_proxy.split_game_path(path)
        if parts is None:
            self._send(404, {"error": "not a game path"})
            return
        game_id, sub = parts
        game = game_proxy.game_for(game_id)
        if not game:
            self._send(404, {"error": "unknown game"})
            return
        query = parse_qs(parsed.query)
        # `wallet_token` survives a launcher redirect that carries the
        # publisher's own `token`; `token` is ours on a direct launch.
        token = ((query.get("wallet_token") or [""])[0]
                 or (query.get("token") or [""])[0]
                 or self._cookie("wallet_token"))
        provider = game.get("provider") or ""
        money = game_proxy.MONEY_PATHS.get(provider, ())
        is_money = bool(money) and any(
            _re.search(pattern, sub) for pattern in money)
        is_document = sub == ""
        passthrough = provider in game_proxy.REDIRECT_PROVIDERS
        # We rewrite the body of a document, a money answer and every script
        # bundle. A body like that cannot be revalidated against the
        # publisher's validator — the bytes we hand back are not the bytes it
        # describes — so the client's validators are withheld and only its
        # request is forwarded. Everything else revalidates, which is the
        # difference between a 304 and re-downloading the whole game.
        plain_headers = {k: v for k, v in self.headers.items()
                         if k.lower() not in game_proxy.CONDITIONAL_HEADERS}
        withheld = is_document or is_money or game_proxy.rewritable(sub)
        request_headers = plain_headers if withheld else dict(self.headers)
        request_body = body if self.command == "POST" else None

        def upstream(headers: dict):
            return game_proxy.fetch(url, self.command, request_body,
                                    headers, follow=not passthrough)

        def content_type(up_headers: dict) -> str:
            return (up_headers.get("Content-Type")
                    or up_headers.get("content-type")
                    or "application/octet-stream")

        try:
            # our own parameters never travel: the publisher has no use for a
            # player's wallet credential. The exception is an interposed RGS,
            # whose token the game reads off its own launcher URL and hands
            # straight back to us.
            url = game_proxy.target_url(game, sub, game_proxy.publisher_query(
                parsed.query,
                keep=("token",) if provider in rgs_proxy.UPSTREAMS else ()))
            status, up_headers, data = upstream(request_headers)
            ctype = content_type(up_headers)
            if status == 304 and (withheld
                                  or game_proxy.rewriteable_type(ctype)):
                # a rewrite could not have run on an empty answer, and a 304
                # for it would pin the client to bytes we never computed:
                # ask again without the validators and serve the real body
                status, up_headers, data = upstream(plain_headers)
                ctype = content_type(up_headers)
        except (game_proxy.ProxyError, OSError, ValueError) as exc:
            import sys as _sys
            print(f"[proxy] upstream failed: {type(exc).__name__}: {exc}",
                  file=_sys.stderr, flush=True)
            self._send(502, {"error": f"publisher unavailable: {type(exc).__name__}"})
            return
        if passthrough and self._pass_redirect(status, up_headers, game_id,
                                               url, token):
            return
        text = "text" in ctype.lower() or "json" in ctype.lower()
        view = DEMO.wallet_view_for(token)
        our_origin = self._our_origin()
        original = data
        data = game_proxy.rewrite_urls(data, ctype, game_id, our_origin, money)
        rewrote = data != original
        # money tap: the saldo the game shows is the player's
        # real one, so an RGS answer carries our balance
        if is_money and view is not None:
            data = game_proxy.rewrite_balance(
                data, view.get("balance_minor") or 0)
            rewrote = True
        extra = {}
        is_document = is_document or (passthrough and "html" in ctype.lower())
        if is_document:
            # The document's own host: after a launcher redirect the game is
            # served from `<game>-demo.spribegaming.com`, not the catalog host,
            # and the page resolves its assets against our root (it ships
            # `<base href="/">`), so the catch-all must fetch from the host the
            # document actually came from. These bind the proxy session whether
            # or not there is a wallet behind it.
            doc_host = game["host"]
            if sub.startswith("_abs/"):
                doc_host = sub[len("_abs/"):].split("/", 1)[0]
            extra["Set-Cookie"] = [
                f"proxy_host={doc_host}; Path=/; SameSite=Lax",
                f"proxy_provider={provider}; Path=/; SameSite=Lax",
                f"proxy_game={game_id}; Path=/; SameSite=Lax",
            ]
            if view is not None:
                # the wallet rides every sub-request, and the client the game
                # spawns inherits this origin binding
                extra["Set-Cookie"].append(
                    f"wallet_token={token}; Path=/; SameSite=Lax")
                data = game_proxy.inject_bridge(data, game_id, token, view)
                rewrote = True
            if passthrough:
                # a single-page game routed off `<base href="/">` matches no
                # route under our proxy path and never initialises
                rebased = game_proxy.rebase(data, parsed.path.rstrip("/") + "/")
                rewrote = rewrote or rebased != data
                data = rebased
        if not (rewrote or withheld):
            extra.update(game_proxy.validator_headers(up_headers))
        self._send(status, data, ctype, charset=text,
                   cache=game_proxy.cache_policy(
                       up_headers, status=status, rewritten=rewrote,
                       document=is_document, money=is_money),
                   headers=extra)

    def _serve_publisher_root(self, parsed, body: bytes | None) -> None:
        """Serve a root-level path the game client asks for.

        The client the game spawns builds its URLs from the
        domain in our config, so it lands on our own origin
        at paths the storefront does not know (/apps/…, a
        stray /gs2c/…). The session cookies say which
        publisher hosts them, so the request is forwarded
        and the answer is brought back onto our origin like
        any other proxied call.
        """
        import re as _re
        game_id = self._cookie("proxy_game")
        game = game_proxy.game_for(game_id) if game_id else None
        host = self._cookie("proxy_host")
        if not host or game is None or not game_proxy.allowed_host(host):
            self._send(404, {"error": "not found"})
            return
        # the provider comes from the catalog, not from the browser: the
        # cookie only says which host to fetch, and a stale one would
        # otherwise have the wrong money paths applied to it
        provider = game.get("provider") or ""
        money = game_proxy.MONEY_PATHS.get(provider, ())
        is_money = bool(money) and any(
            _re.search(pattern, parsed.path) for pattern in money)
        try:
            target = game_proxy.checked_url(f"https://{host}{parsed.path}")
        except game_proxy.ProxyError:
            self._send(404, {"error": "not found"})
            return
        if parsed.query:
            target += ("&" if "?" in target else "?") + \
                game_proxy.publisher_query(parsed.query)
        plain_headers = {k: v for k, v in self.headers.items()
                         if k.lower() not in game_proxy.CONDITIONAL_HEADERS}
        withheld = is_money or game_proxy.rewritable(parsed.path)
        request_body = body if self.command == "POST" else None

        def upstream(headers: dict):
            return game_proxy.fetch(target, self.command, request_body, headers)

        def content_type(up_headers: dict) -> str:
            return (up_headers.get("Content-Type")
                    or up_headers.get("content-type")
                    or "application/octet-stream")

        try:
            request_headers = plain_headers if withheld else dict(self.headers)
            status, up_headers, data = upstream(request_headers)
            ctype = content_type(up_headers)
            if status == 304 and (withheld
                                  or game_proxy.rewriteable_type(ctype)):
                # our rewrite could not have run on an empty answer: ask
                # again without the validators and serve the real body
                status, up_headers, data = upstream(plain_headers)
                ctype = content_type(up_headers)
        except (game_proxy.ProxyError, OSError, ValueError) as exc:
            self._send(502, {"error": f"publisher unavailable: {type(exc).__name__}"})
            return
        view = DEMO.wallet_view_for(self._cookie("wallet_token"))
        original = data
        data = game_proxy.rewrite_urls(data, ctype, game_id, self._our_origin(), money)
        rewrote = data != original
        if is_money and view is not None:
            data = game_proxy.rewrite_balance(
                data, view.get("balance_minor") or 0)
            rewrote = True
        extra = ({} if (rewrote or withheld)
                else game_proxy.validator_headers(up_headers))
        self._send(status, data, ctype, charset="text" in ctype.lower()
                   or "json" in ctype.lower(),
                   cache=game_proxy.cache_policy(up_headers, status=status,
                                                rewritten=rewrote, money=is_money),
                   headers=extra)

    def _serve_publisher_root(self, parsed, body: bytes | None) -> None:
        """Serve a root-level path the game client asks for.

        The client the game spawns builds its URLs from the
        domain in our config, so it lands on our own origin
        at paths the storefront does not know (/apps/…, a
        stray /gs2c/…). The session cookies say which
        publisher hosts them, so the request is forwarded
        and the answer is brought back onto our origin like
        any other proxied call.
        """
        import re as _re
        from urllib.parse import parse_qs
        host = self._cookie("proxy_host")
        provider = self._cookie("proxy_provider")
        game_id = self._cookie("proxy_game")
        game = game_proxy.game_for(game_id) if game_id else None
        if not host or game is None:
            self._send(404, {"error": "not found"})
            return
        if not game_proxy.allowed_host(host):
            self._send(404, {"error": "not found"})
            return
        target = f"https://{host}{parsed.path}"
        if parsed.query:
            target += "&" if "?" in target else "?"
            target += parsed.query
        try:
            status, up_headers, data = game_proxy.fetch(
                target, self.command,
                body if self.command == "POST" else None,
                {k: v for k, v in self.headers.items()})
        except (game_proxy.ProxyError, OSError, ValueError) as exc:
            self._send(502, {"error": f"publisher unavailable: {type(exc).__name__}"})
            return
        ctype = up_headers.get("Content-Type") or up_headers.get("content-type") \
            or "application/octet-stream"
        view = DEMO.wallet_view_for(self._cookie("wallet_token"))
        money = game_proxy.MONEY_PATHS.get(provider, ())
        our_origin = self._our_origin()
        data = game_proxy.rewrite_urls(data, ctype, game_id, our_origin, money)
        if money and view is not None and any(
                _re.search(pattern, parsed.path) for pattern in money):
            data = game_proxy.rewrite_balance(
                data, view.get("balance_minor") or 0)
        self._send(status, data, ctype, cache="no-cache",
                   charset="text" in ctype.lower() or "json" in ctype.lower())

    def _serve_rgs(self, parsed, body: bytes | None) -> None:
        """Forward one RGS call and answer the game.

        The game page lives on the publisher's CDN (it was pointed
        at us through the launcher's `env=`), so the answer carries
        CORS. The saldo it reports is the player's real one, and a
        round it reports settles on our books.
        """
        parts = rgs_proxy.split_path(parsed.path)
        if parts is None:
            self._send(404, {"error": "unknown rgs route"})
            return
        provider, tail = parts
        try:
            target = rgs_proxy.upstream_url(provider, tail)
        except rgs_proxy.RgsError as exc:
            self._send(404, {"error": str(exc)})
            return
        if parsed.query:
            target += ("&" if "?" in target else "?") + parsed.query
        request_body = body if self.command == "POST" else None
        # the game carries our wallet token; the publisher's RGS
        # only knows its own, so it is swapped back in for the hop
        token = rgs_proxy.session_token(request_body or b"")
        if not token:
            token = DEMO.rgs_token(
                provider, rgs_proxy.session_uuid(request_body))
        owner = DEMO.wallet_owner(token)
        stake = rgs_proxy.bet_total(request_body)
        if stake and owner is not None and DEMO.wallet_balance(
                owner["player"]) < stake:
            # no money, no spin: the round is refused here rather
            # than played on the publisher's demo credits
            data = rgs_proxy.refusal("Saldo insuficiente — deposite para girar.")
            self._send(200, data, "application/json", cache="no-store",
                       headers=rgs_proxy.cors_headers(
                           self.headers.get("Origin") or "",
                           self.headers.get("Access-Control-Request-Headers") or ""),
                       charset=True)
            return
        forwarded = rgs_proxy.swap_token(request_body,
                                         rgs_proxy.demo_token(provider))
        try:
            status, up_headers, data = game_proxy.fetch(
                target, self.command, forwarded,
                {k: v for k, v in self.headers.items()})
        except (game_proxy.ProxyError, OSError, ValueError) as exc:
            self._send(502, {"error": f"rgs unavailable: {type(exc).__name__}"})
            return
        ctype = up_headers.get("Content-Type") or "application/json"
        if token and DEMO.rgs_token(
                provider, rgs_proxy.session_uuid(data)) == "":
            # remember the session the answer named, so the calls
            # that come next can still reach this wallet
            DEMO.rgs_bind(provider, rgs_proxy.session_uuid(data), token)
        if owner is not None:
            data = self._tap_rgs(provider, owner, request_body, data)
        self._send(status, data, ctype, cache="no-store",
                   headers=rgs_proxy.cors_headers(
                       self.headers.get("Origin") or "",
                       self.headers.get("Access-Control-Request-Headers") or ""),
                   charset="json" in ctype.lower())

    def _tap_rgs(self, provider: str, owner: dict, request: bytes | None,
                 data: bytes) -> bytes:
        """Mirror one RGS answer onto the wallet and swap in our saldo.

        A round's stake arrives in the call and its win accrues in
        the answers; the round is settled on our books the moment
        the RGS finishes it, so the money the player sees is the
        money the operator holds — in both directions.
        """
        session = (rgs_proxy.session_uuid(request)
                   or rgs_proxy.session_uuid(data))
        stake = rgs_proxy.bet_total(request)
        if session and stake:
            DEMO.rgs_open_round(provider, session, stake)
        state = rgs_proxy.round_state(data)
        if session and state:
            DEMO.rgs_note_win(provider, session, state.get("win") or 0)
            if state.get("done"):
                closed = DEMO.rgs_close_round(provider, session)
                if closed and closed["stake"]:
                    self._settle_rgs(provider, owner,
                                     state.get("id") or session,
                                     closed["stake"], closed["win"])
        balance = DEMO.wallet_balance(owner["player"])
        return rgs_proxy.replace_balance(data, balance)

    def _settle_rgs(self, provider: str, owner: dict, round_id: str,
                    stake: int, win: int) -> None:
        """Settle a finished round against the wallet, once."""
        try:
            DEMO.settle_rgs_round(owner["player"], owner["game_id"],
                                  f"{provider}:{round_id}", stake, win)
        except (DuplicatePosting, WalletError, ValueError, KeyError,
                ExclusionError):
            # an already-settled round; the saldo stands
            pass

    def _bearer(self) -> str:
        """Painel session token from `Authorization: Bearer …`, or ""."""
        header = self.headers.get("Authorization") or ""
        if header.lower().startswith("bearer "):
            return header[7:].strip()
        return ""

    def _body(self) -> dict:
        """Read a JSON body. Rejects non-JSON content types: without this,
        any page on any origin can drive the API cross-site (a
        `text/plain` POST is a CORS simple request, no preflight)."""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if ctype and ctype != "application/json":
            raise ValueError(f"Content-Type must be application/json, got {ctype}")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 65536:
            return {}
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}
        return body if isinstance(body, dict) else {}

    def _raw_body(self) -> bytes:
        """Raw request body for the game proxy: the publisher decides its own
        content type, so the JSON-only rule does not apply here."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 262144:
            return b""
        return self.rfile.read(length)

    def _same_origin(self) -> bool:
        """Local demo, single-user: only same-origin writes are accepted."""
        origin = self.headers.get("Origin")
        if not origin:
            return True  # curl / same-origin fetch without Origin
        host = self.headers.get("Host") or ""
        if origin.split("//")[-1] == host:
            return True
        # Local single-user demo: loopback aliases (localhost vs 127.0.0.1 vs ::1)
        # are the same machine — allow them on the same port.
        try:
            from urllib.parse import urlparse

            o = urlparse(origin)
            h = host.split(":")[0]
            o_host = (o.hostname or "").lower()
            o_port = o.port
            srv_port = int(host.split(":")[1]) if ":" in host else None
            loopbacks = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
            if o_host in loopbacks and h in loopbacks:
                return True  # any local loopback alias port (browser preview, file, proxy)
        except (ValueError, IndexError):
            pass
        return False

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith(game_proxy.GAME_PREFIX + "/"):
                self._serve_game(parsed, None)
                return
            if parsed.path.startswith(rgs_proxy.PREFIX + "/"):
                self._serve_rgs(parsed, None)
                return
            if not parsed.path.startswith("/api/"):
                asset = static_file(parsed.path)
                if asset:
                    cache = (
                        "public, max-age=31536000, immutable"
                        if parsed.path.startswith("/_next/static/")
                        else "no-cache"
                    )
                    with open(asset[0], "rb") as handle:
                        self._send(200, handle.read(), asset[1], cache=cache)
                    return
                if self._cookie("proxy_host"):
                    # a path the game client asks for on our
                    # origin; the session cookies name the
                    # publisher that hosts it
                    self._serve_publisher_root(parsed, None)
                    return
                self._send(404, {"error": "not found"})
                return
            if parsed.path == "/api/catalog":
                self._send(200, {"games": DEMO.catalog(),
                                 "demo_rtp": DEMO_RTP_STR,
                                 "vendor": DEMO.vendor_catalog(),
                                 "provider_demos": DEMO.provider_demos(),
                                 "external_demo_url": external_demo_url()})
            elif parsed.path == "/api/health":
                self._send(200, {**DEMO.health_report(),
                                 "proxy": game_proxy.stats()})
            elif parsed.path == "/api/player":
                from urllib.parse import parse_qs
                query = parse_qs(parsed.query)
                self._send(200, DEMO.profile(query["id"][0]))
            elif parsed.path == "/api/history":
                from urllib.parse import parse_qs
                query = parse_qs(parsed.query)
                player = query["player"][0]
                self._send(200, {"rounds": DEMO.history(player),
                                 "risk": DEMO.risk(player)})
            elif parsed.path == "/api/sports":
                DEMO.settle_pending()
                self._send(200, DEMO.sports_showcase())
            elif parsed.path == "/api/trending":
                self._send(200, DEMO.trending())
            elif parsed.path == "/api/live":
                self._send(200, DEMO.live())
            elif parsed.path == "/api/wallet/status":
                from urllib.parse import parse_qs
                query = parse_qs(parsed.query)
                self._send(200, DEMO.wallet_status(query["token"][0]))
            elif parsed.path == "/api/tournaments":
                self._send(200, DEMO.tournaments())
            elif parsed.path == "/api/news":
                self._send(200, DEMO.news())
            elif parsed.path == "/api/jackpot":
                self._send(200, DEMO.jackpot())
            elif parsed.path == "/api/auth/me":
                self._send(200, DEMO.auth_me(self._bearer()))
            elif parsed.path == "/api/admin/users":
                self._send(200, DEMO.admin_users(self._bearer()))
            elif parsed.path == "/api/admin":
                self._send(200, DEMO.admin_dashboard(self._bearer()))
            elif parsed.path == "/api/admin/player":
                from urllib.parse import parse_qs
                query = parse_qs(parsed.query)
                self._send(200, DEMO.admin_player_dashboard(
                    self._bearer(), query["id"][0]))
            else:
                self._send(404, {"error": "not found"})
        except AuthError as exc:
            # panel refusal: the message is written for the client
            self._send(401, {"error": str(exc)})
        except CertificationError as exc:
            self._send(403, {"error": str(exc)})
        except ExclusionError as exc:
            self._send(403, {"error": str(exc)})
        except DuplicatePosting as exc:
            # a replayed round_id or bonus key is a correct refusal,
            # not an internal failure
            self._send(400, {"error": f"duplicate id: {exc}"})
        except (KeyError, ValueError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:
            # no absolute paths or internals in a client-visible message,
            # but the traceback belongs in the server log
            import sys as _sys
            import traceback as _tb
            _tb.print_exc(file=_sys.stderr)
            _sys.stderr.flush()
            self._send(500, {"error": f"internal error: {type(exc).__name__}"})

    def do_HEAD(self) -> None:  # noqa: N802
        """Answer a HEAD like the GET it stands for, without the body.

        The base class answers 501, which is a lie about a publisher asset
        that is right there on disk behind the proxy: a client that probes
        before fetching (or a cache revalidating with HEAD) gets told the
        resource does not exist.
        """
        self._head_only = True
        try:
            self.do_GET()
        finally:
            self._head_only = False

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Answer the RGS preflight.

        A JSON POST from the game page on the publisher's origin
        is not a simple request, so the browser asks first; the
        answer is what lets the money calls through.
        """
        parsed = urlparse(self.path)
        if rgs_proxy.split_path(parsed.path) is not None:
            self._send(200, b"", "text/plain",
                       headers=rgs_proxy.cors_headers(
                           self.headers.get("Origin") or "",
                           self.headers.get("Access-Control-Request-Headers") or ""))
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            # the RGS calls come from the game page on the
            # publisher's origin, so they are cross-origin by
            # design and carry their own CORS answer
            rgs = rgs_proxy.split_path(urlparse(self.path).path)
            if rgs is not None:
                self._serve_rgs(urlparse(self.path), self._raw_body())
                return
            if not self._same_origin():
                import sys

                print(
                    f"[403] cross-origin write refused: Origin={self.headers.get('Origin')!r} Host={self.headers.get('Host')!r}",
                    file=sys.stderr,
                )
                self._send(403, {"error": "cross-origin writes refused"})
                return
            path = urlparse(self.path).path
            if path.startswith(game_proxy.GAME_PREFIX + "/"):
                self._serve_game(urlparse(self.path), self._raw_body())
                return
            if not path.startswith("/api/") and self._cookie("proxy_host"):
                self._serve_publisher_root(urlparse(self.path),
                                           self._raw_body())
                return
            if path == "/api/player":
                self._send(200, DEMO.upsert_player(self._body()))
            elif path == "/api/deposit":
                self._send(200, DEMO.deposit(self._body()))
            elif path == "/api/withdraw":
                self._send(200, DEMO.withdraw(self._body()))
            elif path == "/api/spin":
                self._send(200, DEMO.spin(self._body()))
            elif path == "/api/crash/start":
                self._send(200, DEMO.crash_start(self._body()))
            elif path == "/api/crash/status":
                self._send(200, DEMO.crash_status(self._body()))
            elif path == "/api/crash/cashout":
                self._send(200, DEMO.crash_cashout(self._body()))
            elif path == "/api/wallet/launch":
                result = DEMO.wallet_launch(self._body())
                # the public origin the browser sees (X-Forwarded-* behind the
                # Worker), not our internal Host — the launch URL is handed to
                # the browser, so a wrong scheme/host loads the game off-domain
                origin = self._our_origin()
                interposed = DEMO.interposed_launch(
                    result["game_id"], result["token"], origin)
                if interposed:
                    result["interposed_url"] = interposed
                self._send(200, result)
            elif path == "/api/wallet/debit":
                self._send(200, DEMO.wallet_debit(self._body()))
            elif path == "/api/wallet/credit":
                self._send(200, DEMO.wallet_credit(self._body()))
            elif path == "/api/wallet/round":
                self._send(200, DEMO.wallet_round(self._body()))
            elif path == "/api/bet":
                DEMO.settle_pending()
                self._send(200, DEMO.bet(self._body()))
            elif path == "/api/settle":
                settled = DEMO.settle_pending()
                self._send(200, {"settled": len(settled), "rows": settled})
            elif path == "/api/bonus":
                self._send(200, DEMO.claim_bonus(self._body()))
            elif path == "/api/play":
                self._send(200, DEMO.record_play(self._body()))
            elif path == "/api/chat":
                self._send(200, DEMO.chat(self._body()))
            elif path == "/api/self-exclude":
                body = self._body()
                self._send(200, DEMO.self_exclude(
                    body["player"], body.get("until", "2027-01-01")))
            elif path == "/api/self-exclude-lift":
                self._send(200, DEMO.lift_exclusion(self._body()["player"]))
            elif path == "/api/auth/login":
                self._send(200, DEMO.auth_login(self._body()))
            elif path == "/api/auth/logout":
                self._send(200, DEMO.auth_logout(self._bearer()))
            elif path == "/api/auth/password":
                self._send(200, DEMO.auth_change_password(
                    self._bearer(), self._body()))
            elif path == "/api/admin/users":
                self._send(200, DEMO.admin_create_user(
                    self._bearer(), self._body()))
            elif path == "/api/admin/users/reset":
                self._send(200, DEMO.admin_reset_password(
                    self._bearer(), self._body()))
            elif path == "/api/admin/users/delete":
                self._send(200, DEMO.admin_delete_user(
                    self._bearer(), self._body()))
            else:
                self._send(404, {"error": "not found"})
        except AuthError as exc:
            # panel refusal: the message is written for the client
            self._send(401, {"error": str(exc)})
        except CertificationError as exc:
            self._send(403, {"error": str(exc)})
        except ExclusionError as exc:
            self._send(403, {"error": str(exc)})
        except DuplicatePosting as exc:
            self._send(400, {"error": f"duplicate id: {exc}"})
        except (KeyError, ValueError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:
            # no absolute paths or internals in a client-visible message
            self._send(500, {"error": f"internal error: {type(exc).__name__}"})


def run(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"operator demo (NO REAL MONEY) on http://{host}:{port}")
    stop = threading.Event()

    # self-identifying marker for ops: a second server on this data dir
    # would squander the port and serve stale code (p5 trap on 2026-10-05)
    pid_path = os.path.join(DATA, "server.pid")
    try:
        with open(pid_path, "w", encoding="utf-8") as _pid:
            _pid.write(str(os.getpid()))
    except OSError:
        pid_path = None

    def tick() -> None:
        # an honest liveness signal: the previous read-path receipt was
        # written and then immediately checked for freshness, so the check
        # could never fail
        while not stop.wait(HEARTBEAT_SECONDS):
            DEMO.scheduler.receipt("heartbeat", 0, 0, 0, [])
            try:
                DEMO.sweep_crash()  # a vanished client must not strand a stake
            except Exception:
                pass

    beat = threading.Thread(target=tick, daemon=True, name="heartbeat")
    beat.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        if pid_path and os.path.exists(pid_path):
            try:
                os.unlink(pid_path)
            except OSError:
                pass
    return server


if __name__ == "__main__":
    # HOST/PORT come from the environment so a PaaS (Render/Fly/Koyeb/Railway)
    # can place the server behind its router; the local default is unchanged.
    run(host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8765")))
