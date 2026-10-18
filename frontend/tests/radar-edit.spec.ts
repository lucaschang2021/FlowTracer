import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const id = '00000000-0000-4000-8000-000000000011';
const otherId = '00000000-0000-4000-8000-000000000012';
const record = { id, name: 'Original Radar', description: 'Canvas summary', goal: 'Full detail goal', radarType: 'technology', categories: ['keep'], keywords: ['preserve'], status: 'paused', notificationThreshold: 75 };
const user = { id: '00000000-0000-4000-8000-000000000001', email: 'person@example.com', displayName: 'Explorer', isActive: true };

async function signIn(page: Page) {
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
  await page.getByLabel('邮箱').fill('person@example.com'); await page.getByLabel('密码').fill('not-a-real-password');
  await page.getByRole('button', { name: '登录并载入星图' }).click();
  await expect(page.getByTestId('universe')).toHaveAttribute('data-mode', 'live');
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
}

async function openEditor(page: Page) {
  await page.locator(`[data-radar="${id}"]`).click();
  const trigger = page.getByRole('button', { name: '编辑 Radar' }); await trigger.click();
  const dialog = page.getByRole('dialog', { name: '编辑 Radar' });
  await expect(dialog.getByLabel('名称')).toBeFocused(); return { dialog, trigger };
}

test('live edit loads full detail and applies only a confirmed five-field update', async ({ page }) => {
  await page.addInitScript(({ record, user }) => {
    const state = window as typeof window & { __updateCalls?: number; __detailCalls?: number; __updateInput?: unknown; __releaseUpdate?: () => void };
    state.__updateCalls = 0; state.__detailCalls = 0;
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string, args?: { radarId?: string; input?: Record<string, unknown> }) => {
      if (command === 'bridge_status') return { available: true, origin: 'http://127.0.0.1:8000/api/v1' }; if (command === 'health_ready') return { ready: true };
      if (command === 'auth_login') return { authenticated: true, user }; if (command === 'users_me') return user;
      if (command === 'radars_list') return { items: [record], page: 1, pageSize: 100, total: 1 };
      if (command === 'radars_get') { state.__detailCalls = (state.__detailCalls ?? 0) + 1; if (args?.radarId !== record.id) throw Error('wrong id'); return record; }
      if (command === 'radars_update') {
        state.__updateCalls = (state.__updateCalls ?? 0) + 1; state.__updateInput = args?.input;
        return await new Promise(resolve => { state.__releaseUpdate = () => resolve({ ...record, ...args?.input, name: 'Edited Radar', radarType: 'market' }); });
      }
      if (command === 'auth_logout') return; throw Error(`Unexpected command: ${command}`);
    } } });
  }, { record, user });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await signIn(page);
  const node = page.locator(`[data-radar="${id}"]`); const before = await node.evaluate(el => ({ left: (el as HTMLElement).style.left, top: (el as HTMLElement).style.top }));
  const { dialog, trigger } = await openEditor(page);
  await expect(dialog.getByLabel('目标')).toHaveValue('Full detail goal'); await expect(dialog.getByLabel('通知阈值')).toHaveValue('75');
  await expect(page.locator('header.app-header')).toHaveAttribute('inert', ''); await expect(page.locator('footer.status-bar')).toHaveAttribute('inert', '');
  await dialog.getByLabel('名称').fill(' Edited Radar '); await page.emulateMedia({ reducedMotion: 'reduce' }); await expect(dialog.getByLabel('名称')).toHaveValue(' Edited Radar '); await expect.poll(() => page.evaluate(() => (window as typeof window & { __detailCalls?: number }).__detailCalls)).toBe(1); await dialog.getByLabel('目标').fill(' Updated goal '); await dialog.getByLabel('Radar 类型').selectOption('market');
  await dialog.getByLabel('补充说明（可选）').fill('   '); await dialog.getByLabel('通知阈值').fill('64'); await dialog.getByRole('button', { name: '保存修改' }).click();
  await expect(dialog.getByRole('button', { name: '正在保存…' })).toBeDisabled(); await page.keyboard.press('Escape'); await expect(dialog).toBeVisible();
  await dialog.locator('form').evaluate(form => (form as HTMLFormElement).requestSubmit());
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __updateCalls?: number }).__updateCalls)).toBe(1);
  const input = await page.evaluate(() => (window as typeof window & { __updateInput?: Record<string, unknown> }).__updateInput);
  expect(input).toEqual({ name: 'Edited Radar', goal: 'Updated goal', radarType: 'market', description: null, notificationThreshold: 64 });
  expect(input).not.toHaveProperty('categories'); expect(input).not.toHaveProperty('keywords'); expect(input).not.toHaveProperty('status');
  await page.evaluate(() => (window as typeof window & { __releaseUpdate?: () => void }).__releaseUpdate?.());
  await expect(dialog).toHaveCount(0); await expect(trigger).toBeFocused(); await expect(node).toContainText('Edited Radar');
  expect(await node.evaluate(el => ({ left: (el as HTMLElement).style.left, top: (el as HTMLElement).style.top }))).toEqual(before);
  await expect(node).toHaveClass(/world-gold/);
});

test('failed or mismatched updates retain the form and do not mutate the planet', async ({ page }) => {
  await page.addInitScript(({ record, user, otherId }) => {
    let attempt = 0; Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => {
      if (command === 'bridge_status') return { available: true }; if (command === 'health_ready') return { ready: true }; if (command === 'auth_login') return { authenticated: true, user };
      if (command === 'users_me') return user; if (command === 'radars_list') return { items: [record], page: 1, pageSize: 100, total: 1 }; if (command === 'radars_get') return record;
      if (command === 'radars_update') { attempt += 1; if (attempt === 1) throw { kind: 'api', message: 'Conflict', status: 409 }; if (attempt === 2) return { ...record, id: otherId, name: 'Wrong Radar' }; return { ...record, radarType: 'invalid-enum' }; }
      throw Error(`Unexpected command: ${command}`);
    } } });
  }, { record, user, otherId });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await signIn(page); const { dialog } = await openEditor(page);
  await dialog.getByLabel('名称').fill('Keep my input'); await dialog.getByRole('button', { name: '保存修改' }).click(); await expect(dialog.getByRole('alert')).toContainText('Conflict');
  await expect(dialog.getByLabel('名称')).toHaveValue('Keep my input'); await expect(page.locator(`[data-radar="${id}"]`)).toContainText('Original Radar');
  await dialog.getByRole('button', { name: '保存修改' }).click(); await expect(dialog.getByRole('alert')).toContainText('does not match'); await expect(dialog).toBeVisible();
  await expect(page.locator(`[data-radar="${id}"]`)).toContainText('Original Radar'); await expect(page.locator(`[data-radar="${otherId}"]`)).toHaveCount(0);
  await dialog.getByRole('button', { name: '保存修改' }).click(); await expect(dialog.getByRole('alert')).toContainText('enum'); await expect(dialog).toBeVisible(); await expect(page.getByTestId('universe')).toBeVisible(); await expect(page.locator(`[data-radar="${id}"]`)).toContainText('Original Radar');
});

test('account switch fences a late update response from the new session', async ({ page }) => {
  await page.addInitScript(({ record }) => {
    let loginCount = 0; let release: (() => void) | undefined;
    const users = [
      { id: '00000000-0000-4000-8000-000000000001', email: 'first@example.com', displayName: 'First', isActive: true },
      { id: '00000000-0000-4000-8000-000000000002', email: 'second@example.com', displayName: 'Second', isActive: true },
    ];
    Object.assign(window as typeof window & { __releaseUpdate?: () => void }, { __releaseUpdate: () => release?.() });
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => {
      if (command === 'bridge_status') return { available: true }; if (command === 'health_ready') return { ready: true };
      if (command === 'auth_login') { loginCount += 1; return { authenticated: true, user: users[Math.min(loginCount - 1, 1)] }; }
      if (command === 'users_me') return users[Math.min(loginCount - 1, 1)];
      if (command === 'radars_list') return { items: loginCount === 1 ? [record] : [], page: 1, pageSize: 100, total: loginCount === 1 ? 1 : 0 };
      if (command === 'radars_get') return record;
      if (command === 'radars_update') return await new Promise(resolve => { release = () => resolve({ ...record, name: 'Late write' }); });
      if (command === 'auth_logout') return; throw Error(`Unexpected command: ${command}`);
    } } });
  }, { record });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await signIn(page); const { dialog } = await openEditor(page);
  await dialog.getByLabel('名称').fill('Late write'); await dialog.getByRole('button', { name: '保存修改' }).click();
  await page.locator('.main-nav button').filter({ hasText: /^设置$/ }).dispatchEvent('click'); await expect(page.locator('.page-scene')).toHaveAttribute('data-page', 'Settings');
  await page.locator('.settings-list button').filter({ hasText: /^退出登录$/ }).first().dispatchEvent('click'); await expect(page.getByRole('heading', { name: '欢迎回来。' })).toBeVisible();
  await signIn(page); await page.evaluate(() => (window as typeof window & { __releaseUpdate?: () => void }).__releaseUpdate?.());
  await expect(page.locator('[data-radar]')).toHaveCount(0);
});

test('demo Radars expose no edit action or update request', async ({ page }) => {
  await page.addInitScript(() => { (window as typeof window & { __updates?: number }).__updates = 0; Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => { if (command === 'bridge_status') return { available: true }; if (command === 'health_ready') return { ready: true }; if (command === 'radars_update') (window as typeof window & { __updates?: number }).__updates = 1; throw Error(`Unexpected command: ${command}`); } } }); });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle'); await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(page.getByTestId('universe')).toHaveAttribute('data-mode', 'demo'); await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle'); await page.locator('[data-radar="demo-market"]').click();
  await expect(page.getByRole('button', { name: '编辑 Radar' })).toHaveCount(0); await expect.poll(() => page.evaluate(() => (window as typeof window & { __updates?: number }).__updates)).toBe(0);
});
