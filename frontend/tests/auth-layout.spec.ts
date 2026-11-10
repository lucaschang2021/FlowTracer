import { expect, test } from '@playwright/test';

for (const viewport of [{ width: 1600, height: 900 }, { width: 960, height: 640 }]) {
  for (const language of ['zh-CN', 'en']) {
    test(`sign-in frame stays fixed through delayed API failure, ${viewport.width}x${viewport.height} ${language}`, async ({ page }, info) => {
      await page.setViewportSize(viewport);
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.addInitScript(() => {
        const state = window as typeof window & { releaseStatus?: () => void; failReady?: () => void; failLogin?: () => void };
        Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => {
          if (command === 'bridge_status') return new Promise(resolve => { state.releaseStatus = () => resolve({ available: true, origin: 'http://127.0.0.1:8000' }); });
          if (command === 'health_ready') return new Promise((_resolve, reject) => { state.failReady = () => reject({ kind: 'network', message: 'Local API unavailable. 本机 API 暂时无法连接。 '.repeat(8), requestId: 'request-long-id-'.repeat(15) }); });
          if (command === 'auth_login') return new Promise((_resolve, reject) => { state.failLogin = () => reject({ kind: 'network', message: 'Connection still unavailable.', requestId: 'request-retry' }); });
          throw new Error(`Unexpected layout-test command: ${command}`);
        } } });
      });
      await page.goto('/');
      await page.getByLabel('语言').selectOption(language);
      await page.getByRole('button', { name: language === 'en' ? 'Skip intro' : '跳过动画' }).click();
      await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
      const panel = page.locator('.auth-panel');
      const frames = [await panel.boundingBox()];
      const demoBefore = await page.locator('.demo-enter').boundingBox();
      await expect.poll(() => page.evaluate(() => typeof (window as typeof window & { releaseStatus?: () => void }).releaseStatus)).toBe('function');
      await page.evaluate(() => (window as typeof window & { releaseStatus?: () => void }).releaseStatus?.());
      await expect(page.locator('.connection-state')).toContainText('http://127.0.0.1:8000');
      frames.push(await panel.boundingBox());
      await page.evaluate(() => (window as typeof window & { failReady?: () => void }).failReady?.());
      await expect(page.getByRole('alert')).toContainText('Local API unavailable.');
      frames.push(await panel.boundingBox());
      const demoAfter = await page.locator('.demo-enter').boundingBox();
      console.log(JSON.stringify({ viewport, language, frames }));
      await page.screenshot({ path: info.outputPath('api-error.png') });
      for (const frame of frames.slice(1)) expect(frame).toEqual(frames[0]);
      expect(demoAfter).toEqual(demoBefore);
      expect(frames[0]!.y).toBeGreaterThanOrEqual(0);
      expect(frames[0]!.y + frames[0]!.height).toBeLessThanOrEqual(viewport.height);
      await expect(page.getByRole('alert')).toContainText('request-long-id-');
      expect(await page.getByRole('alert').evaluate(el => el.scrollHeight > el.clientHeight)).toBe(true);
      await page.getByLabel(language === 'en' ? 'Email' : '邮箱', { exact: true }).fill('preview@example.invalid');
      await page.getByLabel(language === 'en' ? 'Password' : '密码', { exact: true }).fill('not-a-real-password');
      await page.locator('.login-enter').click();
      await expect(page.locator('.login-enter')).toBeDisabled();
      expect(await panel.boundingBox()).toEqual(frames[0]);
      await page.evaluate(() => (window as typeof window & { failLogin?: () => void }).failLogin?.());
      await expect(page.getByRole('alert')).toContainText('Connection still unavailable.');
      expect(await panel.boundingBox()).toEqual(frames[0]);
      await expect(page.getByLabel(language === 'en' ? 'Password' : '密码', { exact: true })).toHaveValue('');
      await page.getByRole('tab', { name: language === 'en' ? 'Register' : '注册' }).click();
      await expect(page.getByLabel(language === 'en' ? 'Display name' : '显示名称')).toBeVisible();
      expect(await panel.boundingBox()).toEqual(frames[0]);
      await page.locator('.demo-enter').scrollIntoViewIfNeeded();
      const demo = await page.locator('.demo-enter').boundingBox();
      expect(demo!.y).toBeGreaterThanOrEqual(frames[0]!.y);
      expect(demo!.y + demo!.height).toBeLessThanOrEqual(frames[0]!.y + frames[0]!.height);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  }
}

for (const kind of ['login', 'register'] as const) {
  test(`switching to guided practice fences a delayed ${kind} before account requests`, async ({ page }) => {
    await page.addInitScript(() => {
      const state = window as typeof window & { authCalls?: string[]; releaseAuth?: () => void };
      state.authCalls = [];
      Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => {
        state.authCalls!.push(command);
        if (command === 'bridge_status') return { available: true };
        if (command === 'health_ready') return { ready: true };
        if (command === 'auth_login' || command === 'auth_register') return new Promise(resolve => { state.releaseAuth = () => resolve({ authenticated: true }); });
        if (command === 'users_me' || command === 'radars_list') throw new Error(`stale ${command} must not run`);
        throw new Error(`Unexpected auth-fencing command: ${command}`);
      } } });
    });
    await page.goto('/');
    await page.getByRole('button', { name: '跳过动画' }).click();
    await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
    await expect(page.getByText('本机 API 已就绪')).toBeVisible();
    if (kind === 'register') {
      await page.getByRole('tab', { name: '注册' }).click();
      await page.getByLabel('显示名称').fill('Practice switch');
    }
    await page.getByLabel('邮箱', { exact: true }).fill('switch@example.com');
    await page.getByLabel('密码', { exact: true }).fill('not-a-real-password');
    expect(await page.locator('.auth-form').evaluate(form => (form as HTMLFormElement).checkValidity())).toBe(true);
    await page.locator('.login-enter').click();
    const expectedAuthCommand = kind === 'login' ? 'auth_login' : 'auth_register';
    await expect.poll(() => page.evaluate(() => (window as typeof window & { authCalls?: string[] }).authCalls!)).toContain(expectedAuthCommand);
    await expect.poll(() => page.evaluate(() => typeof (window as typeof window & { releaseAuth?: () => void }).releaseAuth)).toBe('function');
    await page.getByRole('button', { name: '开始交互教程' }).click();
    await expect(page.locator('.app-shell')).toHaveAttribute('data-mode', 'tutorial');
    await page.evaluate(() => (window as typeof window & { releaseAuth?: () => void }).releaseAuth?.());
    await page.waitForTimeout(100);
    const calls = await page.evaluate(() => (window as typeof window & { authCalls?: string[] }).authCalls!);
    expect(calls.filter(command => command === expectedAuthCommand)).toHaveLength(1);
    expect(calls.filter(command => command === 'users_me' || command === 'radars_list')).toEqual([]);
  });
}
