"use client";

import { useEffect, useState } from "react";
import { api } from "./api";

/** Keep the last successful board while a refresh fails. Polls never overlap,
 * and responses from a view that has been left cannot replace newer data. */
export function useSportsFeed(active) {
  const [sports, setSports] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (!active) return undefined;
    let stopped = false;
    let timer;
    let slowTimer;
    const controller = new AbortController();
    const load = async () => {
      setLoading(true);
      setSlow(false);
      slowTimer = setTimeout(() => { if (!stopped) setSlow(true); }, 6000);
      try {
        const next = await api("GET", "/api/sports", undefined, { signal: controller.signal });
        if (stopped) return;
        if (!next || !Array.isArray(next.fixtures)) throw new Error("invalid feed");
        setSports(next);
        setUpdatedAt(Date.now());
        setError("");
      } catch (e) {
        if (!stopped) setError("Não foi possível atualizar as partidas. Tente novamente.");
      } finally {
        if (!stopped) {
          clearTimeout(slowTimer);
          setLoading(false);
          setSlow(false);
          timer = setTimeout(load, 15000);
        }
      }
    };
    load();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); clearTimeout(slowTimer); };
  }, [active, attempt]);

  return { sports, loading, slow, error, updatedAt, retry: () => setAttempt((n) => n + 1) };
}
