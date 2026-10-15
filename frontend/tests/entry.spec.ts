import { expect, test } from '@playwright/test';

test('approved startup canvas stays mounted across entry, star map and utility pages', async ({ page }, info) => {
  await page.goto('/');
  const backdrop = page.getByTestId('original-backdrop');
  await expect(backdrop).toHaveCount(1);
  await expect(page.locator('.celestial-background')).toHaveCount(0);
  for (const selector of ['.original-backdrop', '.original-orbit-art']) {
    const loaded = await page.locator(selector).evaluate(async element => {
      const url = getComputedStyle(element).backgroundImage.match(/url\("?([^"\)]+)"?\)/)?.[1];
      if (!url) return false;
      const image = new Image(); image.src = url;
      await image.decode(); return image.naturalWidth > 1000;
    });
    expect(loaded).toBe(true);
  }
  expect(await page.locator('.original-orbit-system').evaluate(el => getComputedStyle(el).animationDuration)).toBe('280s');
  expect(await page.locator('.original-polar-grid svg').evaluate(el => getComputedStyle(el).animationDuration)).toBe('230s');
  const first = await page.locator('.original-flowing-stars').evaluate(el => (el as HTMLCanvasElement).toDataURL());
  await expect.poll(() => page.locator('.original-flowing-stars').evaluate(el => (el as HTMLCanvasElement).toDataURL())).not.toBe(first);
  await expect(page.locator('.intro-wordmark')).toHaveAttribute('data-complete', 'true', { timeout: 10000 });
  await page.screenshot({ path: info.outputPath('restored-original-intro.png') });
  await page.getByRole('button', { name: '按任意键开始' }).click();
  await expect(page.getByRole('heading', { name: '欢迎回来。' })).toBeVisible();
  await expect(backdrop).toHaveCount(1);
  await page.screenshot({ path: info.outputPath('restored-original-login.png') });
  await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
  await expect(backdrop).toHaveCount(1);
  await expect(page.locator('.celestial-background')).toHaveCount(0);
  await expect(page.locator('.stage-scene .app-shell')).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
  await expect(page.locator('[data-radar]')).toHaveCount(6);
  await page.screenshot({ path: info.outputPath('shared-canvas-workspace.png') });
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await expect(page.locator('.page-scene')).toHaveAttribute('data-motion', 'idle');
  await expect(backdrop).toHaveCount(1);
  await expect(page.locator('.original-flowing-stars')).toHaveCount(1);
  await page.screenshot({ path: info.outputPath('shared-canvas-settings.png') });
});

test('intro, demo sign-in, bilingual settings and persisted preferences', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:1420/')) errors.push(request.url()); });
  await page.goto('/');
  await expect(page.getByRole('main', { name: '启动画面' })).toBeFocused();
  await page.getByLabel('语言').selectOption('en');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('button', { name: 'PRESS ANY KEY TO START' })).toBeVisible();
  // Let the complete ink sequence finish, and verify that pixels genuinely appeared.
  await expect.poll(async () => page.locator('.intro-emblem').evaluate(canvas => {
    const element = canvas as HTMLCanvasElement;
    return Array.from(element.getContext('2d')!.getImageData(0, 0, 512, 512).data).filter((n, i) => i % 4 === 3 && n > 128).length;
  }), { timeout: 10000 }).toBeGreaterThan(10000);
  await expect(page.locator('.intro-wordmark')).toHaveAttribute('data-complete', 'true');
  await page.screenshot({ path: info.outputPath('intro-en.png') });
  await page.getByRole('main').focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
  await expect(page.locator('input')).toHaveCount(2);
  await page.screenshot({ path: info.outputPath('login-en.png') });
  await page.getByRole('button', { name: 'Enter demo universe' }).click();
  await expect(page.locator('[data-radar]')).toHaveCount(6);
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('checkbox', { name: /Reduce motion/ }).check();
  await page.getByLabel('Language').selectOption('zh-CN');
  await expect(page.getByRole('heading', { name: '让宇宙，适合你。' })).toBeVisible();
  await page.screenshot({ path: info.outputPath('settings-zh.png') });
  await page.getByRole('button', { name: '重播启动动画' }).click();
  expect(await page.locator('.original-polar-grid svg').evaluate(el => getComputedStyle(el).animationName)).toBe('none');
  await page.reload();
  await expect(page.getByLabel('语言')).toHaveValue('zh-CN');
  await expect(page.locator('.quiet-mode')).toHaveCount(1);
  await page.getByRole('button', { name: '跳过动画' }).click();
  await page.getByRole('button', { name: '进入演示星图' }).click();
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await page.getByRole('button', { name: '返回演示登录' }).click();
  await expect(page.getByRole('heading', { name: '欢迎回来。' })).toBeVisible();
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual(['flowtracer.demo.preferences.v1']);
  expect(errors).toEqual([]);
});

test('system reduced motion and unavailable storage keep entry usable', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } }); });
  await page.goto('/');
  expect(await page.locator('.original-polar-grid svg').evaluate(el => getComputedStyle(el).animationName)).toBe('none');
  await page.keyboard.press('a');
  await expect(page.getByRole('heading', { name: '欢迎回来。' })).toBeVisible();
  await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(page.locator('[data-radar]')).toHaveCount(6);
});
