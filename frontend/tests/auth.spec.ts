import { expect, test } from '@playwright/test';

test('browser preview defaults to real mode and requires explicit demo entry', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '跳过动画' }).click();
  await expect(page.getByRole('heading', { name: '欢迎回来。' })).toBeVisible();
  await expect(page.getByLabel('邮箱')).toBeVisible();
  await expect(page.getByLabel('密码')).toBeVisible();
  await expect(page.getByRole('button', { name: '登录并载入星图' })).toBeDisabled();
  await expect(page.getByText('普通网页预览无法使用桌面桥')).toBeVisible();
  await expect(page.getByText('连接失败不会自动切换。')).toBeVisible();
  await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(page.getByTestId('universe')).toHaveAttribute('data-mode', 'demo');
  await expect(page.locator('[data-radar]')).toHaveCount(6);
  await expect(page.getByText('离线演示', { exact: true })).toBeVisible();
});

test('register form keeps account fields local to the explicit real flow', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '跳过动画' }).click();
  await page.getByRole('tab', { name: '注册' }).click();
  await expect(page.getByLabel('显示名称')).toBeVisible();
  await page.getByLabel('显示名称').fill('Explorer');
  await page.getByLabel('邮箱').fill('person@example.com');
  await page.getByLabel('密码').fill('not-a-real-password');
  await expect(page.getByLabel('密码')).toHaveValue('not-a-real-password');
  await expect(page.getByRole('button', { name: '创建账户并载入' })).toBeDisabled();
  await expect(page.getByTestId('universe')).toHaveCount(0);
});

for (const kind of ['login', 'register'] as const) {
  test(`${kind} success dissolves the sign-in layer while the startup canvas stays mounted`, async ({ page }, info) => {
    await page.addInitScript(() => {
      const user = { id: '00000000-0000-4000-8000-000000000001', email: 'person@example.com', displayName: 'Explorer', isActive: true };
      Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => {
        if (command === 'bridge_status') return { available: true, origin: 'http://127.0.0.1:18083' };
        if (command === 'health_ready') return { ready: true };
        if (command === 'auth_login' || command === 'auth_register') return { authenticated: true, user };
        if (command === 'users_me') return user;
        if (command === 'radars_list') return { items: [], page: 1, pageSize: 20, total: 0 };
        throw new Error(`Unexpected mocked command: ${command}`);
      } } });
    });
    await page.goto('/');
    const backdrop = page.getByTestId('original-backdrop');
    await backdrop.evaluate(element => { element.dataset.persistentCanvas = 'yes'; });
    await page.getByRole('button', { name: '跳过动画' }).click();
    await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
    if (kind === 'register') {
      await page.getByRole('tab', { name: '注册' }).click();
      await page.getByLabel('显示名称').fill('Explorer');
    }
    await page.getByLabel('邮箱').fill('person@example.com');
    await page.getByLabel('密码').fill('not-a-real-password');
    await expect(page.getByLabel('邮箱')).toHaveValue('person@example.com');
    await expect(page.getByLabel('密码')).toHaveValue('not-a-real-password');
    await page.getByRole('button', { name: kind === 'register' ? '创建账户并载入' : '登录并载入星图' }).click();
    await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'ink-out');
    await expect(page.getByRole('main', { name: '账户登录' })).toHaveCSS('animation-name', 'entry-ink-dissolve');
    if (kind === 'login') {
      await expect.poll(() => page.locator('.entry-screen').evaluate(element => Number(getComputedStyle(element).opacity)), { intervals: [50] }).toBeLessThan(.7);
      await page.screenshot({ path: info.outputPath('login-ink-dissolve.png') });
    }
    await expect(page.getByTestId('universe')).toHaveAttribute('data-mode', 'live');
    await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
    await expect(backdrop).toHaveAttribute('data-persistent-canvas', 'yes');
    await expect(page.locator('[data-radar]')).toHaveCount(0);
    if (kind === 'login') await page.screenshot({ path: info.outputPath('live-empty-shared-canvas.png') });
  });
}
