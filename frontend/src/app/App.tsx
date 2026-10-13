import { useEffect, useRef, useState } from 'react';
import { Universe } from '../features/universe/Universe';
import { freshDemo } from '../features/universe/demo';
import { Icon } from './Icon';
import { LanguageSelect, PreferencesProvider, usePreferences } from './Preferences';
import { Entry } from './Entry';
import { useScene } from './motion';

const pages = ['Canvas', 'Signals', 'Memory', 'Opportunities', 'Settings'] as const;
const pageNames = { Canvas: '星图', Signals: '信号', Memory: '记忆', Opportunities: '机会', Settings: '设置' };
type Page = typeof pages[number];
export default function App() { return <PreferencesProvider><DemoApp/></PreferencesProvider>; }
function DemoApp() {
  const { quiet } = usePreferences();
  const { value: stage, change: setStage, phase, busy } = useScene<'intro' | 'login' | 'workspace'>('intro');
  const screen = useRef<HTMLDivElement>(null);
  useEffect(() => { if (!busy) screen.current?.querySelector<HTMLElement>(stage === 'workspace' ? '[data-testid="universe"]' : '.entry-screen')?.focus({ preventScroll: true }); }, [stage, busy]);
  return <div className={quiet ? 'quiet-mode' : undefined}><div ref={screen} className="stage-scene" data-motion={phase} data-stage={stage} inert={busy}>{stage === 'workspace'
    ? <Workspace onLeave={() => setStage('login')} onReplay={() => setStage('intro')}/>
    : <Entry stage={stage} onContinue={() => setStage(stage === 'intro' ? 'login' : 'workspace')} onBack={() => setStage('intro')}/>}</div></div>;
}
function Workspace({ onLeave, onReplay }: { onLeave: () => void; onReplay: () => void }) {
  const { quiet, setQuiet, t } = usePreferences();
  const { value: page, change: setPage, phase: pagePhase, busy: pageBusy } = useScene<Page>('Canvas');
  const [radars, setRadars] = useState(freshDemo);
  const [resetKey, setResetKey] = useState(0);
  const [showGuide, setShowGuide] = useState(false);
  const guideButton = useRef<HTMLButtonElement>(null);
  const closeGuide = () => { setShowGuide(false); requestAnimationFrame(() => guideButton.current?.focus()); };
  const reset = () => { setRadars(freshDemo()); setResetKey(n => n + 1); setPage('Canvas'); };
  return <div className="app-shell">
    <header className="app-header" inert={showGuide}>
      <a className="brand" href="#canvas" onClick={e => { e.preventDefault(); setPage('Canvas'); }} aria-label={t('FlowTracer，返回星图', 'FlowTracer, return to star map')}>
        <span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 56 56"><circle cx="28" cy="28" r="21"/><circle cx="28" cy="28" r="26" opacity=".2"/><path d="M28 0v56M0 28h56" opacity=".35"/><path className="brand-star" d="M28 15Q30 26 40 28Q30 30 28 41Q26 30 16 28Q26 26 28 15"/></svg></span>
        <span><span className="brand-name">FLOWTRACER</span><span className="brand-tagline">{t('个人情报宇宙', 'PERSONAL INTELLIGENCE UNIVERSE')}</span></span>
      </a>
      <nav className="main-nav" aria-label={t('主导航', 'Main navigation')}>{pages.map(item => <button key={item} aria-current={item === page ? 'page' : undefined} onClick={() => setPage(item)}>{t(pageNames[item], item)}</button>)}</nav>
      <div className="header-actions"><span className="demo-badge">{t('离线演示', 'OFFLINE UX DEMO')}</span><button ref={guideButton} className="icon-button" aria-label={t('查看演示说明', 'Demo guide')} onClick={() => setShowGuide(true)}><Icon name="plus"/></button><button className="icon-button" aria-label={t('重置演示布局', 'Reset demo layout')} onClick={reset}><Icon name="reset"/></button></div>
    </header>
    <main className="app-main" inert={showGuide}>
      <div className="page-scene" data-motion={pagePhase} data-page={page} inert={pageBusy}>
      {page === 'Canvas' ? <Universe key={resetKey} radars={radars} onChange={setRadars} onLoad={reset}/> : <section className="utility-page" aria-labelledby="page-heading">
        <span className="eyebrow">FLOWTRACER / {t(pageNames[page], page.toUpperCase())}</span>
        <h1 id="page-heading">{page === 'Settings' ? t('让宇宙，适合你。', 'Make this universe yours.') : t(pageNames[page], page)}</h1>
        {page === 'Settings' ? <div className="settings-list">
          <div className="setting-row"><span><strong>{t('显示语言', 'Display language')}</strong><small>{t('立即生效并保存在本机；不改变 Radar 名称。', 'Saved on this device. Radar names remain unchanged.')}</small></span><LanguageSelect/></div>
          <label className="setting-row"><span><strong>{t('减少动态效果', 'Reduce motion')}</strong><small>{t('同时尊重系统的“减少动态效果”设置。', 'System reduced-motion preferences are also respected.')}</small></span><input type="checkbox" checked={quiet} onChange={e => setQuiet(e.target.checked)}/></label>
          <div className="setting-row"><span><strong>{t('画布状态预览', 'Canvas previews')}</strong><small>{t('布局仅保留在当前演示会话。', 'Layout changes last only for this demo session.')}</small></span><div className="button-row"><button className="text-button" onClick={() => { setRadars([]); setPage('Canvas'); }}>{t('查看空画布', 'Empty canvas')}</button><button className="text-button" onClick={reset}>{t('恢复演示布局', 'Restore demo')}</button></div></div>
          <div className="setting-row"><span><strong>{t('启动与登录', 'Startup & sign-in')}</strong><small>{t('演示入口，不验证账号、不保存凭据。', 'Preview only. No authentication or credentials are stored.')}</small></span><div className="button-row"><button className="text-button" onClick={onReplay}>{t('重播启动动画', 'Replay intro')}</button><button className="text-button" onClick={onLeave}>{t('返回演示登录', 'Return to demo sign-in')}</button></div></div>
          <div><h2>{t('演示环境', 'Demo environment')}</h2><p>{t('本地示例数据。未连接账户、后端或采集服务。', 'Local fixtures only. No account, backend or collection service is connected.')}</p><span className="status-label">{t('仅限沙盒演示', 'SANDBOX ONLY')}</span></div>
        </div> : <><div className="placeholder-symbol" aria-hidden="true"><Icon name="radar"/></div><p className="page-summary">{t('这片星域，尚未接入。', 'This constellation is not connected yet.')}</p><p className="muted">{t('当前为离线交互演示。此页面没有接入真实数据，也不会发起采集或写入请求。', 'This is an offline interaction demo. This page does not load live data, collect information or send writes.')}</p><button className="text-button" onClick={() => setPage('Canvas')}>{t('返回星图', 'Return to star map')} <Icon name="arrow"/></button></>}
      </section>}
      </div>
    </main>
    <footer className="status-bar" inert={showGuide} aria-label={t('演示统计', 'Demo statistics')}><div><span className="stat-symbol" aria-hidden="true">◎</span><span><span className="stat-label">{t('雷达行星 · 演示', 'RADAR WORLDS · DEMO')}</span><strong>{radars.length}</strong></span></div><div><span className="stat-symbol" aria-hidden="true">✧</span><span><span className="stat-label">{t('星系 · 演示', 'GALAXIES · DEMO')}</span><strong>{radars.length ? 1 : 0}</strong></span></div><div><span className="stat-symbol" aria-hidden="true">✦</span><span><span className="stat-label">{t('新信号 · 演示', 'NEW SIGNALS · DEMO')}</span><strong>{radars.reduce((sum, radar) => sum + radar.signals, 0)}</strong></span></div><div><span className="stat-symbol" aria-hidden="true">◇</span><span><span className="stat-label">{t('状态', 'STATUS')}</span><strong className="sandbox-status">{t('仅限沙盒演示', 'SANDBOX ONLY')}</strong></span></div></footer>
    {showGuide && <div className="modal-scrim" onClick={e => { if (e.target === e.currentTarget) closeGuide(); }}><section className="guide-dialog" role="dialog" aria-modal="true" aria-labelledby="guide-title" onKeyDown={e => { if (e.key === 'Escape') closeGuide(); if (e.key === 'Tab') e.preventDefault(); }}>
      <button autoFocus className="panel-close icon-button" aria-label={t('关闭演示说明', 'Close demo guide')} onClick={closeGuide}><Icon name="close"/></button><span className="eyebrow">{t('离线交互演示', 'OFFLINE UX DEMO')}</span><h2 id="guide-title">{t('一张安静的情报星图。', 'A quiet map of your intelligence.')}</h2><p>{t('行星代表 Radar，轨道展示 Galaxy 分组的视觉结构。全部内容为隔离的演示数据。', 'Planets represent Radars; orbits show Galaxy groups. All content is isolated demo data.')}</p><p>{t('拖动行星、滚轮缩放、空格拖动画布。Tab 选择行星，Enter 查看；聚焦画布后用方向键平移。', 'Drag planets, scroll to zoom, or hold Space to pan. Tab through planets and press Enter to inspect. Arrow keys pan the focused canvas.')}</p><p className="muted">{t('不提供真实登录、创建 Radar、保存布局或后端连接。', 'No real sign-in, Radar creation, saved layouts or backend connection.')}</p></section></div>}
  </div>;
}
