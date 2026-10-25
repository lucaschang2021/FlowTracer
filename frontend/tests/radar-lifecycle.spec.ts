import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const id = '00000000-0000-4000-8000-000000000011';
const otherId = '00000000-0000-4000-8000-000000000012';
const record = { id, name: 'Lifecycle Radar', description: 'Keep layout', goal: 'Track lifecycle', radarType: 'technology', categories: [], keywords: [], status: 'active', notificationThreshold: 75 };
const other = { ...record, id: otherId, name: 'Other Radar', radarType: 'market' };
const user = { id: '00000000-0000-4000-8000-000000000001', email: 'person@example.com', displayName: 'Explorer', isActive: true };

async function signIn(page: Page) {
  await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle'); await page.getByLabel('邮箱').fill('person@example.com'); await page.getByLabel('密码').fill('not-a-real-password');
  await page.getByRole('button', { name: '登录并载入星图' }).click(); await expect(page.getByTestId('universe')).toHaveAttribute('data-mode', 'live'); await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion', 'idle');
}
async function select(page: Page) { await page.locator(`[data-radar="${id}"]`).click(); await expect(page.getByTestId('detail-panel')).toBeVisible(); }

test('pause, resume and named soft-delete confirmation mutate only after confirmed responses', async ({ page }) => {
  await page.addInitScript(({ record, other, user }) => {
    const state = window as typeof window & { __calls?: Record<string, number>; __releasePause?: () => void; __releaseDelete?: () => void };
    state.__calls = { pause: 0, resume: 0, delete: 0 };
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string, args?: { radarId?: string }) => {
      if (command === 'bridge_status') return { available: true }; if (command === 'health_ready') return { ready: true }; if (command === 'auth_login') return { authenticated: true, user }; if (command === 'users_me') return user;
      if (command === 'radars_list') return { items: [record, other], page: 1, pageSize: 100, total: 2 };
      if (!args?.radarId || args.radarId !== record.id) { if (command.startsWith('radars_')) throw Error('wrong Radar identity'); }
      if (command === 'radars_pause') { state.__calls!.pause += 1; return await new Promise(resolve => { state.__releasePause = () => resolve({ ...record, status: 'paused' }); }); }
      if (command === 'radars_resume') { state.__calls!.resume += 1; return { ...record, status: 'active' }; }
      if (command === 'radars_delete') { state.__calls!.delete += 1; return await new Promise<void>(resolve => { state.__releaseDelete = resolve; }); }
      if (command === 'auth_logout') return; throw Error(`Unexpected command: ${command}`);
    } } });
  }, { record, other, user });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await signIn(page); await select(page);
  const node = page.locator(`[data-radar="${id}"]`); const before = await node.evaluate(el => ({ left: (el as HTMLElement).style.left, top: (el as HTMLElement).style.top }));
  const pause = page.getByRole('button', { name: '暂停 Radar' }); await pause.click(); let dialog = page.getByRole('dialog', { name: '暂停 Radar' }); await expect(dialog.getByRole('button', { name: '取消' })).toBeFocused();
  await dialog.getByRole('button', { name: '取消' }).click(); await expect(pause).toBeFocused(); expect(await page.evaluate(() => (window as typeof window & { __calls?: Record<string, number> }).__calls!.pause)).toBe(0);
  await pause.click(); dialog = page.getByRole('dialog', { name: '暂停 Radar' }); const confirmPause = dialog.getByRole('button', { name: '确认暂停' }); await confirmPause.evaluate(button => { button.click(); button.click(); });
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __calls?: Record<string, number> }).__calls!.pause)).toBe(1); await page.keyboard.press('Escape'); await expect(dialog).toBeVisible();
  await page.evaluate(() => (window as typeof window & { __releasePause?: () => void }).__releasePause?.()); await expect(dialog).toHaveCount(0); const resume = page.getByRole('button', { name: '恢复 Radar' }); await expect(resume).toBeFocused();
  expect(await node.evaluate(el => ({ left: (el as HTMLElement).style.left, top: (el as HTMLElement).style.top }))).toEqual(before); await expect(page.getByTestId('detail-panel')).toBeVisible();
  await resume.click(); await page.getByRole('dialog', { name: '恢复 Radar' }).getByRole('button', { name: '确认恢复' }).click(); await expect(page.getByRole('button', { name: '暂停 Radar' })).toBeFocused();
  await page.getByRole('button', { name: '移除 Radar' }).click(); dialog = page.getByRole('dialog', { name: '移除 Radar' }); await expect(dialog).toContainText('Lifecycle Radar'); await expect(dialog).toContainText('软删除'); await expect(dialog.getByRole('button', { name: '取消' })).toBeFocused();
  await dialog.getByRole('button', { name: '取消' }).click(); expect(await page.evaluate(() => (window as typeof window & { __calls?: Record<string, number> }).__calls!.delete)).toBe(0);
  await page.getByRole('button', { name: '移除 Radar' }).click(); dialog = page.getByRole('dialog', { name: '移除 Radar' }); const confirmDelete = dialog.getByRole('button', { name: '确认移除“Lifecycle Radar”' }); await confirmDelete.evaluate(button => { button.click(); button.click(); });
  await expect.poll(() => page.evaluate(() => (window as typeof window & { __calls?: Record<string, number> }).__calls!.delete)).toBe(1); await page.evaluate(() => (window as typeof window & { __releaseDelete?: () => void }).__releaseDelete?.());
  await expect(page.locator(`[data-radar="${id}"]`)).toHaveCount(0); await expect(page.locator(`[data-radar="${otherId}"]`)).toHaveCount(1); await expect(page.getByTestId('detail-panel')).toHaveCount(0); await expect(page.getByTestId('universe')).toBeFocused();
});

test('409 keeps original status and permits one retry without duplicate pending calls', async ({ page }) => {
  await page.addInitScript(({ record, user }) => { let calls = 0; Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => {
    if (command === 'bridge_status') return { available: true }; if (command === 'health_ready') return { ready: true }; if (command === 'auth_login') return { authenticated: true, user }; if (command === 'users_me') return user; if (command === 'radars_list') return { items: [record], page: 1, pageSize: 100, total: 1 };
    if (command === 'radars_pause') { calls += 1; if (calls === 1) throw { kind: 'api', message: 'Lifecycle conflict', status: 409 }; return { ...record, status: 'paused' }; } throw Error(`Unexpected command: ${command}`);
  } } }); }, { record, user });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await signIn(page); await select(page); await page.getByRole('button', { name: '暂停 Radar' }).click(); const dialog = page.getByRole('dialog', { name: '暂停 Radar' });
  await dialog.getByRole('button', { name: '确认暂停' }).click(); await expect(dialog.getByRole('alert')).toContainText('Lifecycle conflict'); await expect(page.getByRole('button', { name: '暂停 Radar' })).toHaveCount(1);
  await dialog.getByRole('button', { name: '确认暂停' }).click(); await expect(dialog).toHaveCount(0); await expect(page.getByRole('button', { name: '恢复 Radar' })).toBeVisible();
});

test('account switch fences a late lifecycle response', async ({ page }) => {
  await page.addInitScript(({ record }) => { let logins = 0; let release: (() => void) | undefined; const users = [{ id:'00000000-0000-4000-8000-000000000001',email:'first@example.com',displayName:'First',isActive:true },{ id:'00000000-0000-4000-8000-000000000002',email:'second@example.com',displayName:'Second',isActive:true }];
    Object.assign(window as typeof window & { __release?: () => void }, { __release: () => release?.() }); Object.defineProperty(window, '__TAURI_INTERNALS__', { value: { invoke: async (command: string) => { if (command==='bridge_status') return {available:true}; if(command==='health_ready') return {ready:true}; if(command==='auth_login'){logins+=1;return{authenticated:true,user:users[Math.min(logins-1,1)]}}; if(command==='users_me')return users[Math.min(logins-1,1)]; if(command==='radars_list')return{items:logins===1?[record]:[],page:1,pageSize:100,total:logins===1?1:0}; if(command==='radars_pause')return await new Promise(resolve=>{release=()=>resolve({...record,status:'paused'})}); if(command==='auth_logout')return; throw Error(`Unexpected command: ${command}`); } } });
  }, { record });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await signIn(page); await select(page); await page.getByRole('button', { name: '暂停 Radar' }).click(); await page.getByRole('dialog', { name: '暂停 Radar' }).getByRole('button', { name: '确认暂停' }).click();
  await page.locator('.main-nav button').filter({ hasText: /^设置$/ }).dispatchEvent('click'); await page.locator('.settings-list button').filter({ hasText: /^退出登录$/ }).first().dispatchEvent('click'); await expect(page.getByRole('heading', { name: '欢迎回来。' })).toBeVisible(); await signIn(page); await page.evaluate(() => (window as typeof window & { __release?: () => void }).__release?.()); await expect(page.locator('[data-radar]')).toHaveCount(0);
});

test('demo exposes no lifecycle actions and sends no writes', async ({ page }) => {
  await page.addInitScript(() => { (window as typeof window & { __writes?: number }).__writes=0; Object.defineProperty(window,'__TAURI_INTERNALS__',{value:{invoke:async(command:string)=>{if(command==='bridge_status')return{available:true};if(command==='health_ready')return{ready:true};if(command.startsWith('radars_'))(window as typeof window & {__writes?:number}).__writes=1;throw Error(`Unexpected command: ${command}`)}}}); });
  await page.goto('/'); await page.getByRole('button', { name: '跳过动画' }).click(); await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion','idle'); await page.getByRole('button',{name:'进入演示星图'}).click(); await expect(page.locator('.stage-scene')).toHaveAttribute('data-motion','idle'); await page.locator('[data-radar="demo-market"]').click();
  for (const name of ['暂停 Radar','恢复 Radar','移除 Radar']) await expect(page.getByRole('button',{name})).toHaveCount(0); expect(await page.evaluate(()=>(window as typeof window & {__writes?:number}).__writes)).toBe(0);
});
