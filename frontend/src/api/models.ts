import type { RadarPage, RadarRecord, RadarType, ResourceStatus } from './desktop';
import type { UniverseRadar } from '../features/universe/model';

const types = new Set<RadarType>(['academic', 'business', 'technology', 'market', 'policy', 'competitive', 'custom', 'opportunity']);
const statuses = new Set<ResourceStatus>(['active', 'paused', 'archived']);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const colors: Record<RadarType, string> = {
  academic: 'teal', business: 'gold', technology: 'blue', market: 'gold',
  policy: 'ice', competitive: 'violet', custom: 'silver', opportunity: 'silver',
};

export function toUniverseRadar(record: RadarRecord, index: number, total: number): UniverseRadar {
  if (!uuid.test(record.id) || record.id.startsWith('demo-')) throw new Error('Backend Radar identity is invalid.');
  if (!types.has(record.radarType) || !statuses.has(record.status)) throw new Error('Backend Radar enum is invalid.');
  const count = Math.max(1, total);
  const ring = 220 + Math.floor(index / 8) * 180;
  const angle = (index % 8) / Math.min(8, count) * Math.PI * 2 - Math.PI / 2;
  return {
    id: record.id,
    name: record.name,
    type: record.radarType,
    status: record.status,
    signals: null,
    x: Math.cos(angle) * ring,
    y: Math.sin(angle) * ring * .62,
    color: colors[record.radarType],
    description: record.description?.trim() || record.goal,
    dataSource: 'live',
  };
}

export function mapRadarPage(page: RadarPage): UniverseRadar[] {
  if (!Number.isInteger(page.total) || page.total < 0 || !Array.isArray(page.items)) throw new Error('Backend Radar page is invalid.');
  return page.items.map((record, index) => toUniverseRadar(record, index, page.items.length));
}
