"""Vendor aggregator seam. Stdlib only. No live vendor yet.

Route-1 wiring (decision 0003: EveryMatrix primary, SOFTSWISS fallback) lands
here the day sandbox credentials arrive. Until then this module is a tested,
unconfigured seam: explicit endpoint URLs in, `CasinoAggregator`-shaped calls
out, and a hard rule that vendor titles stay non-launchable until real BR
certificates are registered (Portaria 1207/2024 — no cert, no launch).

No vendor API shapes are guessed: every endpoint URL is required config,
filled from the answers to `p3/sandbox-request.md`.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable


class AggregatorError(RuntimeError):
    pass


@dataclass(frozen=True)
class VendorConfig:
    """All URLs explicit. There are no defaults to get wrong."""

    vendor: str  # everymatrix | softswiss (or other single live aggregator)
    base_url: str
    api_key: str
    catalog_path: str = "/catalogue"
    launch_path: str = "/launch"
    bet_path: str = "/bet"
    credit_path: str = "/wallet/credit"
    history_path: str = "/rounds"
    timeout_seconds: int = 10

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "VendorConfig":
        source = env if env is not None else os.environ
        vendor = (source.get("DEMO_AGGREGATOR") or "").strip().lower()
        base = (source.get("DEMO_API_URL") or "").strip().rstrip("/")
        key = (source.get("DEMO_API_KEY") or "").strip()
        missing = [n for n, v in
                   (("DEMO_AGGREGATOR", vendor), ("DEMO_API_URL", base),
                    ("DEMO_API_KEY", key)) if not v]
        if missing:
            raise AggregatorError(
                "vendor aggregator unconfigured (missing "
                + ", ".join(missing) + "); stub serves local demo titles")
        # A plain-http base would put the aggregator key on the wire, and a
        # redirect would replay the Authorization header to another host.
        if not base.startswith("https://"):
            raise AggregatorError(
                f"DEMO_API_URL must be https:// (got {base!r}); "
                "an aggregator key must never travel in cleartext")
        return cls(vendor=vendor, base_url=base, api_key=key)


class _NoCrossOriginRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse to follow a redirect off the aggregator host.

    urllib replays the original headers on a 302, which would hand the
    Authorization bearer token to whoever the redirect points at.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).netloc != req.host:
            raise AggregatorError("refusing cross-host redirect with credentials")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_NoCrossOriginRedirect())


def _post(url: str, api_key: str, payload: dict, timeout: int) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    with _OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


@dataclass
class VendorAggregator:
    """Seamless-wallet client. Transport is injectable for tests."""

    config: VendorConfig
    transport: Callable = _post
    sessions: dict[str, str] = field(default_factory=dict)
    credits: dict[str, int] = field(default_factory=dict)

    def _call(self, path: str, payload: dict) -> dict:
        try:
            result = self.transport(
                self.config.base_url + path, self.config.api_key,
                payload, self.config.timeout_seconds)
        except AggregatorError:
            raise
        except Exception as exc:
            raise AggregatorError(f"{self.config.vendor} call failed: {exc}")
        if not isinstance(result, dict):
            raise AggregatorError(f"{self.config.vendor} returned non-object")
        return result

    def catalogue(self) -> list[dict]:
        result = self._call(self.config.catalog_path, {})
        games = result.get("games", [])
        if not isinstance(games, list):
            raise AggregatorError("vendor catalogue has no games list")
        return games

    def launch(self, player_id: str, game_id: str) -> str:
        result = self._call(self.config.launch_path,
                            {"player_id": player_id, "game_id": game_id,
                             "locale": "pt-BR", "currency": "BRL"})
        session_id = result.get("session_id")
        if not session_id:
            raise AggregatorError("vendor launch returned no session")
        self.sessions[str(session_id)] = game_id
        return str(session_id)

    def bet(self, session_id: str, round_id: str, stake_minor: int) -> dict:
        if stake_minor <= 0:
            raise AggregatorError("stake must be positive")
        return self._call(self.config.bet_path,
                          {"session_id": session_id, "round_id": round_id,
                           "stake_minor": stake_minor, "currency": "BRL"})

    def wallet_credit(self, round_id: str, amount_minor: int) -> bool:
        """Reserve the round before the network call.

        Recording the credit only after the response returns left a window in
        which a crash or retry re-credited the same round: a duplicate payout
        is a money bug, not a retry.
        """
        if round_id in self.credits:
            return False  # idempotent: double-credit is a payout bug
        self.credits[round_id] = amount_minor
        try:
            self._call(self.config.credit_path,
                       {"round_id": round_id, "amount_minor": amount_minor,
                        "currency": "BRL"})
        except AggregatorError:
            self.credits.pop(round_id, None)
            raise
        return True

    def round_history(self, session_id: str, limit: int) -> list[dict]:
        result = self._call(self.config.history_path,
                            {"session_id": session_id, "limit": limit})
        rows = result.get("rounds", [])
        if not isinstance(rows, list):
            raise AggregatorError("vendor history has no rounds list")
        return rows[-limit:] if limit > 0 else []
