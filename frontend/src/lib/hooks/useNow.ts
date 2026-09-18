"use client";

import { useEffect, useState } from "react";

/**
 * The current time, refreshed every `interval` ms. Kept in state so relative
 * times ("5 minutes ago") stay pure during render.
 */
export function useNow(interval = 60_000): number {
  const [now, setNow] = useState(0);
  useEffect(() => {
    const tick = () => setNow(Date.now());
    const first = window.setTimeout(tick, 0);
    const timer = window.setInterval(tick, interval);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [interval]);
  return now;
}
