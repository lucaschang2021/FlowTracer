import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const ownerA = '00000000-0000-4000-8000-000000000001';
const ownerB = '00000000-0000-4000-8000-000000000002';
const target = '00000000-0000-4000-8000-000000000011';
const hidden = '00000000-0000-4000-8000-000000000012';
const hidden2 = '00000000-0000-4000-8000-000000000013';
const galaxy = '00000000-0000-4000-8000-000000000021';
const key = (owner: string) => `flowtracer:spatial:v1:${owner}`;
const layout = (owner: string, members = [target, hidden, hidden2]) => ({ version: 1, owner, positions: { [target]: { x: 300, y: 240 }, [hidden]: { x: 700, y: 350 }, [hidden2]: { x: 900, y: 500 } }, view: { x: 0, y: 0, zoom: 1 }, galaxies: [{ id: galaxy, name: 'Saved group', members }] });
type Fixture = typeof window & { __deleteCalls: number; __releaseDelete: () => void; __flushViews: () => void; __holdViews: boolean; __pendingViews: () => number };

async function setup(page: Page, fail: boolean, pair = false) {
  await page.addInitScript(({ ownerA, ownerB, target, a, b, fail }) => {
    localStorage.setItem(`flowtracer:spatial:v1:${ownerA}`, JSON.stringify(a));
    localStorage.setItem(`flowtracer:spatial:v1:${ownerB}`, JSON.stringify(b));
    const state = window as Fixture;
    state.__deleteCalls = 0;
    state.__holdViews = false;
    let logins = 0;
    const original = window.setTimeout.bind(window), clear = window.clearTimeout.bind(window);
    const delayed = new Map<number, () => void>(); let timer = -1;
    window.setTimeout = ((fn: TimerHandler, delay?: number, ...args: unknown[]) => {
      if (state.__holdViews && delay === 180 && typeof fn === 'function') { const id = timer--; delayed.set(id, () => fn(...args)); return id; }
      return original(fn, delay, ...args);
    }) as typeof window.setTimeout;
    window.clearTimeout = id => { delayed.delete(id!); clear(id); };
    state.__flushViews = () => { const tasks = [...delayed.values()]; delayed.clear(); tasks.forEach(fn => fn()); };
    state.__pendingViews = () => delayed.size;
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string, args?: { radarId?: string }) => {
      const user = { id: logins > 1 ? ownerB : ownerA, email: 'person@example.com', displayName: 'Explorer', isActive: true };
      if (command === 'bridge_status') return { available: true };
      if (command === 'health_ready') return { ready: true };
      if (command === 'auth_login') { logins++; return { authenticated: true }; }
      if (command === 'users_me') return user;
      if (command === 'auth_logout') return;
      if (command === 'radars_list') return { items: [{ id: target, name: 'Delete target', description: '', goal: 'Track', radarType: 'technology', categories: [], keywords: [], status: 'active', notificationThreshold: 75 }], page: 1, pageSize: 100, total: 3 };
      if (command === 'radars_delete') {
        if (args?.radarId !== target) throw Error('wrong delete identity');
        state.__deleteCalls++;
        if (fail) throw { kind: 'api', message: 'Deletion refused', status: 409 };
        return new Promise<void>(resolve => { state.__releaseDelete = resolve; });
      }
      throw Error(`Unexpected command: ${command}`);
    } } });
  }, { ownerA, ownerB, target, a: layout(ownerA, pair ? [target, hidden] : undefined), b: layout(ownerB), fail });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await login(page);
  // Arm only around selection on the settled Canvas: this queues its view save.
  // Login, navigation and account-switch timers always use the real scheduler.
  await expect(page.locator('.page-scene')).toHaveAttribute('data-motion', 'idle');
  await page.evaluate(() => { (window as Fixture).__holdViews = true; });
  try { await page.locator(`[data-radar="${target}"]`).click(); }
  finally { await page.evaluate(() => { (window as Fixture).__holdViews = false; }); }
  expect(await page.evaluate(() => (window as Fixture).__pendingViews())).toBe(1);
  await page.getByRole('button', { name: '移除 Radar' }).click();
}
async function login(page: Page) {
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
  await page.getByLabel('邮箱').fill('person@example.com'); await page.getByLabel('密码').fill('fixture-password');
  await page.getByRole('button', { name: '登录并载入星图' }).click();
  await expect(page.getByTestId('universe')).toHaveAttribute('data-mode', 'live');
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
}
async function stored(page: Page, owner = ownerA) { return page.evaluate(k => JSON.parse(localStorage.getItem(k)!), key(owner)); }

for (const outcome of ['success', 'cancel', 'failure', 'pair'] as const) {
  test(`confirmed Radar deletion layout: ${outcome}`, async ({ page }) => {
    await setup(page, outcome === 'failure', outcome === 'pair');
    const dialog = page.getByRole('dialog', { name: '移除 Radar' });
    if (outcome === 'cancel') await dialog.getByRole('button', { name: '取消' }).click();
    else {
      await dialog.getByRole('button', { name: '确认移除“Delete target”' }).click();
      await expect.poll(() => page.evaluate(() => (window as Fixture).__deleteCalls)).toBe(1);
      expect((await stored(page)).positions).toEqual(layout(ownerA).positions);
      if (outcome === 'failure') await expect(dialog.getByRole('alert')).toContainText('Deletion refused');
      else { await page.evaluate(() => (window as Fixture).__releaseDelete()); await expect(dialog).toHaveCount(0); }
    }
    await page.evaluate(() => (window as Fixture).__flushViews());
    const result = await stored(page), removed = outcome === 'success' || outcome === 'pair';
    expect(result.positions).toEqual(removed ? { [hidden]: layout(ownerA).positions[hidden], [hidden2]: layout(ownerA).positions[hidden2] } : layout(ownerA).positions);
    expect(result.galaxies).toEqual(outcome === 'pair' ? [] : [{ id: galaxy, name: 'Saved group', members: removed ? [hidden, hidden2] : [target, hidden, hidden2] }]);
    expect(await stored(page, ownerB)).toEqual(layout(ownerB));
    expect(await page.evaluate(() => (window as Fixture).__deleteCalls)).toBe(outcome === 'cancel' ? 0 : 1);
    await expect(page.locator(`[data-radar="${target}"]`)).toHaveCount(removed ? 0 : 1);
  });
}

test('confirmed Radar deletion layout: late A response cannot clean B or A', async ({ page }) => {
  await setup(page, false);
  await page.getByRole('button', { name: '确认移除“Delete target”' }).click();
  await expect.poll(() => page.evaluate(() => (window as Fixture).__deleteCalls)).toBe(1);
  await page.locator('.main-nav button').filter({ hasText: /^设置$/ }).dispatchEvent('click');
  await page.locator('.settings-list .setting-row').filter({ has: page.getByRole('button', { name: '刷新会话', exact: true }) }).locator('button:visible').filter({ hasText: /^退出登录$/ }).dispatchEvent('click');
  await expect(page.getByRole('heading', { name: '欢迎回来。' })).toBeVisible(); await login(page);
  await page.evaluate(async () => { (window as Fixture).__releaseDelete(); await new Promise(resolve => setTimeout(resolve, 0)); (window as Fixture).__flushViews(); });
  expect((await stored(page)).positions).toEqual(layout(ownerA).positions);
  expect((await stored(page)).galaxies).toEqual(layout(ownerA).galaxies);
  expect(await stored(page, ownerB)).toEqual(layout(ownerB));
  await expect(page.locator(`[data-radar="${target}"]`)).toHaveCount(1);
});
