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

  useEffect(() => {
    if (!active) return undefined;
    let stopped = false;
    let timer;
    const load = async () => {
      setLoading(true);
      try {
        const next = await api("GET", "/api/sports");
        if (stopped) return;
        if (!next || !Array.isArray(next.fixtures)) throw new Error("invalid feed");
        setSports(next);
        setUpdatedAt(Date.now());
        setError("");
      } catch (e) {
        if (!stopped) setError("Não foi possível atualizar as partidas. Tente novamente.");
      } finally {
        if (!stopped) {
          setLoading(false);
          timer = setTimeout(load, 15000);
        }
      }
    };
    load();
    return () => { stopped = true; clearTimeout(timer); };
  }, [active, attempt]);

  return { sports, loading, error, updatedAt, retry: () => setAttempt((n) => n + 1) };
}
