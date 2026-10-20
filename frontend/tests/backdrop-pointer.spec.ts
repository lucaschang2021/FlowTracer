import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const backdrop = (page: Page) => page.getByTestId('original-backdrop');
const offset = (page: Page) => backdrop(page).evaluate(element => {
  const [x, y = '0'] = getComputedStyle(element).translate.split(' ');
  return [Number.parseFloat(x), Number.parseFloat(y)];
});

async function demo(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: '跳过动画' }).click();
  await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
  await expect(page.getByTestId('universe')).toHaveAttribute('data-projection', 'ready');
}

test('background subtly follows the mouse without moving foreground or exposing edges', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await demo(page);
  const foreground = page.locator('.app-shell');
  const before = await foreground.boundingBox();
  await page.mouse.move(1590, 890);
  await expect.poll(async () => (await offset(page))[0]).toBeGreaterThan(10);
  await expect.poll(async () => (await offset(page))[1]).toBeGreaterThan(7);
  let bounds = await backdrop(page).boundingBox();
  expect(bounds!.x).toBeLessThanOrEqual(0); expect(bounds!.y).toBeLessThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeGreaterThanOrEqual(1600);
  expect(bounds!.y + bounds!.height).toBeGreaterThanOrEqual(900);
  await page.mouse.move(10, 10);
  await expect.poll(async () => (await offset(page))[0]).toBeLessThan(-10);
  await expect.poll(async () => (await offset(page))[1]).toBeLessThan(-7);
  bounds = await backdrop(page).boundingBox();
  expect(bounds!.x + bounds!.width).toBeGreaterThanOrEqual(1600);
  expect(bounds!.y + bounds!.height).toBeGreaterThanOrEqual(900);
  expect(await foreground.boundingBox()).toEqual(before);
  await expect(backdrop(page)).toHaveCSS('pointer-events', 'none');
  await expect(page.locator('.original-polar-grid svg')).toHaveCSS('animation-duration', '120s');
  await page.mouse.move(800, 450);
  await expect.poll(async () => Math.abs((await offset(page))[0])).toBeLessThan(.05);
  expect(errors).toEqual([]);
});

test('pointer follow resets on leave and blur and does not compete with dragging', async ({ page }) => {
  await demo(page);
  await page.mouse.move(1400, 200);
  await expect.poll(async () => (await offset(page))[0]).toBeGreaterThan(7);
  await page.mouse.down();
  await page.mouse.move(1450, 220);
  await expect.poll(async () => Math.abs((await offset(page))[0])).toBeLessThan(.05);
  await page.mouse.up();
  await page.mouse.move(1400, 200);
  await expect.poll(async () => (await offset(page))[0]).toBeGreaterThan(7);
  await page.evaluate(() => window.dispatchEvent(new Event('blur')));
  await expect.poll(async () => Math.abs((await offset(page))[0])).toBeLessThan(.05);
  await page.mouse.move(1350, 220);
  await expect.poll(async () => (await offset(page))[0]).toBeGreaterThan(6);
  await page.evaluate(() => window.dispatchEvent(new PointerEvent('pointerout', { relatedTarget: null })));
  await expect.poll(async () => Math.abs((await offset(page))[0])).toBeLessThan(.05);
});

test('quiet preference disables pointer follow and re-enabling motion restores it', async ({ page }) => {
  await demo(page);
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await expect(page.locator('.page-scene')).toHaveAttribute('data-motion', 'idle');
  const quiet = page.getByRole('checkbox', { name: /减少动态效果/ });
  await quiet.check();
  await page.mouse.move(1500, 800);
  await expect.poll(async () => await offset(page)).toEqual([0, 0]);
  await quiet.uncheck();
  await page.mouse.move(1450, 780);
  await expect.poll(async () => (await offset(page))[0]).toBeGreaterThan(8);
});

test('system reduced motion disables pointer follow even after pointer movement', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await demo(page);
  await page.mouse.move(1500, 800);
  await expect.poll(async () => await offset(page)).toEqual([0, 0]);
  await expect(page.locator('.original-polar-grid svg')).toHaveCSS('animation-name', 'none');
});
