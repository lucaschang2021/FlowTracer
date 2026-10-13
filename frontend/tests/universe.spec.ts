import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

async function camera(page: Page) {
  return page.getByTestId('world-layer').evaluate(el => {
    const m = new DOMMatrix(getComputedStyle(el).transform);
    return { x: m.e, y: m.f, zoom: m.a };
  });
}
const nodes = (page: Page) => page.locator('[data-radar]');
const pageErrors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  pageErrors.set(page, errors);
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', e => { if (e.type() === 'error') errors.push(e.text()); });
  page.on('request', request => {
    if (!request.url().startsWith('http://127.0.0.1:1420/')) errors.push(`Unexpected external request: ${request.url()}`);
  });
  await page.goto('/');
  await page.getByRole('button', { name: '跳过动画' }).click();
  await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(nodes(page)).toHaveCount(6);
  await expect(page.getByTestId('universe')).toHaveAttribute('data-projection', 'ready');
  await expect(page.getByLabel('当前缩放')).not.toHaveText('100%');
  // Store collected events on the test, including any later interactions.
  test.info().annotations.push({ type: 'offline-mode', description: 'All requests must remain on the local preview origin.' });
});
test.afterEach(async ({ page }) => { expect(pageErrors.get(page)).toEqual([]); });

for (const viewport of [{ width: 1366, height: 768 }, { width: 1600, height: 900 }, { width: 1920, height: 1080 }]) {
  test(`layout and screenshots ${viewport.width}x${viewport.height}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    // setViewportSize completes before ResizeObserver's next rendering step.
    // Wait for the actual fitted camera, not a timeout or a stale 1600px layout.
    const expectedZoom = Math.min((viewport.width - 270) / 880, (viewport.height - 144 - 340) / 345, 1.25);
    await expect.poll(async () => (await camera(page)).zoom).toBeCloseTo(expectedZoom, 5);
    await expect(page.getByTestId('detail-panel')).toHaveCount(0);
    await expect(page.getByText('离线演示', { exact: true })).toBeVisible();
    const rects = await nodes(page).evaluateAll(elements => elements.map(el => {
      const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, right: r.right, bottom: r.bottom };
    }));
    for (const r of rects) { expect(r.x).toBeGreaterThan(0); expect(r.right).toBeLessThan(viewport.width); expect(r.y).toBeGreaterThan(136); expect(r.bottom).toBeLessThan(viewport.height - 130); }
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
    const header = await page.locator('.app-header').evaluate(el => Array.from(el.children).map(child => { const r = child.getBoundingClientRect(); return { left: r.left, right: r.right }; }));
    expect(header[0].right).toBeLessThan(header[1].left); expect(header[1].right).toBeLessThan(header[2].left);
    await page.screenshot({ path: info.outputPath(`canvas-${viewport.width}.png`) });
    await page.getByRole('button', { name: '查看 AI Research Galaxy 演示结构' }).click();
    await expect(page.getByRole('heading', { name: 'AI Research Galaxy' })).toBeVisible();
    const panel = await page.getByTestId('detail-panel').boundingBox();
    const zoom = await page.getByRole('button', { name: '缩小星图' }).boundingBox();
    expect(panel!.y + panel!.height).toBeLessThan(zoom!.y);
    await page.screenshot({ path: info.outputPath(`galaxy-${viewport.width}.png`) });
    await page.getByRole('button', { name: '关闭详情' }).click();
    await expect(page.getByRole('button', { name: '查看 AI Research Galaxy 演示结构' })).toBeFocused();
  });
}

test('select, close, drag threshold, keyboard movement and reset', async ({ page }) => {
  const node = page.locator('[data-radar="demo-market"]');
  await node.click();
  await expect(page.getByRole('heading', { name: 'Market Observatory' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('detail-panel')).toHaveCount(0);
  await expect(node).toBeFocused();
  const before = await node.boundingBox();
  await page.mouse.move(before!.x + 85, before!.y + 40);
  await page.mouse.down(); await page.mouse.move(before!.x + 155, before!.y + 65, { steps: 8 }); await page.mouse.up();
  await expect(page.getByTestId('detail-panel')).toHaveCount(0);
  const after = await node.boundingBox();
  expect(after!.x - before!.x).toBeCloseTo(70, 0); expect(after!.y - before!.y).toBeCloseTo(25, 0);
  await node.focus(); await page.keyboard.press('Alt+ArrowRight');
  expect((await node.boundingBox())!.x - after!.x).toBeCloseTo(16, 0);
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('detail-panel')).toBeVisible();
  await page.getByRole('button', { name: '重置演示布局' }).click();
  await expect(page.getByTestId('detail-panel')).toHaveCount(0);
  expect(await node.evaluate(el => el.style.left)).toBe('20px');
});

test('cursor anchored wheel, limits, Space pan and fit', async ({ page }) => {
  const canvas = page.getByTestId('universe');
  const bounds = await canvas.boundingBox();
  const anchor = { x: 780, y: 280 };
  const before = await camera(page);
  await page.mouse.move(anchor.x + bounds!.x, anchor.y + bounds!.y);
  await page.mouse.wheel(0, -70);
  await expect.poll(async () => (await camera(page)).zoom).toBeGreaterThan(before.zoom);
  const after = await camera(page);
  expect((anchor.x - before.x) / before.zoom).toBeCloseTo((anchor.x - after.x) / after.zoom, 2);
  expect((anchor.y - before.y) / before.zoom).toBeCloseTo((anchor.y - after.y) / after.zoom, 2);
  for (let i = 0; i < 12; i++) await page.getByRole('button', { name: '放大星图' }).click();
  await expect(page.getByLabel('当前缩放')).toHaveText('240%');
  for (let i = 0; i < 24; i++) await page.getByRole('button', { name: '缩小星图' }).click();
  await expect(page.getByLabel('当前缩放')).toHaveText('35%');
  await canvas.focus();
  const start = await camera(page);
  await page.keyboard.down('Space'); await page.mouse.move(250, 220); await page.mouse.down(); await page.mouse.move(350, 280, { steps: 8 }); await page.mouse.up(); await page.keyboard.up('Space');
  await expect.poll(async () => Math.round((await camera(page)).x - start.x)).toBe(100);
  expect(Math.round((await camera(page)).y - start.y)).toBe(60);
  await page.getByRole('button', { name: '适配全部行星', exact: true }).click();
  await expect.poll(async () => (await camera(page)).zoom).toBeCloseTo(before.zoom, 4);
});

test('honest navigation, empty canvas, reduced motion and guide focus', async ({ page }, info) => {
  for (const name of ['信号', '记忆', '机会']) {
    await page.getByRole('button', { name, exact: true }).click();
    await expect(page.getByText('这片星域，尚未接入。')).toBeVisible();
  }
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await page.getByRole('checkbox', { name: /减少动态效果/ }).check();
  await page.getByRole('button', { name: '查看空画布' }).click();
  await expect(nodes(page)).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '一片安静的星空。' })).toBeVisible();
  await page.screenshot({ path: info.outputPath('empty-canvas.png') });
  await page.getByRole('button', { name: '载入演示 Radar' }).click();
  await expect(nodes(page)).toHaveCount(6);
  expect(await page.locator('.planet').first().evaluate(el => getComputedStyle(el).transitionDuration)).toBe('0s');
  await page.getByRole('button', { name: '设置', exact: true }).click();
  await page.getByRole('checkbox', { name: /减少动态效果/ }).uncheck();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.getByRole('button', { name: '星图', exact: true }).click();
  expect(await page.locator('.planet').first().evaluate(el => getComputedStyle(el).transitionDuration)).toBe('0s');
  await page.getByRole('button', { name: '查看演示说明' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Tab'); await expect(page.getByRole('button', { name: '关闭演示说明' })).toBeFocused();
  await page.keyboard.press('Escape'); await expect(page.getByRole('button', { name: '查看演示说明' })).toBeFocused();
});
