import { useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';

// Exact star placement and current field from the approved standalone intro.
const brightStars = [[12,18,-2,12],[28,35,-7,15],[39,11,-4,13],[66,21,-11,17],[84,36,-5,14],[92,15,-1,11],[19,73,-9,18],[33,85,-3,12],[59,76,-13,19],[77,81,-6,15],[88,65,-8,16],[9,53,-4,14]];
const scatter = (seed: number) => { const value = Math.sin(seed * 127.17) * 43758.5453; return value - Math.floor(value); };
const points = Array.from({ length: 145 }, (_, index) => ({
  x: 15 + scatter(index + 1) * 1335, y: 12 + scatter(index + 173) * 744,
  phase: scatter(index + 311) * Math.PI * 2, alpha: .10 + scatter(index + 509) * .19,
  size: index % 17 === 0 ? 1.7 : .7 + scatter(index + 719) * .65,
}));
function currentOffset(x: number, y: number, phase: number, seconds: number) {
  return {
    x: Math.sin(y * .016 - seconds * .14 + phase) * 7.2 + Math.sin(x * .011 + seconds * .075 + phase * .7) * 3.1,
    y: Math.cos(x * .013 + seconds * .13 + phase) * 4.3 + Math.sin(y * .011 - seconds * .09) * 2.2,
  };
}

export function OriginalBackdrop({ reduced }: { reduced: boolean }) {
  const backdrop = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const stars = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = backdrop.current;
    if (!element) return;
    let frame = 0;
    let x = 0, y = 0;
    const reset = () => {
      cancelAnimationFrame(frame); frame = 0;
      element.style.translate = '0px 0px';
    };
    reset();
    if (reduced) return;
    const paint = () => {
      frame = 0;
      element.style.translate = `${x.toFixed(2)}px ${y.toFixed(2)}px`;
    };
    const move = (event: PointerEvent) => {
      if (event.pointerType !== 'mouse') return;
      if (event.buttons || document.hidden) { reset(); return; }
      x = Math.max(-12, Math.min(12, (event.clientX / Math.max(1, window.innerWidth) - .5) * 24));
      y = Math.max(-9, Math.min(9, (event.clientY / Math.max(1, window.innerHeight) - .5) * 18));
      if (!frame) frame = requestAnimationFrame(paint);
    };
    const leave = (event: PointerEvent) => { if (!event.relatedTarget) reset(); };
    window.addEventListener('pointermove', move, { passive: true });
    window.addEventListener('pointerout', leave, { passive: true });
    window.addEventListener('blur', reset);
    window.addEventListener('resize', reset);
    document.addEventListener('visibilitychange', reset);
    return () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerout', leave);
      window.removeEventListener('blur', reset);
      window.removeEventListener('resize', reset);
      document.removeEventListener('visibilitychange', reset);
      reset();
    };
  }, [reduced]);
  useEffect(() => {
    const element = canvas.current;
    const ink = element?.getContext('2d');
    if (!element || !ink) return;
    const scale = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
    element.width = Math.round(1365 * scale); element.height = Math.round(768 * scale);
    ink.setTransform(scale, 0, 0, scale, 0, 0);
    let frame = 0, last = 0;
    const draw = (seconds: number) => {
      ink.clearRect(0, 0, 1365, 768); ink.shadowColor = 'rgba(145,206,229,.38)';
      for (const point of points) {
        const drift = reduced ? { x: 0, y: 0 } : currentOffset(point.x, point.y, point.phase, seconds);
        const shimmer = reduced ? .72 : .62 + .38 * Math.sin(seconds * .32 + point.phase);
        ink.fillStyle = `rgba(165,208,226,${(point.alpha * shimmer).toFixed(3)})`;
        ink.shadowBlur = point.size > 1.5 ? 9 : 0;
        ink.fillRect(point.x + drift.x, point.y + drift.y, point.size, point.size);
      }
      ink.shadowBlur = 0;
      stars.current?.querySelectorAll('i').forEach((star, index) => {
        const drift = reduced ? { x: 0, y: 0 } : currentOffset(brightStars[index][0] * 13.65, brightStars[index][1] * 7.68, index * .61, seconds);
        star.style.translate = `${(drift.x * .8).toFixed(2)}px ${(drift.y * .8).toFixed(2)}px`;
      });
    };
    const animate = (now: number) => { frame = requestAnimationFrame(animate); if (now - last < 33) return; last = now; draw(now / 1000); };
    const resume = () => { cancelAnimationFrame(frame); if (reduced) draw(0); else if (!document.hidden) frame = requestAnimationFrame(animate); };
    draw(0); resume(); document.addEventListener('visibilitychange', resume);
    return () => { cancelAnimationFrame(frame); document.removeEventListener('visibilitychange', resume); };
  }, [reduced]);
  return <div ref={backdrop} className="original-backdrop" data-testid="original-backdrop" aria-hidden="true">
    <div className="original-orbit-system"><div className="original-orbit-art"/></div>
    <div className="original-breath"/><div className="original-ambient"/>
    <div className="original-polar-grid"><svg viewBox="0 0 800 800" focusable="false">
      <g className="original-polar-lines"><circle cx="400" cy="400" r="92"/><circle cx="400" cy="400" r="190"/><circle cx="400" cy="400" r="286"/><circle cx="400" cy="400" r="374"/><path d="M400 26V774 M26 400H774 M76 213L724 587 M213 76L587 724 M76 587L724 213 M213 724L587 76"/></g>
      <g className="original-polar-secondary"><circle cx="400" cy="400" r="334"/><circle cx="400" cy="400" r="238"/><path d="M112 112L688 688 M688 112L112 688"/></g>
      <g className="original-polar-accents"><path d="M398 26 A374 374 0 0 1 724 213 M211 723 A374 374 0 0 1 77 586 M550 319 A190 190 0 0 1 590 400 M238 300 A190 190 0 0 1 255 276"/><circle cx="400" cy="26" r="2.2"/><circle cx="724" cy="213" r="1.6"/><circle cx="211" cy="723" r="1.8"/></g>
    </svg></div>
    <canvas ref={canvas} className="original-flowing-stars"/>
    <div ref={stars} className="original-stars">{brightStars.map(([x,y,delay,duration], index) => <i key={index} style={{ '--x': `${x}%`, '--y': `${y}%`, '--d': `${delay}s`, '--t': `${duration}s` } as CSSProperties}/>)}</div>
  </div>;
}
