import { MAX_ZOOM, MIN_ZOOM } from './model';
import type { Point, UniverseRadar, View } from './model';

export const LAYOUT_VERSION = 1;
export const DEMO_OWNER = 'demo';
export const MAX_POSITIONS = 500;
export const MAX_GALAXIES = 50;
export const MAX_MEMBERS = 100;
export const MAX_NAME_LENGTH = 64;
const COORDINATE_LIMIT = 1_000_000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DEMO_RADAR = /^demo-[a-z0-9-]{1,80}$/;

export type Galaxy = { id: string; name: string; members: string[] };
export type SpatialLayout = { version: typeof LAYOUT_VERSION; owner: string; positions: Record<string, Point>; view: View; galaxies: Galaxy[] };
export type LayoutRead = { ok: true; value: SpatialLayout } | { ok: false; reason: string };

export const validUuid = (value: unknown): value is string => typeof value === 'string' && UUID.test(value);
export const validOwner = (value: unknown): value is string => value === DEMO_OWNER || validUuid(value);
export const storageKey = (owner: string) => `flowtracer:spatial:v${LAYOUT_VERSION}:${owner}`;
const finite = (value: unknown, limit = COORDINATE_LIMIT): value is number => typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= limit;
const validRadarId = (value: unknown, owner: string): value is string => validUuid(value) || (owner === DEMO_OWNER && typeof value === 'string' && DEMO_RADAR.test(value));

export function emptyLayout(owner: string, view: View): SpatialLayout { return { version: LAYOUT_VERSION, owner, positions: {}, view, galaxies: [] }; }

export function parseLayout(raw: string | null, expectedOwner: string): LayoutRead {
  if (!validOwner(expectedOwner)) return { ok: false, reason: 'invalid-owner' };
  if (raw === null) return { ok: false, reason: 'empty' };
  let input: unknown;
  try { input = JSON.parse(raw); } catch { return { ok: false, reason: 'invalid-json' }; }
  if (!input || typeof input !== 'object') return { ok: false, reason: 'invalid-root' };
  const value = input as Record<string, unknown>;
  if (value.version !== LAYOUT_VERSION) return { ok: false, reason: 'unsupported-version' };
  if (value.owner !== expectedOwner) return { ok: false, reason: 'owner-mismatch' };
  const sourceView = value.view as Record<string, unknown> | null;
  if (!sourceView || !finite(sourceView.x) || !finite(sourceView.y) || !finite(sourceView.zoom, MAX_ZOOM) || sourceView.zoom < MIN_ZOOM || sourceView.zoom > MAX_ZOOM) return { ok: false, reason: 'invalid-view' };
  const sourcePositions = value.positions;
  if (!sourcePositions || typeof sourcePositions !== 'object' || Array.isArray(sourcePositions)) return { ok: false, reason: 'invalid-positions' };
  const positionEntries = Object.entries(sourcePositions as Record<string, unknown>);
  if (positionEntries.length > MAX_POSITIONS) return { ok: false, reason: 'position-capacity' };
  const positions: Record<string, Point> = {};
  for (const [id, pointValue] of positionEntries) {
    const point = pointValue as Record<string, unknown> | null;
    if (!validRadarId(id, expectedOwner) || !point || !finite(point.x) || !finite(point.y)) return { ok: false, reason: 'invalid-position' };
    positions[id] = { x: point.x, y: point.y };
  }
  if (!Array.isArray(value.galaxies) || value.galaxies.length > MAX_GALAXIES) return { ok: false, reason: 'invalid-galaxies' };
  const galaxyIds = new Set<string>(), claimedMembers = new Set<string>();
  const galaxies: Galaxy[] = [];
  for (const candidate of value.galaxies) {
    if (!candidate || typeof candidate !== 'object') return { ok: false, reason: 'invalid-galaxy' };
    const galaxy = candidate as Record<string, unknown>;
    if (!validUuid(galaxy.id) || galaxyIds.has(galaxy.id)) return { ok: false, reason: 'invalid-galaxy-id' };
    const name = typeof galaxy.name === 'string' ? galaxy.name.trim() : '';
    if (!name || name.length > MAX_NAME_LENGTH || !Array.isArray(galaxy.members) || galaxy.members.length < 2 || galaxy.members.length > MAX_MEMBERS) return { ok: false, reason: 'invalid-galaxy-content' };
    const members: string[] = [], local = new Set<string>();
    for (const member of galaxy.members) {
      if (!validRadarId(member, expectedOwner) || local.has(member) || claimedMembers.has(member)) return { ok: false, reason: 'invalid-galaxy-member' };
      local.add(member); claimedMembers.add(member); members.push(member);
    }
    galaxyIds.add(galaxy.id); galaxies.push({ id: galaxy.id, name, members });
  }
  return { ok: true, value: { version: LAYOUT_VERSION, owner: expectedOwner, positions, view: { x: sourceView.x, y: sourceView.y, zoom: sourceView.zoom }, galaxies } };
}

export function applyPositions(radars: UniverseRadar[], positions: Record<string, Point>): UniverseRadar[] { return radars.map(radar => positions[radar.id] ? { ...radar, ...positions[radar.id] } : radar); }

export function mergePositions(positions: Record<string, Point>, radars: UniverseRadar[]): Record<string, Point> {
  const merged = { ...positions };
  for (const radar of radars) merged[radar.id] = { x: radar.x, y: radar.y };
  return merged;
}

export function serializeLayout(owner: string, positions: Record<string, Point>, view: View, galaxies: Galaxy[]): string {
  if (!validOwner(owner)) throw new Error('invalid-owner');
  const candidate = JSON.stringify({ version: LAYOUT_VERSION, owner, positions, view, galaxies });
  const parsed = parseLayout(candidate, owner);
  if (!parsed.ok) throw new Error(parsed.reason);
  return JSON.stringify(parsed.value);
}

export function galaxyBounds(galaxy: Galaxy, radars: UniverseRadar[]): { x: number; y: number; width: number; height: number } | null {
  const members = radars.filter(radar => galaxy.members.includes(radar.id));
  if (!members.length) return null;
  const xs = members.map(radar => radar.x), ys = members.map(radar => radar.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  return { x: minX - 120, y: minY - 105, width: Math.max(320, maxX - minX + 240), height: Math.max(250, maxY - minY + 210) };
}
