import { describe, expect, it } from 'vitest';
import { DEMO_RADARS, freshDemo } from './demo';
import { fitView, keepInView, MAX_ZOOM, MIN_ZOOM, movePoint, normalizedWheel, toScreen, toWorld, zoomAt } from './model';

describe('camera geometry', () => {
  it('converts between screen and world coordinates', () => {
    const view = { x: 47, y: -19, zoom: .7 }, point = { x: -210, y: 375 };
    const result = toWorld(toScreen(point, view), view);
    expect(result.x).toBeCloseTo(point.x); expect(result.y).toBeCloseTo(point.y);
  });
  it('anchors zoom to the cursor, including clamped zoom', () => {
    const view = { x: 180, y: 70, zoom: 1.2 }, anchor = { x: 310, y: 450 };
    for (const factor of [.001, .8, 1.4, 100]) {
      const next = zoomAt(view, anchor, factor);
      expect(next.zoom).toBeGreaterThanOrEqual(MIN_ZOOM); expect(next.zoom).toBeLessThanOrEqual(MAX_ZOOM);
      expect(toWorld(anchor, next).x).toBeCloseTo(toWorld(anchor, view).x);
      expect(toWorld(anchor, next).y).toBeCloseTo(toWorld(anchor, view).y);
    }
  });
  it.each([{ width: 1366, height: 624 }, { width: 1600, height: 756 }, { width: 1920, height: 936 }])('fits every node with readable screen-sized labels at $width', size => {
    for (const panelWidth of [0, 370]) {
      const view = fitView(DEMO_RADARS, size, panelWidth);
      for (const radar of DEMO_RADARS) {
        const point = toScreen(radar, view);
        expect(point.x).toBeGreaterThanOrEqual(85); expect(point.x).toBeLessThanOrEqual(size.width - panelWidth - 85);
        expect(point.y).toBeGreaterThanOrEqual(100); expect(point.y).toBeLessThanOrEqual(size.height - 100);
      }
    }
  });
  it('adapts to data extent instead of using a fixed screenshot zoom', () => {
    const size = { width: 1366, height: 624 };
    const compact = fitView(DEMO_RADARS, size);
    const wide = fitView(DEMO_RADARS.map(r => ({ x: r.x * 3, y: r.y * 3 })), size);
    expect(wide.zoom).toBeLessThan(compact.zoom);
    expect(fitView([], size)).toEqual({ x: 683, y: 312, zoom: 1 });
    expect(Number.isFinite(fitView([{ x: 0, y: 0 }], size).zoom)).toBe(true);
  });
  it('moves a dragged node by screen delta at every zoom', () => {
    expect(movePoint({ x: 40, y: 30 }, { x: 20, y: -10 }, .5)).toEqual({ x: 80, y: 10 });
  });
  it('normalizes wheel units and caps trackpad bursts', () => {
    expect(normalizedWheel(3, 1, 624)).toBe(48);
    expect(normalizedWheel(-1, 2, 624)).toBe(-100);
    expect(normalizedWheel(4, 0, 624)).toBe(4);
  });
  it('keeps a selected point clear of the detail panel', () => {
    const point = { x: 900, y: 800 }, size = { width: 1366, height: 624 };
    const next = keepInView({ x: 0, y: 0, zoom: 1 }, point, size, 370);
    expect(toScreen(point, next)).toEqual({ x: 866, y: 464 });
  });
  it('isolates fixture copies and marks demo IDs as non-backend IDs', () => {
    const copy = freshDemo(); copy[0].x = 999;
    expect(DEMO_RADARS[0].x).toBe(-450);
    expect(copy.every(r => r.id.startsWith('demo-'))).toBe(true);
    expect(copy.reduce((sum, r) => sum + (r.signals ?? 0), 0)).toBe(24);
  });
});
