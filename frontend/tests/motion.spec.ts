import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

async function enter(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: '跳过动画' }).click();
  await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-stage', 'workspace');
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
}
test('projection unfolds, then returns control without changing camera geometry', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await enter(page);
  await expect(page.getByTestId('universe')).toHaveAttribute('data-projection', 'opening');
  await expect(page.locator('.projection-field')).toHaveCSS('animation-name', 'holo-unfold');
  await page.screenshot({ path: info.outputPath('hologram-unfolding.png') });
  await expect(page.getByTestId('universe')).toHaveAttribute('data-projection', 'ready');
  await expect(page.locator('.projection-field')).toHaveCSS('transform', 'none');
  await page.locator('[data-radar="demo-market"]').click();
  await expect(page.getByRole('heading', { name: 'Market Observatory' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('[data-radar="demo-market"]')).toBeFocused();
  await page.screenshot({ path: info.outputPath('hologram-settled.png') });
  expect(errors).toEqual([]);
});

test('rapid page changes use the last destination and leave no inert screen', async ({ page }) => {
  await enter(page);
  // Native buttons remain operable while only the old page content exits.
  await page.getByRole('button', { name: '信号', exact: true }).click();
  await page.getByRole('button', { name: '记忆', exact: true }).click();
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await expect(page.locator('.page-scene')).toHaveAttribute('data-page', 'Settings');
  await expect(page.locator('.page-scene')).toHaveAttribute('data-motion', 'idle');
  await expect(page.getByRole('checkbox', { name: /减少动态效果/ })).toBeEnabled();
  await expect(page.getByRole('button', { name: '设置', exact: true })).toHaveAttribute('aria-current', 'page');
  await page.getByRole('checkbox', { name: /减少动态效果/ }).check();
  await page.getByRole('button', { name: '星图', exact: true }).click();
  await expect(page.getByTestId('universe')).toHaveAttribute('data-projection', 'ready');
  await expect(page.locator('.projection-field')).toHaveCSS('animation-name', 'none');
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await page.getByRole('button', { name: '返回演示登录' }).click();
  await expect(page.getByTestId('original-backdrop')).toHaveCount(1);
  await expect(page.locator('.stage-scene')).not.toHaveAttribute('inert', '');
});

test('changing system motion preference mid-transition settles immediately', async ({ page }) => {
  await enter(page);
  await page.getByRole('button', { name: '信号', exact: true }).click();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.locator('.page-scene')).toHaveAttribute('data-page', 'Signals');
  await expect(page.locator('.page-scene')).toHaveAttribute('data-motion', 'idle');
  await expect(page.getByText('这片星域，尚未接入。')).toBeVisible();
  await page.getByRole('button', { name: '星图', exact: true }).click();
  await expect(page.getByTestId('universe')).toHaveAttribute('data-projection', 'ready');
});

test('login projection releases its fill so exit can fade away', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: '跳过动画' }).click();
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
  await expect(page.locator('.demo-login')).toHaveCSS('animation-fill-mode', 'backwards');
  await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'out');
  // Freeze the actual CSS exit transition halfway to inspect the composited result.
  const opacity = await page.locator('.demo-login').evaluate(element => {
    const transition = element.getAnimations().find(animation => animation instanceof CSSTransition && animation.transitionProperty === 'opacity');
    if (!transition) return 1;
    transition.pause(); transition.currentTime = 90;
    return Number(getComputedStyle(element).opacity);
  });
  expect(opacity).toBeLessThan(.9);
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-stage', 'workspace');
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
});
