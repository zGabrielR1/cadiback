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
  // Public operator settings the storefront adapts to: whether signup
  // demands the payout account, and whether hidden test accounts may log
  // in. Fetched on boot so the account modal knows the rules before a
  // single player logs in.
  const [serverConfig, setServerConfig] = useState({
    require_bank_at_signup: false,
    test_accounts_enabled: true,
  });
  const [refreshError, setRefreshError] = useState("");
  const [busy, setBusy] = useState(false);

  const refreshSeq = useRef(0);

  useEffect(() => {
    let alive = true;
    api("GET", "/api/config")
      .then((cfg) => {
        if (alive && cfg) setServerConfig(cfg);
      })
      .catch(() => {
        /* keep the safe defaults: bank optional, test accounts on */
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
    serverConfig,
    refreshError,
    setRefreshError,
    busy,
    setBusy,
    refresh,
  };
}
