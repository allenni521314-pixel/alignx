import { useState, useEffect, useRef } from "react";

export function useProgress(analyzing: boolean, done: boolean) {
  const [pct, setPct] = useState(0);
  const ref = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!analyzing) { setPct(0); if (ref.current) clearInterval(ref.current); return; }
    if (done) { setPct(100); if (ref.current) clearInterval(ref.current); return; }
    setPct(0);
    ref.current = setInterval(() => setPct(p => Math.min(90, p + 3)), 300);
    return () => { if (ref.current) clearInterval(ref.current); };
  }, [analyzing, done]);

  return pct;
}
