import { describe, expect, it } from 'vitest';
import { readPreferences } from './Preferences';

describe('local demo preferences', () => {
  it('defaults to Chinese without stored preferences', () => {
    expect(readPreferences({ getItem: () => null })).toEqual({ locale: 'zh-CN', quiet: false });
  });
  it('restores only validated display preferences', () => {
    expect(readPreferences({ getItem: () => '{"locale":"en","quiet":true,"token":"ignored"}' })).toEqual({ locale: 'en', quiet: true });
    expect(readPreferences({ getItem: () => '{"locale":"unknown","quiet":"false"}' })).toEqual({ locale: 'zh-CN', quiet: false });
  });
  it('survives corrupt or unavailable storage', () => {
    for (const value of ['{bad', 'null', '[]']) expect(readPreferences({ getItem: () => value })).toEqual({ locale: 'zh-CN', quiet: false });
    expect(readPreferences({ getItem: () => { throw new Error('Storage unavailable'); } })).toEqual({ locale: 'zh-CN', quiet: false });
  });
});
