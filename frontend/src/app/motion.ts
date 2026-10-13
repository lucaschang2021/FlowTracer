import { useCallback, useEffect, useRef, useState } from 'react';
import { usePreferences } from './Preferences';

export function useReducedMotion() {
  const { quiet } = usePreferences();
  const [system, setSystem] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const media = matchMedia('(prefers-reduced-motion: reduce)');
    const change = () => setSystem(media.matches);
    media.addEventListener('change', change);
    return () => media.removeEventListener('change', change);
  }, []);
  return quiet || system;
}

/** Last intent wins; no animationend dependency, stale timers or hidden-tab deadlocks. */
export function useScene<T extends string>(initial: T) {
  const reduced = useReducedMotion();
  const [value, setValue] = useState(initial);
  const [phase, setPhase] = useState<'idle' | 'out' | 'in' | 'enter'>('idle');
  const current = useRef(initial);
  const target = useRef(initial);
  const status = useRef(phase);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const frame = useRef(0);
  const clear = useCallback(() => { clearTimeout(timer.current); cancelAnimationFrame(frame.current); }, []);
  const mark = useCallback((next: typeof phase) => { status.current = next; setPhase(next); }, []);
  const settle = useCallback(() => { clear(); current.current = target.current; setValue(target.current); mark('idle'); }, [clear, mark]);
  useEffect(() => { if (reduced) settle(); return clear; }, [reduced, settle, clear]);
  useEffect(() => {
    const visibility = () => { if (document.hidden) settle(); };
    document.addEventListener('visibilitychange', visibility);
    return () => document.removeEventListener('visibilitychange', visibility);
  }, [settle]);
  const change = useCallback((next: T) => {
    target.current = next;
    if (reduced || document.hidden) { settle(); return; }
    if (status.current === 'out' || (current.current === next && status.current === 'idle')) return;
    clear(); mark('out');
    timer.current = setTimeout(() => {
      current.current = target.current; setValue(target.current); mark('in');
      frame.current = requestAnimationFrame(() => {
        frame.current = requestAnimationFrame(() => {
          mark('enter'); timer.current = setTimeout(() => mark('idle'), 340);
        });
      });
    }, 180);
  }, [reduced, settle, clear, mark]);
  return { value, phase, change, busy: phase !== 'idle' };
}
