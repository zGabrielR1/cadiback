"use client";

import { useEffect, useRef } from "react";

/** Cloudflare Turnstile widget — the browser half of the bot gate.
 *
 * The widget hands the browser a short-lived token; the *server* exchanges it
 * at siteverify (foundry.turnstile). Two things this component gets right that
 * are easy to miss:
 *
 *  - **Explicit rendering.** The account modal mounts after the page loads, so
 *    Turnstile's implicit scan never sees the div. The widget is rendered by
 *    hand and its id is kept.
 *  - **Reset after every attempt.** A token is single-use. Once the parent has
 *    submitted (success or failure) it bumps `resetSignal`; the widget is reset
 *    so the next try gets a fresh token instead of a replayed one.
 *
 * `onToken` is held in a ref so a parent that passes a fresh closure each
 * render does not tear the widget down on every render.
 */
const SCRIPT_ID = "cf-turnstile-script";
const SCRIPT_SRC =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

/** Load Cloudflare's script once per page; resolve with `window.turnstile`. */
function loadTurnstile() {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("no browser"));
  }
  if (window.turnstile) return Promise.resolve(window.turnstile);
  return new Promise((resolve, reject) => {
    const ready = () =>
      window.turnstile
        ? resolve(window.turnstile)
        : reject(new Error("turnstile unavailable"));
    const failed = () => reject(new Error("turnstile script failed to load"));
    const existing = document.getElementById(SCRIPT_ID);
    if (existing) {
      existing.addEventListener("load", ready, { once: true });
      existing.addEventListener("error", failed, { once: true });
      return;
    }
    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.src = SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = ready;
    script.onerror = failed;
    document.head.appendChild(script);
  });
}

export default function TurnstileWidget({
  siteKey,
  action,
  onToken,
  resetSignal = 0,
}) {
  const slotRef = useRef(null);
  const widgetIdRef = useRef(null);
  const onTokenRef = useRef(onToken);
  onTokenRef.current = onToken;

  // Render (or re-render) whenever the surface's action changes — switching
  // between login and register must mint a token for the right action.
  useEffect(() => {
    if (!siteKey || !action) return undefined;
    let cancelled = false;
    onTokenRef.current?.(""); // a token for the previous action is now stale
    loadTurnstile()
      .then((turnstile) => {
        if (cancelled || !slotRef.current) return;
        if (widgetIdRef.current !== null) {
          try {
            turnstile.remove(widgetIdRef.current);
          } catch {
            /* already gone */
          }
          widgetIdRef.current = null;
        }
        widgetIdRef.current = turnstile.render(slotRef.current, {
          sitekey: siteKey,
          action,
          callback: (token) => onTokenRef.current?.(token),
          "error-callback": () => onTokenRef.current?.(""),
          "expired-callback": () => onTokenRef.current?.(""),
        });
      })
      .catch(() => onTokenRef.current?.(""));
    return () => {
      cancelled = true;
      if (widgetIdRef.current !== null && typeof window !== "undefined" &&
          window.turnstile) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {
          /* already gone */
        }
        widgetIdRef.current = null;
      }
    };
  }, [siteKey, action]);

  // After each submit attempt the parent bumps resetSignal: clear the stale
  // token and reset the widget so a retry is not a replayed token.
  useEffect(() => {
    if (!resetSignal) return;
    onTokenRef.current?.("");
    if (widgetIdRef.current !== null && typeof window !== "undefined" &&
        window.turnstile) {
      try {
        window.turnstile.reset(widgetIdRef.current);
      } catch {
        /* already gone */
      }
    }
  }, [resetSignal]);

  if (!siteKey) return null;
  return <div className="turnstile-slot" ref={slotRef} />;
}
