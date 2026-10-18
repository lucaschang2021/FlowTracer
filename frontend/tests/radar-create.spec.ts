import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const created = { id: '00000000-0000-4000-8000-000000000011', name: 'New Radar', description: null, goal: 'Track change', radarType: 'technology', categories: [], keywords: [], status: 'active', notificationThreshold: 75 };

const waitForStageIdle = async (page: Page) => {
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
};

const signIn = async (page: Page, email: string) => {
  await waitForStageIdle(page);
  await page.getByLabel('邮箱').fill(email);
  await page.getByLabel('密码').fill('not-a-real-password');
  await expect(page.getByLabel('邮箱')).toHaveValue(email);
  await expect(page.getByLabel('密码')).toHaveValue('not-a-real-password');
  await page.getByRole('button', { name: '登录并载入星图' }).click();
  await expect(page.getByTestId('universe')).toHaveAttribute('data-mode', 'live');
  await waitForStageIdle(page);
};

const installEmptyLiveBridge = async (page: Page) => {
  await page.addInitScript(() => {
    const user = { id: '00000000-0000-4000-8000-000000000001', email: 'person@example.com', displayName: 'Explorer', isActive: true };
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => {
      if (command === 'bridge_status') return { available: true, origin: 'http://127.0.0.1:8000/api/v1' };
      if (command === 'health_ready') return { ready: true };
      if (command === 'auth_login') return { authenticated: true, user };
      if (command === 'users_me') return user;
      if (command === 'radars_list') return { items: [], page: 1, pageSize: 100, total: 0 };
      if (command === 'auth_logout') return;
      throw Error(`Unexpected command: ${command}`);
    } } });
  });
};

test('create dialog traps keyboard focus and restores its trigger', async ({ page }) => {
  await installEmptyLiveBridge(page);
  await page.goto('/');
  await page.getByRole('button', { name: '跳过动画' }).click();
  await signIn(page, 'person@example.com');
  const trigger = page.getByRole('button', { name: '新建 Radar' });
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: '新建 Radar' });
  const name = dialog.getByLabel('名称');
  const close = dialog.getByRole('button', { name: '关闭新建 Radar' });
  const submit = dialog.getByRole('button', { name: '创建 Radar' });
  await expect(name).toBeFocused();
  await expect(page.locator('header.app-header')).toHaveAttribute('inert', '');
  await expect(page.locator('main.app-main')).toHaveAttribute('inert', '');
  await expect(page.locator('footer.status-bar')).toHaveAttribute('inert', '');
  await close.focus();
  await page.keyboard.press('Shift+Tab');
  await expect(submit).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(close).toBeFocused();
  const settings = page.locator('.main-nav button').filter({ hasText: /^设置$/ });
  await settings.focus();
  await expect(close).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await trigger.click();
  await page.getByRole('dialog', { name: '新建 Radar' }).getByRole('button', { name: '取消' }).click();
  await expect(trigger).toBeFocused();
  await expect(page.locator('.page-scene')).toHaveAttribute('data-page', 'Canvas');
});

test('live Radar create preserves input on failure and inserts only confirmed UUID once', async ({ page }) => {
  await page.addInitScript(record => {
    let attempts = 0;
    (window as typeof window & { __radarCreateCalls?: number; __releaseRadarCreate?: () => void }).__radarCreateCalls = 0;
    const user = { id: '00000000-0000-4000-8000-000000000001', email: 'person@example.com', displayName: 'Explorer', isActive: true };
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string, args?: { input?: { name?: string; goal?: string; radarType?: string } }) => {
      if (command === 'bridge_status') return { available: true, origin: 'http://127.0.0.1:8000/api/v1' };
      if (command === 'health_ready') return { ready: true };
      if (command === 'auth_login') return { authenticated: true, user };
      if (command === 'users_me') return user;
      if (command === 'radars_list') return { items: [], page: 1, pageSize: 100, total: 0 };
      if (command === 'radars_create') {
        (window as typeof window & { __radarCreateCalls?: number }).__radarCreateCalls = ((window as typeof window & { __radarCreateCalls?: number }).__radarCreateCalls ?? 0) + 1;
        attempts += 1;
        if (attempts === 1) throw { kind: 'api', message: 'Name conflict', status: 409, code: 'radar_name_conflict' };
        if (args?.input?.name !== 'New Radar' || args.input.goal !== 'Track change' || args.input.radarType !== 'technology') throw Error('Invalid create input');
        return await new Promise<typeof record>(resolve => {
          (window as typeof window & { __releaseRadarCreate?: () => void }).__releaseRadarCreate = () => resolve(record);
        });
      }
      if (command === 'auth_logout') return;
      throw Error(`Unexpected command: ${command}`);
    } } });
  }, created);
  await page.goto('/');
  await page.getByRole('button', { name: '跳过动画' }).click();
  await signIn(page, 'person@example.com');
  await page.getByRole('button', { name: '新建 Radar' }).click();
  await page.getByRole('dialog', { name: '新建 Radar' }).getByLabel('名称').fill(' New Radar ');
  await page.getByRole('dialog', { name: '新建 Radar' }).getByLabel('目标').fill(' Track change ');
  await page.getByRole('dialog', { name: '新建 Radar' }).getByLabel('Radar 类型').selectOption('technology');
  await page.getByRole('button', { name: '创建 Radar' }).click();
  await expect(page.getByRole('alert')).toContainText('Name conflict');
  await expect(page.locator('[data-radar]')).toHaveCount(0);
  await expect(page.getByRole('dialog', { name: '新建 Radar' }).getByLabel('名称')).toHaveValue(' New Radar ');
  await page.getByRole('button', { name: '创建 Radar' }).click();
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __radarCreateCalls?: number }).__radarCreateCalls)).toBe(2);
  await expect(page.getByRole('button', { name: '正在创建…' })).toBeDisabled();
  const pendingDialog = page.getByRole('dialog', { name: '新建 Radar' });
  await page.keyboard.press('Escape');
  await expect(pendingDialog).toBeVisible();
  const description = pendingDialog.getByLabel('补充说明（可选）');
  await description.focus();
  await page.keyboard.press('Tab');
  await expect(pendingDialog.getByLabel('名称')).toBeFocused();
  await page.locator('.main-nav button').filter({ hasText: /^设置$/ }).focus();
  await expect(pendingDialog.getByLabel('名称')).toBeFocused();
  await page.getByRole('dialog', { name: '新建 Radar' }).locator('form').evaluate(form => { (form as HTMLFormElement).requestSubmit(); });
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __radarCreateCalls?: number }).__radarCreateCalls)).toBe(2);
  await page.evaluate(() => (window as typeof window & { __releaseRadarCreate?: () => void }).__releaseRadarCreate?.());
  await expect(page.locator('[data-radar]')).toHaveCount(1);
  await expect(page.locator('[data-radar]')).toHaveAttribute('data-radar', created.id);
});

test('account switch fences a late create response from the new session', async ({ page }) => {
  await page.addInitScript(record => {
    let loginCount = 0;
    let resolveCreate: ((value: typeof record) => void) | undefined;
    (window as typeof window & { __releaseRadarCreate?: () => void; __radarCreateCalls?: number }).__radarCreateCalls = 0;
    const users = [
      { id: '00000000-0000-4000-8000-000000000001', email: 'first@example.com', displayName: 'First', isActive: true },
      { id: '00000000-0000-4000-8000-000000000002', email: 'second@example.com', displayName: 'Second', isActive: true },
    ];
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => {
      if (command === 'bridge_status') return { available: true, origin: 'http://127.0.0.1:8000/api/v1' };
      if (command === 'health_ready') return { ready: true };
      if (command === 'auth_login') { loginCount += 1; return { authenticated: true, user: users[Math.min(loginCount - 1, 1)] }; }
      if (command === 'users_me') return users[Math.min(loginCount - 1, 1)];
      if (command === 'radars_list') return { items: [], page: 1, pageSize: 100, total: 0 };
      if (command === 'radars_create') {
        (window as typeof window & { __radarCreateCalls?: number }).__radarCreateCalls = 1;
        return await new Promise<typeof record>(resolve => {
          resolveCreate = resolve;
          (window as typeof window & { __releaseRadarCreate?: () => void }).__releaseRadarCreate = () => resolveCreate?.(record);
        });
      }
      if (command === 'auth_logout') return;
      throw Error(`Unexpected command: ${command}`);
    } } });
  }, created);
  await page.goto('/');
  await page.getByRole('button', { name: '跳过动画' }).click();
  await signIn(page, 'first@example.com');
  await page.getByRole('button', { name: '新建 Radar' }).click();
  await page.getByRole('dialog', { name: '新建 Radar' }).getByLabel('名称').fill('Late Radar');
  await page.getByRole('dialog', { name: '新建 Radar' }).getByLabel('目标').fill('Must remain in old session');
  await page.getByRole('button', { name: '创建 Radar' }).click();
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __radarCreateCalls?: number }).__radarCreateCalls)).toBe(1);
  // Test-only lifecycle fault injection: dispatch React's existing navigation and
  // sign-out handlers without treating inert background UI as a user-operable path.
  await page.locator('.main-nav button').filter({ hasText: /^设置$/ }).dispatchEvent('click');
  await expect(page.locator('.page-scene')).toHaveAttribute('data-page', 'Settings');
  await expect(page.locator('.page-scene')).toHaveAttribute('data-motion', 'idle');
  const signOut = page.locator('.settings-list button').filter({ hasText: /^退出登录$/ }).first();
  await signOut.dispatchEvent('click');
  await expect(page.getByRole('heading', { name: '欢迎回来。' })).toBeVisible();
  await signIn(page, 'second@example.com');
  await page.evaluate(() => (window as typeof window & { __releaseRadarCreate?: () => void }).__releaseRadarCreate?.());
  await expect(page.locator('[data-radar]')).toHaveCount(0);
  await page.getByRole('button', { name: '设置' }).click();
  await expect(page.locator('.page-scene')).toHaveAttribute('data-page', 'Settings');
  await expect(page.locator('.page-scene')).toHaveAttribute('data-motion', 'idle');
  await expect(page.getByText('Second', { exact: true })).toBeVisible();
});

test('invalid created UUID stays in the form as an error and does not crash the map', async ({ page }) => {
  await page.addInitScript(record => {
    const user = { id: '00000000-0000-4000-8000-000000000001', email: 'person@example.com', displayName: 'Explorer', isActive: true };
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => {
      if (command === 'bridge_status') return { available: true, origin: 'http://127.0.0.1:8000/api/v1' };
      if (command === 'health_ready') return { ready: true };
      if (command === 'auth_login') return { authenticated: true, user };
      if (command === 'users_me') return user;
      if (command === 'radars_list') return { items: [], page: 1, pageSize: 100, total: 0 };
      if (command === 'radars_create') return { ...record, id: 'invalid-response-id' };
      throw Error(`Unexpected command: ${command}`);
    } } });
  }, created);
  await page.goto('/');
  await page.getByRole('button', { name: '跳过动画' }).click();
  await signIn(page, 'person@example.com');
  await page.getByRole('button', { name: '新建 Radar' }).click();
  await page.getByRole('dialog', { name: '新建 Radar' }).getByLabel('名称').fill('Invalid Radar');
  await page.getByRole('dialog', { name: '新建 Radar' }).getByLabel('目标').fill('Validate response');
  await page.getByRole('button', { name: '创建 Radar' }).click();
  await expect(page.getByRole('alert')).toContainText('identity');
  await expect(page.locator('[data-radar]')).toHaveCount(0);
  await expect(page.getByRole('dialog', { name: '新建 Radar' })).toBeVisible();
  await page.getByRole('dialog', { name: '新建 Radar' }).getByLabel('名称').fill('Still usable');
  await expect(page.getByRole('dialog', { name: '新建 Radar' }).getByLabel('名称')).toHaveValue('Still usable');
});

test('demo plus remains guide-only and never calls create', async ({ page }) => {
  await page.addInitScript(() => {
    (window as typeof window & { __radarCreateCalls?: number }).__radarCreateCalls = 0;
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => {
      if (command === 'bridge_status') return { available: true, origin: 'http://127.0.0.1:8000/api/v1' };
      if (command === 'health_ready') return { ready: true };
      if (command === 'radars_create') { (window as typeof window & { __radarCreateCalls?: number }).__radarCreateCalls = 1; }
      throw Error(`Unexpected command: ${command}`);
    } } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: '跳过动画' }).click();
  await waitForStageIdle(page);
  await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(page.getByTestId('universe')).toHaveAttribute('data-mode', 'demo');
  await waitForStageIdle(page);
  await page.getByRole('button', { name: '查看演示说明' }).click();
  await expect(page.getByRole('dialog', { name: '一张安静的情报星图。' })).toBeVisible();
  await expect(page.getByRole('dialog', { name: '新建 Radar' })).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __radarCreateCalls?: number }).__radarCreateCalls)).toBe(0);
});
