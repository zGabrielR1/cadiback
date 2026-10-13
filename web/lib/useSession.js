"use client";

import { useCallback, useRef, useState } from "react";
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
  const [refreshError, setRefreshError] = useState("");
  const [busy, setBusy] = useState(false);

  const refreshSeq = useRef(0);

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
    refreshError,
    setRefreshError,
    busy,
    setBusy,
    refresh,
  };
}
