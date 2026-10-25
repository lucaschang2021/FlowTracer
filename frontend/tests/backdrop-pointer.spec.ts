import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const backdrop = (page: Page) => page.getByTestId('original-backdrop');
async function fixed(page: Page) {
  // Sample across frames: an immediate zero before a queued pointer handler is insufficient.
  const samples = await backdrop(page).evaluate(async element => {
    const values = [];
    for (let frame = 0; frame < 18; frame++) {
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
      const style = getComputedStyle(element), rect = element.getBoundingClientRect();
      values.push({ translate: style.translate, transform: style.transform, x: rect.x, y: rect.y });
    }
    return values;
  });
  for (const sample of samples) expect(sample).toEqual({ translate: 'none', transform: 'none', x: -16, y: -16 });
}
async function demo(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: '跳过动画' }).click();
  await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
  await expect(page.getByTestId('universe')).toHaveAttribute('data-projection', 'ready');
}
test('mouse movement leaves background and foreground fixed while autonomous rotation continues', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await demo(page);
  const foreground = page.locator('.app-shell'), before = await foreground.boundingBox();
  const orbit = page.locator('.original-polar-grid svg');
  const initialRotation = await orbit.evaluate(el => getComputedStyle(el).transform);
  for (const [x, y] of [[1590, 890], [10, 10], [800, 450]]) {
    await page.mouse.move(x, y); await fixed(page);
    expect(await foreground.boundingBox()).toEqual(before);
  }
  const bounds = await backdrop(page).boundingBox();
  expect(bounds!.x + bounds!.width).toBeGreaterThanOrEqual(1600);
  expect(bounds!.y + bounds!.height).toBeGreaterThanOrEqual(900);
  await expect(backdrop(page)).toHaveCSS('pointer-events', 'none');
  await expect(backdrop(page)).toHaveCSS('transition-duration', '0s');
  await expect(orbit).toHaveCSS('animation-duration', '120s');
  expect(await orbit.evaluate(el => getComputedStyle(el).transform)).not.toBe(initialRotation);
  expect(errors).toEqual([]);
});
test('Radar dragging, canvas pan and zoom work without background displacement; leave and blur stay fixed', async ({ page }) => {
  await demo(page);
  const node = page.locator('[data-radar="demo-market"]');
  const position = () => node.evaluate(el => ({ x: (el as HTMLElement).style.left, y: (el as HTMLElement).style.top }));
  const before = await position(), box = await node.boundingBox();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await page.mouse.down(); await page.mouse.move(box!.x + box!.width / 2 + 55, box!.y + box!.height / 2 + 25, { steps: 6 });
  await fixed(page); await page.mouse.up();
  expect(await position()).not.toEqual(before);
  const moved = await node.boundingBox();
  await page.getByTestId('universe').focus(); await page.keyboard.down('Space');
  await page.mouse.move(800, 740); await page.mouse.down(); await page.mouse.move(880, 760, { steps: 6 });
  await page.mouse.up(); await page.keyboard.up('Space');
  await fixed(page);
  expect((await node.boundingBox())!.x).toBeGreaterThan(moved!.x + 50);
  const zoom = page.getByRole('status', { name: '当前缩放' }), oldZoom = await zoom.textContent();
  await page.getByRole('button', { name: '缩小星图', exact: true }).click();
  await expect(zoom).not.toHaveText(oldZoom!);
  await page.evaluate(() => window.dispatchEvent(new Event('blur'))); await fixed(page);
  await page.evaluate(() => window.dispatchEvent(new PointerEvent('pointerout', { relatedTarget: null }))); await fixed(page);
});
test('quiet preference and re-enabled motion both keep background fixed', async ({ page }) => {
  await demo(page);
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await expect(page.locator('.page-scene')).toHaveAttribute('data-motion', 'idle');
  const quiet = page.getByRole('checkbox', { name: /减少动态效果/ });
  await quiet.check(); await page.mouse.move(1500, 800); await fixed(page);
  await expect(page.locator('.original-polar-grid svg')).toHaveCSS('animation-name', 'none');
  await quiet.uncheck(); await page.mouse.move(1450, 780); await fixed(page);
  await expect(page.locator('.original-polar-grid svg')).toHaveCSS('animation-name', 'original-turn');
});
test('system reduced motion keeps background fixed and foreground selection usable', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' }); await demo(page);
  await page.mouse.move(1500, 800); await fixed(page);
  await expect(page.locator('.original-polar-grid svg')).toHaveCSS('animation-name', 'none');
  await page.locator('[data-radar="demo-market"]').click();
  await expect(page.getByRole('heading', { name: 'Market Observatory', exact: true })).toBeVisible();
  await fixed(page);
});
