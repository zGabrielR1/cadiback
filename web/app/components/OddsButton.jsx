"use client";

import { useEffect, useRef, useState } from 'react';

/** Movement is derived only from a changed quote for this selection. */
export default function OddsButton({ price, children, ...props }) {
  const previous = useRef(price);
  const [direction, setDirection] = useState('');
  useEffect(() => {
    if (previous.current === price) return;
    setDirection(price > previous.current ? 'up' : 'down');
    previous.current = price;
    const timeout = setTimeout(() => setDirection(''), 1800);
    return () => clearTimeout(timeout);
  }, [price]);
  return <button {...props} data-odds-change={direction || undefined}>{children}{direction ? <span className="odds-movement" aria-label={direction === 'up' ? 'Cotação aumentou' : 'Cotação diminuiu'}>{direction === 'up' ? '↑' : '↓'}</span> : null}</button>;
}
