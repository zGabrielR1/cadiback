"use client";
import { useCallback, useEffect, useRef, useState } from "react";

/** Pointer and keyboard resizing, constrained to the current viewport. */
export function usePanelResize(storageKey, initialWidth, initialHeight, direction = 1, minimumWidth = 260, maximumWidth = 640) {
  const [size, setSize] = useState({ width: initialWidth, height: initialHeight });
  const drag = useRef(null);
  const bounds = useCallback(value => ({
    width: Math.round(Math.max(Math.min(minimumWidth, window.innerWidth - 32), Math.min(value.width, maximumWidth, window.innerWidth - 32))),
    height: Math.round(Math.max(Math.min(260, window.innerHeight - 160), Math.min(value.height || initialHeight, window.innerHeight - 160))),
  }), [initialWidth, initialHeight, minimumWidth, maximumWidth]);
  const update = useCallback(value => {
    const next = bounds(value);
    setSize(next);
    try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch {}
  }, [bounds, storageKey]);
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
      if (saved && Number.isFinite(saved.width) && Number.isFinite(saved.height)) setSize(bounds(saved));
    } catch {}
    const resize = () => setSize(previous => bounds(previous));
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [bounds, storageKey]);
  const handle = {
    onPointerDown(event) {
      if (event.button !== 0) return;
      event.preventDefault();
      event.currentTarget.focus();
      event.currentTarget.setPointerCapture(event.pointerId);
      drag.current = { x: event.clientX, y: event.clientY, ...size };
    },
    onPointerMove(event) {
      if (!drag.current) return;
      update({ width: drag.current.width + direction * (event.clientX - drag.current.x), height: drag.current.height + event.clientY - drag.current.y });
    },
    onPointerUp() { drag.current = null; },
    onPointerCancel() { drag.current = null; },
    onKeyDown(event) {
      const change = { ArrowLeft: [-24, 0], ArrowRight: [24, 0], ArrowUp: [0, -24], ArrowDown: [0, 24] }[event.key];
      if (event.key === "Home") { event.preventDefault(); update({ width: initialWidth, height: initialHeight }); }
      else if (change) { event.preventDefault(); update({ width: size.width + change[0], height: size.height + change[1] }); }
    },
  };
  return { size, handle, reset: () => update({ width: initialWidth, height: initialHeight }) };
}
