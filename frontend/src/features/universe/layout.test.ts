import { describe, expect, it } from 'vitest';
import { applyPositions, DEMO_OWNER, emptyLayout, mergePositions, parseLayout, serializeLayout, storageKey } from './layout';
import type { UniverseRadar } from './model';

const OWNER = '11111111-1111-4111-8111-111111111111', RADAR_A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', RADAR_B = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', GALAXY = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
const radar = (id: string, x = 1): UniverseRadar => ({ id, x, y: 2, name: id, type: 'custom', status: 'active', signals: null, description: '', color: 'blue', dataSource: 'live' });

describe('versioned spatial layout', () => {
  it('round trips only spatial state and keeps owners in separate keys', () => {
    const raw = serializeLayout(OWNER, mergePositions({}, [radar(RADAR_A), radar(RADAR_B, 3)]), { x: 4, y: 5, zoom: 1.2 }, [{ id: GALAXY, name: 'Watch', members: [RADAR_A, RADAR_B] }]);
    expect(parseLayout(raw, OWNER)).toEqual({ ok: true, value: JSON.parse(raw) }); expect(raw).not.toContain('token'); expect(storageKey(OWNER)).not.toBe(storageKey(DEMO_OWNER));
    expect(parseLayout(raw, '22222222-2222-4222-8222-222222222222')).toEqual({ ok: false, reason: 'owner-mismatch' });
  });
  it.each([
    ['broken JSON', '{', 'invalid-json'],
    ['future version', JSON.stringify({ ...emptyLayout(OWNER, { x: 0, y: 0, zoom: 1 }), version: 2 }), 'unsupported-version'],
    ['non finite coordinate', JSON.stringify({ ...emptyLayout(OWNER, { x: 0, y: 0, zoom: 1 }), positions: { [RADAR_A]: { x: null, y: 0 } } }), 'invalid-position'],
    ['duplicate member', JSON.stringify({ ...emptyLayout(OWNER, { x: 0, y: 0, zoom: 1 }), galaxies: [{ id: GALAXY, name: 'A', members: [RADAR_A, RADAR_A] }] }), 'invalid-galaxy-member'],
  ])('rejects %s without partial recovery', (_label, raw, reason) => expect(parseLayout(raw, OWNER)).toEqual({ ok: false, reason }));
  it('restores visible positions without deleting unloaded references', () => {
    const visible = [radar(RADAR_A)];
    expect(applyPositions(visible, { [RADAR_A]: { x: 9, y: 8 }, [RADAR_B]: { x: 7, y: 6 } })).toEqual([{ ...visible[0], x: 9, y: 8 }]);
  });
  it('merges a visible update without dropping an unloaded position on round trip', () => {
    const positions = mergePositions({ [RADAR_A]: { x: 1, y: 2 }, [RADAR_B]: { x: 7, y: 6 } }, [{ ...radar(RADAR_A), x: 9, y: 8 }]);
    const raw = serializeLayout(OWNER, positions, { x: 0, y: 0, zoom: 1 }, []);
    const read = parseLayout(raw, OWNER);
    expect(read.ok && read.value.positions).toEqual({ [RADAR_A]: { x: 9, y: 8 }, [RADAR_B]: { x: 7, y: 6 } });
  });
  it('accepts demo fixture ids only inside the isolated demo owner', () => {
    const raw = serializeLayout(DEMO_OWNER, mergePositions({}, [{ ...radar('demo-one'), dataSource: 'demo' }]), { x: 0, y: 0, zoom: 1 }, []);
    expect(parseLayout(raw, DEMO_OWNER).ok).toBe(true); expect(() => serializeLayout(OWNER, { 'demo-one': { x: 1, y: 2 } }, { x: 0, y: 0, zoom: 1 }, [])).toThrow('invalid-position');
  });
});
