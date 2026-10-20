"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

/** Shared player-session state (F1): player id, profile, history, health
 * and the busy flag, plus refresh() which reloads all three. Lifted out
 * of page.jsx so shell components and action handlers share one hook
 * instead of threading a dozen props through every modal. */
export function useSession() {
  const [player, setPlayer] = useState(null);
  const [profile, setProfile] = useState(null);
  const [history, setHistory] = useState(null);
  const [health, setHealth] = useState("");
  // Whether the server has a live Asaas Pix rail. When it does, the cashier
  // opens a real charge and waits for confirmation; when it does not, the
  // instant demo credit is the honest fallback.
  const [asaasAvailable, setAsaasAvailable] = useState(false);
  // Whether the server has a live NOWPayments crypto rail, and which coins it
  // offers. Same rule as Asaas: a real invoice when configured, the instant
  // demo credit otherwise.
  const [cryptoAvailable, setCryptoAvailable] = useState(false);
  const [cryptoCoins, setCryptoCoins] = useState([]);
  // Public operator settings the storefront adapts to: whether signup
  // demands the payout account, and whether hidden test accounts may log
  // in. Fetched on boot so the account modal knows the rules before a
  // single player logs in.
  const [serverConfig, setServerConfig] = useState({
    require_bank_at_signup: false,
    test_accounts_enabled: true,
    turnstile_enabled: false,
    turnstile_site_key: "",
    oauth_enabled: false,
    oauth_providers: [],
    password_reset_enabled: false,
  });
  const [refreshError, setRefreshError] = useState("");
  const [busy, setBusy] = useState(false);

  const refreshSeq = useRef(0);

  useEffect(() => {
    let alive = true;
    // `/api/config` carries the operator flags; `/api/betterauth/providers`
    // is the auth server's credential-aware answer (decision 0066). The
    // second wins for the social row: a provider with no credentials must
    // not render a button that cannot complete.
    Promise.all([
      api("GET", "/api/config").catch(() => null),
      fetch("/api/betterauth/providers", { credentials: "same-origin" })
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null),
    ]).then(([cfg, auth]) => {
      if (!alive) return;
      if (!cfg && !auth) return;
      const merged = { ...(cfg || {}) };
      if (auth && Array.isArray(auth.providers)) {
        merged.oauth_providers = auth.providers;
        merged.oauth_enabled = Boolean(auth.enabled) &&
          auth.providers.length > 0;
      } else {
        // the sidecar did not answer: never offer a button that cannot
        // complete, even if the backend's bridge secret is configured
        merged.oauth_providers = [];
        merged.oauth_enabled = false;
      }
      setServerConfig(merged);
    });
    return () => {
      alive = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (!player) return;
    const seq = ++refreshSeq.current;
    try {
      const [p, h, hl] = await Promise.all([
        api("GET", "/api/player?id=" + encodeURIComponent(player)),
        api("GET", "/api/history?player=" + encodeURIComponent(player)),
        api("GET", "/api/health"),
      ]);
      if (seq !== refreshSeq.current) return;
      setProfile(p);
      setHistory(h);
      setHealth(hl.status);
      setAsaasAvailable(!!(hl.asaas && hl.asaas.configured));
      setCryptoAvailable(!!(hl.crypto && hl.crypto.configured));
      if (hl.crypto && Array.isArray(hl.crypto.coins)) setCryptoCoins(hl.crypto.coins);
      setRefreshError("");
    } catch (e) {
      if (seq !== refreshSeq.current) return;
      setRefreshError(e.message);
    }
  }, [player]);

  return {
    player,
    setPlayer,
    profile,
    setProfile,
    history,
    setHistory,
    health,
    setHealth,
    asaasAvailable,
    cryptoAvailable,
    cryptoCoins,
    serverConfig,
    refreshError,
    setRefreshError,
    busy,
    setBusy,
    refresh,
  };
}
