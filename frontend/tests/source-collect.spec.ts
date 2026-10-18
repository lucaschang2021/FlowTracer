import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const radarId = '00000000-0000-4000-8000-000000000011';
const sourceId = '00000000-0000-4000-8000-000000000021';
const runId = '00000000-0000-4000-8000-000000000031';
const radar = { id: radarId, name: 'Source Radar', description: 'Sources', goal: 'Track feeds', radarType: 'technology', categories: [], keywords: [], status: 'active', notificationThreshold: 75 };
const source = { id: sourceId, name: 'Primary feed', sourceType: 'rss', url: 'https://example.com/feed', normalizedUrl: 'https://example.com/feed', pollIntervalMinutes: 60, status: 'active' };
const user = { id: '00000000-0000-4000-8000-000000000001', email: 'person@example.com', displayName: 'Explorer', isActive: true };

async function signIn(page: Page) {
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
  await page.getByLabel('邮箱').fill(user.email); await page.getByLabel('密码').fill('not-a-real-password');
  await page.getByRole('button', { name: '登录并载入星图' }).click(); await expect(page.getByTestId('universe')).toHaveAttribute('data-mode', 'live');
}
async function openSources(page: Page) {
  await page.locator(`[data-radar="${radarId}"]`).click(); await page.getByRole('button', { name: '来源与采集' }).click();
  return page.getByRole('dialog', { name: '来源与采集' });
}

test('create then bind keeps the created identity across a failed bind retry', async ({ page }) => {
  await page.addInitScript(({ radar, user, source }) => {
    const state = window as typeof window & { __calls?: Record<string, number> }; state.__calls = { create: 0, bind: 0 };
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string, args?: { input?: unknown }) => {
      if (command === 'bridge_status') return { available: true }; if (command === 'health_ready') return { ready: true }; if (command === 'auth_login') return { authenticated: true, user }; if (command === 'users_me') return user; if (command === 'radars_list') return { items: [radar], page: 1, pageSize: 100, total: 1 };
      if (command === 'sources_list' || command === 'radar_sources_list') return { items: [], page: 1, pageSize: 20, total: 0 };
      if (command === 'sources_create') { state.__calls!.create += 1; return source; }
      if (command === 'radar_sources_bind') { state.__calls!.bind += 1; if (state.__calls!.bind === 1) throw { kind: 'api', message: 'Bind conflict', status: 409 }; return; }
      throw Error(`Unexpected command: ${command} ${JSON.stringify(args)}`);
    } } });
  }, { radar, user, source });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await signIn(page); const dialog = await openSources(page);
  await dialog.getByLabel('来源名称').fill('Primary feed'); await dialog.getByLabel(/来源 URL/).fill(source.url); await dialog.getByRole('button', { name: '创建并绑定' }).click();
  await expect(dialog.getByRole('alert')).toContainText('Bind conflict'); await expect(dialog).toContainText('重试不会重复创建'); await dialog.getByRole('button', { name: '重试绑定' }).click();
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __calls?: Record<string, number> }).__calls)).toEqual({ create: 1, bind: 2 }); await expect(dialog.getByLabel('来源名称')).toHaveValue('');
});

test('collect suppresses duplicate pending clicks, gets immediately, and polls to terminal status', async ({ page }) => {
  await page.addInitScript(({ radar, user, source, runId }) => {
    const state = window as typeof window & { __calls?: Record<string, number>; __keys?: string[]; __release?: () => void }; state.__calls = { collect: 0, run: 0 }; state.__keys = [];
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string, args?: { idempotencyKey?: string }) => {
      if (command === 'bridge_status') return { available: true }; if (command === 'health_ready') return { ready: true }; if (command === 'auth_login') return { authenticated: true, user }; if (command === 'users_me') return user; if (command === 'radars_list') return { items: [radar], page: 1, pageSize: 100, total: 1 };
      if (command === 'sources_list' || command === 'radar_sources_list') return { items: [source], page: 1, pageSize: 20, total: 1 };
      if (command === 'sources_collect') { state.__calls!.collect += 1; state.__keys!.push(args!.idempotencyKey!); return await new Promise(resolve => { state.__release = () => resolve({ runId, status: 'queued' }); }); }
      if (command === 'collection_runs_get') { state.__calls!.run += 1; return state.__calls!.run === 1 ? { id: runId, sourceId: source.id, status: 'running', fetchedCount: 1, createdCount: 0, duplicateCount: 0, failedCount: 0 } : { id: runId, sourceId: source.id, status: 'succeeded', fetchedCount: 3, createdCount: 2, duplicateCount: 1, failedCount: 0 }; }
      throw Error(`Unexpected command: ${command}`);
    } } });
  }, { radar, user, source, runId });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await signIn(page); const dialog = await openSources(page); const collect = dialog.getByRole('button', { name: '手动采集' });
  await collect.evaluate(button => { button.click(); button.click(); }); await expect.poll(() => page.evaluate(() => (window as typeof window & { __calls?: Record<string, number> }).__calls!.collect)).toBe(1); await page.evaluate(() => (window as typeof window & { __release?: () => void }).__release?.());
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __calls?: Record<string, number> }).__calls!.run)).toBeGreaterThanOrEqual(1); await expect(dialog).toContainText('running'); await expect(dialog).toContainText('succeeded', { timeout: 5000 }); await expect(dialog).toContainText('新建 2');
  expect(await page.evaluate(() => (window as typeof window & { __keys?: string[] }).__keys)).toHaveLength(1);
});

test('a refreshed generation ignores a late poll and closing prevents any later poll', async ({ page }) => {
  await page.addInitScript(({ radar, user, source, runId }) => {
    const state = window as typeof window & { __runCalls?: number; __collectCalls?: number; __releaseOld?: () => void }; state.__runCalls = 0; state.__collectCalls = 0;
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => {
      if (command === 'bridge_status') return { available: true }; if (command === 'health_ready') return { ready: true }; if (command === 'auth_login') return { authenticated: true, user }; if (command === 'users_me') return user; if (command === 'radars_list') return { items: [radar], page: 1, pageSize: 100, total: 1 };
      if (command === 'sources_list' || command === 'radar_sources_list') return { items: [source], page: 1, pageSize: 20, total: 1 };
      if (command === 'sources_collect') { state.__collectCalls! += 1; return { runId, status: 'queued' }; }
      if (command === 'collection_runs_get') { state.__runCalls! += 1; const call = state.__runCalls!; if (call === 1 || call === 4) return { id: runId, sourceId: source.id, status: 'running', fetchedCount: call, createdCount: 0, duplicateCount: 0, failedCount: 0 }; if (call === 2) return await new Promise(resolve => { state.__releaseOld = () => resolve({ id: runId, sourceId: source.id, status: 'failed', fetchedCount: 99, createdCount: 0, duplicateCount: 0, failedCount: 99 }); }); return { id: runId, sourceId: source.id, status: 'succeeded', fetchedCount: 3, createdCount: 2, duplicateCount: 1, failedCount: 0 }; }
      throw Error(`Unexpected command: ${command}`);
    } } });
  }, { radar, user, source, runId });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await signIn(page); let dialog = await openSources(page); await dialog.getByRole('button', { name: '手动采集' }).click(); await expect(dialog).toContainText('running');
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __runCalls?: number }).__runCalls), { timeout: 5000 }).toBe(2); await dialog.getByRole('button', { name: '查看最新状态' }).click(); await expect(dialog).toContainText('succeeded');
  await page.evaluate(() => (window as typeof window & { __releaseOld?: () => void }).__releaseOld?.()); await page.waitForTimeout(2200); await expect(dialog).toContainText('succeeded'); await expect(dialog).not.toContainText('失败 99'); expect(await page.evaluate(() => (window as typeof window & { __runCalls?: number }).__runCalls)).toBe(3);
  await dialog.getByRole('button', { name: '手动采集' }).click(); await expect(dialog).toContainText('running'); await dialog.getByRole('button', { name: '关闭来源与采集' }).click(); await expect(dialog).toHaveCount(0); await page.waitForTimeout(2200); expect(await page.evaluate(() => (window as typeof window & { __runCalls?: number }).__runCalls)).toBe(4);
});

test('503 retries the same intent key while a terminal run permits a new key', async ({ page }) => {
  await page.addInitScript(({ radar, user, source, runId }) => {
    const state = window as typeof window & { __keys?: string[] }; state.__keys = [];
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string, args?: { idempotencyKey?: string }) => {
      if (command === 'bridge_status') return { available: true }; if (command === 'health_ready') return { ready: true }; if (command === 'auth_login') return { authenticated: true, user }; if (command === 'users_me') return user; if (command === 'radars_list') return { items: [radar], page: 1, pageSize: 100, total: 1 };
      if (command === 'sources_list' || command === 'radar_sources_list') return { items: [source], page: 1, pageSize: 20, total: 1 };
      if (command === 'sources_collect') { state.__keys!.push(args!.idempotencyKey!); if (state.__keys!.length === 1) throw { kind: 'api', message: 'Collector unavailable', status: 503 }; return { runId, status: 'queued' }; }
      if (command === 'collection_runs_get') return { id: runId, sourceId: source.id, status: 'succeeded', fetchedCount: 1, createdCount: 1, duplicateCount: 0, failedCount: 0 };
      throw Error(`Unexpected command: ${command}`);
    } } });
  }, { radar, user, source, runId });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await signIn(page); const dialog = await openSources(page); await dialog.getByRole('button', { name: '手动采集' }).click(); await expect(dialog.getByRole('alert')).toContainText('Collector unavailable'); await dialog.getByRole('button', { name: '重试同次采集' }).click(); await expect(dialog).toContainText('succeeded');
  await dialog.getByRole('button', { name: '手动采集' }).click(); await expect.poll(() => page.evaluate(() => (window as typeof window & { __keys?: string[] }).__keys!.length)).toBe(3); const keys = await page.evaluate(() => (window as typeof window & { __keys?: string[] }).__keys!); expect(keys[1]).toBe(keys[0]); expect(keys[2]).not.toBe(keys[1]);
});

test('demo exposes no source or collection action and sends no writes', async ({ page }) => {
  await page.addInitScript(() => { (window as typeof window & { __writes?: number }).__writes = 0; Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => { if (command === 'bridge_status') return { available: true }; if (command === 'health_ready') return { ready: true }; if (/source|collect/.test(command)) (window as typeof window & { __writes?: number }).__writes = 1; throw Error(`Unexpected command: ${command}`); } } }); });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle'); await page.getByRole('button', { name: '进入演示星图' }).click(); await page.locator('[data-radar="demo-market"]').click();
  await expect(page.getByRole('button', { name: '来源与采集' })).toHaveCount(0); expect(await page.evaluate(() => (window as typeof window & { __writes?: number }).__writes)).toBe(0);
});
