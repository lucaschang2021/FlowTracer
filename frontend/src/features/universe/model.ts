export type Point = { x: number; y: number };
export type View = Point & { zoom: number };
export type Size = { width: number; height: number };
export type RadarType = 'academic' | 'business' | 'technology' | 'market' | 'policy' | 'competitive' | 'custom' | 'opportunity';
export type DemoRadar = Point & {
  id: string; name: string; type: RadarType;
  status: 'active' | 'paused'; signals: number; description: string; color: string;
};
export const MIN_ZOOM = 0.35;
export const MAX_ZOOM = 2.4;
export const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

export function toWorld(point: Point, view: View): Point {
  return { x: (point.x - view.x) / view.zoom, y: (point.y - view.y) / view.zoom };
}

export function toScreen(point: Point, view: View): Point {
  return { x: point.x * view.zoom + view.x, y: point.y * view.zoom + view.y };
}

export function zoomAt(view: View, anchor: Point, factor: number): View {
  const zoom = clamp(view.zoom * factor, MIN_ZOOM, MAX_ZOOM);
  const world = toWorld(anchor, view);
  return { x: anchor.x - world.x * zoom, y: anchor.y - world.y * zoom, zoom };
}

export function fitView(points: readonly Point[], size: Size, panelWidth = 0): View {
  const width = Math.max(200, size.width - panelWidth);
  const height = Math.max(200, size.height);
  if (!points.length) return { x: width / 2, y: height / 2, zoom: 1 };
  const xs = points.map(p => p.x), ys = points.map(p => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  // Node art / labels stay screen-sized; reserve their footprint at every zoom.
  const zoom = clamp(Math.min((width - 270) / Math.max(1, maxX - minX), (height - 340) / Math.max(1, maxY - minY), 1.25), MIN_ZOOM, MAX_ZOOM);
  return { x: width / 2 - (minX + maxX) * zoom / 2, y: height / 2 - (minY + maxY) * zoom / 2, zoom };
}

export function movePoint(point: Point, delta: Point, zoom: number): Point {
  return { x: point.x + delta.x / zoom, y: point.y + delta.y / zoom };
}

export function normalizedWheel(delta: number, mode: number, height: number): number {
  return clamp(delta * (mode === 1 ? 16 : mode === 2 ? height : 1), -100, 100);
}

export function keepInView(view: View, point: Point, size: Size, panelWidth: number): View {
  const screen = toScreen(point, view);
  const right = Math.max(130, size.width - panelWidth - 130);
  const bottom = Math.max(140, size.height - 160);
  return { ...view, x: view.x + clamp(screen.x, 130, right) - screen.x, y: view.y + clamp(screen.y, 140, bottom) - screen.y };
}
