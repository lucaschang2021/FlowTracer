import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const errors = new WeakMap<Page, string[]>();
test.beforeEach(async ({ page }) => {
  const seen: string[] = []; errors.set(page, seen);
  page.on('pageerror', error => seen.push(error.message));
  page.on('console', message => { if (message.type() === 'error') seen.push(message.text()); });
  page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:1420/')) seen.push(`Unexpected request: ${request.method()} ${request.url()}`); });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(page.getByTestId('universe')).toHaveAttribute('data-projection', 'ready');
});
test.afterEach(async ({ page }) => expect(errors.get(page)).toEqual([]));

test('marquee creates a persistent Galaxy that can be renamed, navigated and disbanded', async ({ page }) => {
  const market = page.locator('[data-radar="demo-market"]'), research = page.locator('[data-radar="demo-research"]');
  const a = await market.boundingBox(), b = await research.boundingBox();
  await page.mouse.move(Math.min(a!.x, b!.x) - 8, Math.min(a!.y, b!.y) - 8); await page.mouse.down();
  await page.mouse.move(Math.max(a!.x + a!.width, b!.x + b!.width) + 8, Math.max(a!.y + a!.height, b!.y + b!.height) + 8, { steps: 10 }); await page.mouse.up();
  await expect(page.getByText('已选择 2 个 Radar')).toBeVisible(); await page.getByRole('button', { name: '建立 Galaxy' }).click();
  await expect(page.getByTestId('galaxy-panel')).toBeVisible(); await page.getByRole('button', { name: '重命名 Galaxy' }).click(); await page.getByLabel('Galaxy 名称').fill('Frontier Watch'); await page.getByRole('button', { name: '保存名称' }).click();
  await page.getByTestId('galaxy-panel').getByRole('button', { name: /Research Frontiers/ }).click(); await expect(page.getByRole('heading', { name: 'Research Frontiers' })).toBeVisible(); await page.keyboard.press('Escape');
  await page.reload(); await page.getByRole('button', { name: '跳过动画' }).click(); await page.getByRole('button', { name: '进入演示星图' }).click();
  await page.getByRole('button', { name: '查看 Galaxy Frontier Watch' }).click(); await expect(page.getByRole('heading', { name: 'Frontier Watch' })).toBeVisible();
  await page.getByRole('button', { name: '解散 Galaxy（保留 Radar）' }).click(); await expect(page.locator('[data-radar]')).toHaveCount(6); await expect(page.getByRole('button', { name: '查看 Galaxy Frontier Watch' })).toHaveCount(0);
});

test('keyboard selection creates a Galaxy and Escape cancels selection', async ({ page }) => {
  const agent = page.locator('[data-radar="demo-agent"]'), opportunity = page.locator('[data-radar="demo-opportunity"]');
  await agent.focus(); await page.keyboard.press('Shift+Enter'); await opportunity.focus(); await page.keyboard.press('Shift+Enter'); await page.getByTestId('universe').focus(); await page.keyboard.press('g');
  await expect(page.getByTestId('galaxy-panel')).toBeVisible(); await page.getByRole('button', { name: '关闭 Galaxy' }).click();
  await marketSelect(page); await page.keyboard.press('Escape'); await expect(page.getByText('已选择 1 个 Radar')).toHaveCount(0);
});

async function marketSelect(page: Page) { const market = page.locator('[data-radar="demo-market"]'); await market.focus(); await page.keyboard.press('Shift+Enter'); }

test('corrupt demo storage falls back to memory with a visible warning', async ({ page }) => {
  await page.evaluate(() => localStorage.setItem('flowtracer:spatial:v1:demo', '{broken'));
  await page.reload(); await page.getByRole('button', { name: '跳过动画' }).click(); await page.getByRole('button', { name: '进入演示星图' }).click();
  await expect(page.getByRole('alert')).toContainText('已忽略损坏或不匹配的布局'); await expect(page.locator('[data-radar]')).toHaveCount(6);
});

test('storage refusal remains visible after a preference remount', async ({ page }) => {
  await page.evaluate(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key: string, value: string) {
      if (key.startsWith('flowtracer:spatial:')) throw new DOMException('denied', 'SecurityError');
      return original.call(this, key, value);
    };
  });
  await page.getByRole('button', { name: '设置', exact: true }).click(); await page.getByRole('checkbox', { name: /减少动态效果/ }).check();
  await page.getByRole('button', { name: '星图', exact: true }).click();
  const radar = page.locator('[data-radar="demo-market"]'); await radar.focus(); await page.keyboard.press('Alt+ArrowRight');
  await expect(page.getByRole('alert')).toContainText('本机布局存储不可用');
});
