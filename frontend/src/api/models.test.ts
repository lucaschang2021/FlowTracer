import { describe, expect, it } from 'vitest';
import { mapRadarPage, toUniverseRadar } from './models';
import type { RadarRecord, RadarType } from './desktop';

const base = (type: RadarType, index: number): RadarRecord => ({
  id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
  name: type,
  description: null,
  goal: `Track ${type}`,
  radarType: type,
  categories: [],
  keywords: [],
  status: index % 3 === 0 ? 'active' : index % 3 === 1 ? 'paused' : 'archived',
  notificationThreshold: 75,
});

describe('live Radar mapping', () => {
  it('maps all eight frozen Radar types without inventing signal counts', () => {
    const kinds: RadarType[] = ['academic', 'business', 'technology', 'market', 'policy', 'competitive', 'custom', 'opportunity'];
    const result = mapRadarPage({ items: kinds.map(base), page: 1, pageSize: 100, total: kinds.length });
    expect(result.map(item => item.type)).toEqual(kinds);
    expect(result.every(item => item.dataSource === 'live' && item.signals === null)).toBe(true);
    expect(result.map(item => item.status)).toContain('archived');
  });

  it('rejects demo identities and unknown enums in live records', () => {
    expect(() => toUniverseRadar({ ...base('custom', 0), id: 'demo-ai' }, 0, 1)).toThrow(/identity/);
    expect(() => toUniverseRadar({ ...base('custom', 0), radarType: 'unknown' as RadarType }, 0, 1)).toThrow(/enum/);
  });
});
