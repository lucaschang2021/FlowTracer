import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

const grid = (page: Page) => page.locator('.original-polar-grid svg');

async function motion(locator: Locator) {
  return locator.evaluate(element => {
    const animation = element.getAnimations().find(item => item instanceof CSSAnimation && item.animationName === 'original-turn');
    const timing = animation?.effect?.getComputedTiming();
    return {
      animationName: getComputedStyle(element).animationName,
      duration: getComputedStyle(element).animationDuration,
      easing: timing?.easing,
      currentTime: Number(animation?.currentTime ?? -1),
      playState: animation?.playState,
      transform: getComputedStyle(element).transform,
    };
  });
}

test('shared polar grid rotates continuously across intro, workspace and utility pages', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:1420/')) errors.push(`Unexpected external request: ${request.url()}`); });
  await page.goto('/');

  const backdrop = page.getByTestId('original-backdrop');
  await expect(backdrop).toHaveCount(1);
  await expect(backdrop).toHaveCSS('pointer-events', 'none');
  await grid(page).evaluate(element => { (element as SVGElement).dataset.motionIdentity = 'shared-grid'; });

  const introStart = await motion(grid(page));
  expect(introStart).toMatchObject({ animationName: 'original-turn', duration: '120s', easing: 'linear', playState: 'running' });
  await page.waitForTimeout(160);
  const introEnd = await motion(grid(page));
  expect(introEnd.currentTime).toBeGreaterThan(introStart.currentTime + 80);
  expect(introEnd.transform).not.toBe(introStart.transform);
  expect(await page.getByRole('main', { name: '启动画面' }).evaluate(element => element.getAnimations().some(item => item instanceof CSSAnimation && item.animationName === 'original-turn'))).toBe(false);

  await page.getByRole('button', { name: '跳过动画' }).click();
  await expect(page.getByRole('heading', { name: '欢迎回来。' })).toBeVisible();
  await expect(backdrop).toHaveCount(1);
  await expect(grid(page)).toHaveAttribute('data-motion-identity', 'shared-grid');
  const loginTime = (await motion(grid(page))).currentTime;
  expect(loginTime).toBeGreaterThan(introEnd.currentTime);

  await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-stage', 'workspace');
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
  await expect(backdrop).toHaveCount(1);
  await expect(grid(page)).toHaveAttribute('data-motion-identity', 'shared-grid');
  const workspaceTime = (await motion(grid(page))).currentTime;
  expect(workspaceTime).toBeGreaterThan(loginTime);
  expect(await page.locator('.app-shell').evaluate(element => element.getAnimations().some(item => item instanceof CSSAnimation && item.animationName === 'original-turn'))).toBe(false);

  await page.getByRole('button', { name: '设置', exact: true }).click();
  await expect(page.locator('.page-scene')).toHaveAttribute('data-page', 'Settings');
  await expect(page.locator('.page-scene')).toHaveAttribute('data-motion', 'idle');
  await expect(grid(page)).toHaveAttribute('data-motion-identity', 'shared-grid');
  expect((await motion(grid(page))).currentTime).toBeGreaterThan(workspaceTime);
  expect(await page.locator('.utility-page').evaluate(element => element.getAnimations().some(item => item instanceof CSSAnimation && item.animationName === 'original-turn'))).toBe(false);

  await page.getByRole('checkbox', { name: /减少动态效果/ }).check();
  await expect.poll(async () => (await motion(grid(page))).animationName).toBe('none');
  expect(errors).toEqual([]);
});

test('system reduced motion disables the shared polar grid rotation', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  const state = await motion(grid(page));
  expect(state.animationName).toBe('none');
  expect(state.playState).toBeUndefined();
  await expect(page.getByRole('button', { name: '跳过动画' })).toBeEnabled();
});
