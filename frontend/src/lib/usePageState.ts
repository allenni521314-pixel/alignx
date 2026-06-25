import { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

export function usePageState<T>(key: string, initial: T): [T, (v: T) => void] {
  const { pathname } = useLocation();
  const storageKey = `alignx_state_${pathname}_${key}`;

  const [state, setState] = useState<T>(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      return saved ? JSON.parse(saved) : initial;
    } catch {
      return initial;
    }
  });

  const initRef = useRef(true);
  useEffect(() => {
    if (initRef.current) { initRef.current = false; return; }
    try { localStorage.setItem(storageKey, JSON.stringify(state)); } catch {}
  }, [state, storageKey]);

  return [state, setState];
}
