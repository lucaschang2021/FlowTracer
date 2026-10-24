import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

type Ledger = { account: string; command: string };
type Fixture = typeof window & { __productLedger: Ledger[]; __releaseA: () => void; __pendingA: number; __releasedA: number; __storageWrites: string[] };
const targets = [
  { name: 'Memory', nav: '记忆', command: 'bookmarks_list' },
  { name: 'Opportunity', nav: '机会', command: 'opportunities_list' },
  { name: 'Notifications', nav: '设置', command: 'notifications_list' },
] as const;

async function login(page: Page, account: string) {
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
  await page.getByLabel('邮箱').fill(`${account}@example.com`);
  await page.getByLabel('密码').fill('fixture-password');
  await page.getByRole('button', { name: '登录并载入星图' }).click();
  await expect(page.getByTestId('universe')).toHaveAttribute('data-mode', 'live');
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
}
async function navigate(page: Page, nav: string) {
  await page.getByRole('button', { name: nav, exact: true }).click();
  await expect(page.locator('.page-scene')).toHaveAttribute('data-motion', 'idle');
}
async function storage(page: Page) {
  return page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage } }));
}

for (const target of targets) for (const outcome of ['resolve', 'reject'] as const) {
  test(`${target.name}: late A ${outcome} leaves B UI, storage and requests isolated`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(({ command, outcome }) => {
      const state = window as Fixture;
      state.__productLedger = []; state.__pendingA = 0; state.__releasedA = 0; state.__storageWrites = [];
      const set = Storage.prototype.setItem, remove = Storage.prototype.removeItem, clear = Storage.prototype.clear;
      Storage.prototype.setItem = function (key, value) { state.__storageWrites.push(`set:${key}`); return set.call(this, key, value); };
      Storage.prototype.removeItem = function (key) { state.__storageWrites.push(`remove:${key}`); return remove.call(this, key); };
      Storage.prototype.clear = function () { state.__storageWrites.push('clear'); return clear.call(this); };
      let account = '', bRequests = 0;
      const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
      const response = (cmd: string, title: string) => {
        const common = { id: id(81), title, createdAt: '2026-10-20T00:00:00Z' };
        const item = cmd === 'bookmarks_list'
          ? { ...common, documentId: id(51), note: null, canonicalUrl: 'https://example.com/fixture', analysisId: null, radarId: null, summary: 'Memory fixture', category: null, radarScore: null, recommendation: null, updatedAt: common.createdAt }
          : cmd === 'opportunities_list'
            ? { ...common, sourceId: id(21), platform: 'fixture', description: 'Opportunity fixture', budgetMin: null, budgetMax: null, currency: null, skills: [], deadline: null, publishedAt: null, estimatedEffortHours: null, deliveryType: null, profileVersion: 'v1', sourceUrl: 'https://example.com/fixture', status: 'active', updatedAt: common.createdAt, score: null }
            : { ...common, kind: 'intelligence', analysisId: id(61), opportunityId: null, content: 'Notification fixture', priority: 'normal', reason: 'Fixture', url: null, status: 'unread', readAt: null };
        return { items: [item], page: 1, pageSize: 10, total: 1 };
      };
      Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (cmd: string, args?: { input?: { email?: string } }) => {
        if (cmd === 'bridge_status') return { available: true };
        if (cmd === 'health_ready') return { ready: true };
        if (cmd === 'auth_login') { account = args?.input?.email?.toLowerCase().startsWith('b@') ? 'B' : 'A'; return { authenticated: true }; }
        if (cmd === 'users_me') return { id: id(account === 'A' ? 1 : 2), email: `${account}@example.com`, displayName: `Account ${account}`, isActive: true };
        if (cmd === 'auth_logout') { account = ''; return; }
        if (cmd === 'radars_list') return { items: [], page: 1, pageSize: 100, total: 0 };
        state.__productLedger.push({ account, command: cmd });
        if (!['bookmarks_list', 'opportunities_list', 'notifications_list'].includes(cmd)) throw Error(`Unexpected product write or command: ${cmd}`);
        if (account === 'A' && cmd === command) {
          state.__pendingA++;
          return new Promise((resolve, reject) => {
            state.__releaseA = () => {
              state.__pendingA--; state.__releasedA++;
              if (outcome === 'resolve') resolve(response(cmd, 'A-STALE-DATA'));
              else reject({ kind: 'api', message: 'A-STALE-ERROR', status: 503, requestId: 'A-stale-request' });
            };
          });
        }
        if (account === 'B' && cmd === command) return response(cmd, `B-FRESH-${++bRequests}`);
        return { items: [], page: 1, pageSize: 10, total: 0 };
      } } });
    }, { command: target.command, outcome });

    await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await login(page, 'A');
    await navigate(page, target.nav);
    await expect.poll(() => page.evaluate(() => (window as Fixture).__pendingA)).toBe(1);
    if (target.nav !== '设置') await navigate(page, '设置');
    await page.locator('.settings-list .setting-row').filter({ has: page.getByRole('button', { name: '刷新会话', exact: true }) }).getByRole('button', { name: '退出登录', exact: true }).click();
    await expect(page.getByRole('heading', { name: '欢迎回来。' })).toBeVisible(); await login(page, 'B');
    await navigate(page, target.nav);
    await expect(page.getByText('B-FRESH-1', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => (window as Fixture).__pendingA)).toBe(1);
    const beforeStorage = await storage(page);
    const beforeCalls = await page.evaluate(() => (window as Fixture).__productLedger);
    await page.evaluate(async () => {
      const state = window as Fixture;
      state.__storageWrites = []; state.__releaseA();
      // Drain promise continuations and let React commit before negative assertions.
      await new Promise<void>(resolve => setTimeout(resolve, 0));
      await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
    });
    expect(await page.evaluate(() => (window as Fixture).__releasedA)).toBe(1);
    expect(await page.evaluate(() => (window as Fixture).__pendingA)).toBe(0);
    await expect(page.getByText('B-FRESH-1', { exact: true })).toBeVisible();
    await expect(page.getByText(/A-STALE|账户已切换/)).toHaveCount(0);
    await expect(page.getByRole('alert')).toHaveCount(0);
    expect(await storage(page)).toEqual(beforeStorage);
    expect(await page.evaluate(() => (window as Fixture).__storageWrites)).toEqual([]);
    expect(await page.evaluate(() => (window as Fixture).__productLedger)).toEqual(beforeCalls);

    if (target.name === 'Opportunity') {
      await page.locator('.product-filters select').nth(1).selectOption('active');
      await page.getByRole('button', { name: '应用筛选', exact: true }).click();
    }
    else await page.locator(target.name === 'Notifications' ? '.notification-panel' : '.product-page').getByRole('button', { name: '刷新', exact: true }).click();
    await expect(page.getByText('B-FRESH-2', { exact: true })).toBeVisible();
    await expect(page.getByText(/A-STALE|账户已切换/)).toHaveCount(0);
    const ledger = await page.evaluate(() => (window as Fixture).__productLedger);
    expect(ledger.slice(beforeCalls.length)).toEqual([{ account: 'B', command: target.command }]);
    expect(ledger.every(call => ['bookmarks_list', 'opportunities_list', 'notifications_list'].includes(call.command))).toBe(true);
    expect(await storage(page)).toEqual(beforeStorage);
    expect(errors).toEqual([]);
    console.log(JSON.stringify({ target: target.name, outcome, ledger, releasedA: 1, storageWritesAfterRelease: await page.evaluate(() => (window as Fixture).__storageWrites) }));
  });
}
