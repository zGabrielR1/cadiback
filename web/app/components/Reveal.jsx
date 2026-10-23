"use client";

import { useEffect, useRef } from "react";

/** A small scroll-reveal wrapper for the editorial layer.
 *
 *  The `.js` class set in <head> arms the hidden state, so a reader without
 *  JavaScript sees every section. The observer arms once, and reduced-motion
 *  readers skip the animation entirely. */
export default function Reveal({
  as: Tag = "div",
  className = "",
  delay = 0,
  children,
  style,
  ...rest
}) {
  const ref = useRef(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;

    const show = () => node.classList.add("is-visible");
    if (typeof IntersectionObserver !== "function") {
      show();
      return undefined;
    }
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches) {
      show();
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          show();
          observer.disconnect();
        }
      },
      { threshold: 0.06, rootMargin: "0px 0px -48px 0px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const classes = ["ed-reveal", className].filter(Boolean).join(" ");
  const mergedStyle = delay ? { "--reveal-delay": `${delay}ms`, ...style } : style;

  return (
    <Tag ref={ref} className={classes} style={mergedStyle} {...rest}>
      {children}
    </Tag>
  );
}
