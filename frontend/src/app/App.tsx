import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { desktopApi, errorMessage, isDesktopBridge } from '../api/desktop';
import type { BridgeError, CollectionRun, CollectionQueued, IntelligenceDetail, IntelligencePage, IntelligenceQuery, RadarCreateInput, RadarRecord, RadarUpdateInput, SourceCreateInput, SourcePage, SourceRecord, User } from '../api/desktop';
import { mapRadarPage, toUniverseRadar } from '../api/models';
import { RadarCreatePanel } from '../features/radars/RadarCreatePanel';
import { RadarEditPanel } from '../features/radars/RadarEditPanel';
import { RadarActionPanel } from '../features/radars/RadarActionPanel';
import type { RadarLifecycleAction } from '../features/radars/RadarActionPanel';
import { SourceCollectPanel } from '../features/sources/SourceCollectPanel';
import { SignalsPage } from '../features/signals/SignalsPage';
import { MemoryPage } from '../features/memory/MemoryPage';
import { OpportunityPage } from '../features/opportunities/OpportunityPage';
import { NotificationsPanel } from '../features/notifications/NotificationsPanel';
import type { AccountRequest } from '../api/product';
import { Universe } from '../features/universe/Universe';
import { freshDemo } from '../features/universe/demo';
import { DEMO_OWNER, storageKey } from '../features/universe/layout';
import type { UniverseRadar } from '../features/universe/model';
import { Icon } from './Icon';
import { LanguageSelect, PreferencesProvider, usePreferences } from './Preferences';
import { Entry } from './Entry';
import { useReducedMotion, useScene } from './motion';
import { OriginalBackdrop } from './OriginalBackdrop';

const pages = ['Canvas', 'Signals', 'Memory', 'Opportunities', 'Settings'] as const;
const pageNames = { Canvas: '星图', Signals: '信号', Memory: '记忆', Opportunities: '机会', Settings: '设置' };
type Page = typeof pages[number];
type Mode = 'live' | 'demo';
type BridgeUi = { available: boolean; origin?: string; ready: boolean | null; busy: boolean; error?: BridgeError };
export default function App() { return <PreferencesProvider><FlowApp/></PreferencesProvider>; }
function FlowApp() {
  const { quiet } = usePreferences();
  const reduced = useReducedMotion();
  const { value: stage, change: setStage, phase, busy } = useScene<'intro' | 'login' | 'workspace'>('intro');
  const screen = useRef<HTMLDivElement>(null);
  const requestEpoch = useRef(0);
  const [mode, setMode] = useState<Mode>('live');
  const [radars, setRadars] = useState<UniverseRadar[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [bridge, setBridge] = useState<BridgeUi>({ available: isDesktopBridge(), ready: null, busy: false });
  useEffect(() => { if (!busy) screen.current?.querySelector<HTMLElement>(stage === 'workspace' ? '[data-testid="universe"]' : '.entry-screen')?.focus({ preventScroll: true }); }, [stage, busy]);
  useEffect(() => {
    if (stage !== 'login') return;
    const epoch = ++requestEpoch.current;
    if (!isDesktopBridge()) { setBridge({ available: false, ready: null, busy: false }); return; }
    void desktopApi.status().then(async status => {
      if (epoch !== requestEpoch.current) return;
      setBridge({ available: status.available, origin: status.origin, ready: null, busy: false, error: status.error });
      if (!status.available) return;
      try { const readiness = await desktopApi.ready(); if (epoch === requestEpoch.current) setBridge(current => ({ ...current, ready: readiness.ready })); }
      catch (error) { if (epoch === requestEpoch.current) setBridge(current => ({ ...current, ready: false, error: errorMessage(error) })); }
    }).catch(error => { if (epoch === requestEpoch.current) setBridge({ available: false, ready: null, busy: false, error: errorMessage(error) }); });
    return () => { requestEpoch.current += 1; };
  }, [stage]);
  const authenticate = async (kind: 'login' | 'register', credentials: { email: string; password: string; displayName?: string }) => {
    const epoch = ++requestEpoch.current;
    setBridge(current => ({ ...current, busy: true, error: undefined }));
    try {
      if (kind === 'register') await desktopApi.register(credentials.email, credentials.password, credentials.displayName ?? '');
      else await desktopApi.login(credentials.email, credentials.password);
      credentials.password = '';
      const [account, page] = await Promise.all([desktopApi.me(), desktopApi.radars()]);
      const liveRadars = mapRadarPage(page);
      if (epoch !== requestEpoch.current) return;
      setMode('live'); setUser(account); setRadars(liveRadars); setBridge(current => ({ ...current, busy: false, error: undefined })); setStage('workspace', 'ink');
    } catch (error) {
      credentials.password = '';
      if (epoch === requestEpoch.current) setBridge(current => ({ ...current, busy: false, error: errorMessage(error) }));
    }
  };
  const enterDemo = () => { requestEpoch.current += 1; setMode('demo'); setUser(null); setRadars(freshDemo()); setBridge(current => ({ ...current, busy: false, error: undefined })); setStage('workspace'); };
  const leaveWorkspace = () => {
    requestEpoch.current += 1;
    const wasLive = mode === 'live';
    setUser(null); setRadars([]); setMode('live'); setStage('login');
    if (wasLive) void desktopApi.logout().catch(error => setBridge(current => ({ ...current, error: errorMessage(error) })));
  };
  const refreshSession = async () => {
    const epoch = ++requestEpoch.current;
    setBridge(current => ({ ...current, busy: true, error: undefined }));
    try { await desktopApi.refresh(); const account = await desktopApi.me(); if (epoch === requestEpoch.current) { setUser(account); setBridge(current => ({ ...current, busy: false })); } }
    catch (error) { if (epoch === requestEpoch.current) setBridge(current => ({ ...current, busy: false, error: errorMessage(error) })); }
  };
  const createRadar = async (input: RadarCreateInput) => {
    if (mode !== 'live' || !user) throw new Error('请先登录真实账户。');
    const epoch = requestEpoch.current;
    const record = await desktopApi.createRadar(input);
    if (epoch !== requestEpoch.current) throw new Error('账户已切换，请重新打开星图。');
    const radar = toUniverseRadar(record, radars.length, radars.length + 1);
    setRadars(current => [...current, radar]);
  };
  const getRadar = useCallback(async (id: string) => {
    if (mode !== 'live' || !user) throw new Error('请先登录真实账户。');
    const epoch = requestEpoch.current;
    const record = await desktopApi.radar(id);
    if (epoch !== requestEpoch.current) throw new Error('账户已切换，请重新打开星图。');
    return record;
  }, [mode, user]);
  const updateRadar = useCallback(async (id: string, input: RadarUpdateInput) => {
    if (mode !== 'live' || !user) throw new Error('请先登录真实账户。');
    const epoch = requestEpoch.current;
    const record = await desktopApi.updateRadar(id, input);
    if (epoch !== requestEpoch.current) throw new Error('账户已切换，请重新打开星图。');
    if (record.id !== id) throw new Error('Backend Radar identity does not match the requested Radar.');
    const mapped = toUniverseRadar(record, 0, 1);
    setRadars(current => current.map(radar => {
      if (radar.id !== id) return radar;
      return { ...mapped, x: radar.x, y: radar.y, signals: radar.signals };
    }));
  }, [mode, user]);
  const lifecycleRadar = useCallback(async (id: string, action: RadarLifecycleAction) => {
    if (mode !== 'live' || !user) throw new Error('请先登录真实账户。');
    const epoch = requestEpoch.current;
    if (action === 'delete') {
      await desktopApi.deleteRadar(id);
      if (epoch !== requestEpoch.current) throw new Error('账户已切换，请重新打开星图。');
      setRadars(current => current.filter(radar => radar.id !== id));
      return;
    }
    const record = action === 'pause' ? await desktopApi.pauseRadar(id) : await desktopApi.resumeRadar(id);
    if (epoch !== requestEpoch.current) throw new Error('账户已切换，请重新打开星图。');
    if (record.id !== id || record.status !== (action === 'pause' ? 'paused' : 'active')) throw new Error('Backend Radar lifecycle response is invalid.');
    const mapped = toUniverseRadar(record, 0, 1);
    setRadars(current => current.map(radar => radar.id === id ? { ...mapped, x: radar.x, y: radar.y, signals: radar.signals } : radar));
  }, [mode, user]);
  const sourceLists = useCallback(async (radarId: string,allPage:number,boundPage:number) => { if(mode!=='live'||!user)throw new Error('请先登录真实账户。');const epoch=requestEpoch.current;const [all,bound]=await Promise.all([desktopApi.sources(allPage,20),desktopApi.radarSources(radarId,boundPage,20)]);if(epoch!==requestEpoch.current)throw new Error('账户已切换，请重新打开星图。');return{all,bound};},[mode,user]);
  const createSource = useCallback(async(input:SourceCreateInput)=>{if(mode!=='live'||!user)throw new Error('请先登录真实账户。');const epoch=requestEpoch.current;const value=await desktopApi.createSource(input);if(epoch!==requestEpoch.current)throw new Error('账户已切换，请重新打开星图。');return value;},[mode,user]);
  const bindSource = useCallback(async(radarId:string,sourceId:string)=>{if(mode!=='live'||!user)throw new Error('请先登录真实账户。');const epoch=requestEpoch.current;await desktopApi.bindSource(radarId,sourceId);if(epoch!==requestEpoch.current)throw new Error('账户已切换，请重新打开星图。');},[mode,user]);
  const unbindSource = useCallback(async(radarId:string,sourceId:string)=>{if(mode!=='live'||!user)throw new Error('请先登录真实账户。');const epoch=requestEpoch.current;await desktopApi.unbindSource(radarId,sourceId);if(epoch!==requestEpoch.current)throw new Error('账户已切换，请重新打开星图。');},[mode,user]);
  const collectSource = useCallback(async(sourceId:string,key:string):Promise<CollectionQueued>=>{if(mode!=='live'||!user)throw new Error('请先登录真实账户。');const epoch=requestEpoch.current;const value=await desktopApi.collectSource(sourceId,key);if(epoch!==requestEpoch.current)throw new Error('账户已切换，请重新打开星图。');return value;},[mode,user]);
  const collectionRun = useCallback(async(runId:string,sourceId:string):Promise<CollectionRun>=>{if(mode!=='live'||!user)throw new Error('请先登录真实账户。');const epoch=requestEpoch.current;const value=await desktopApi.collectionRun(runId,sourceId);if(epoch!==requestEpoch.current)throw new Error('账户已切换，请重新打开星图。');return value;},[mode,user]);
  const intelligence = useCallback(async(query:IntelligenceQuery):Promise<IntelligencePage>=>{if(mode!=='live'||!user)throw new Error('请先登录真实账户。');const epoch=requestEpoch.current;const value=await desktopApi.intelligence(query);if(epoch!==requestEpoch.current)throw new Error('账户已切换，请重新打开信号。');return value;},[mode,user]);
  const intelligenceDetail = useCallback(async(id:string,radarId:string):Promise<IntelligenceDetail>=>{if(mode!=='live'||!user)throw new Error('请先登录真实账户。');const epoch=requestEpoch.current;const value=await desktopApi.intelligenceDetail(id,radarId);if(epoch!==requestEpoch.current)throw new Error('账户已切换，请重新打开信号。');return value;},[mode,user]);
  const accountRequest:AccountRequest=useCallback(async<T,>(operation:()=>Promise<T>)=>{if(mode!=='live'||!user)throw new Error('请先登录真实账户。');const epoch=requestEpoch.current;const value=await operation();if(epoch!==requestEpoch.current)throw new Error('账户已切换，请重新打开此页面。');return value;},[mode,user]);
  const bookmarkSignal=useCallback(async(documentId:string)=>{await accountRequest(()=>desktopApi.createBookmark({documentId}));},[accountRequest]);
  return <div className={quiet ? 'quiet-mode' : undefined}><div ref={screen} className="stage-scene" data-motion={phase} data-stage={stage} inert={busy}><OriginalBackdrop reduced={reduced}/>{stage === 'workspace'
    ? <Workspace mode={mode} radars={radars} setRadars={setRadars} user={user} bridge={bridge} accountRequest={accountRequest} onBookmarkSignal={bookmarkSignal} onLeave={leaveWorkspace} onReplay={() => setStage('intro')} onRefresh={refreshSession} onCreateRadar={createRadar} onGetRadar={getRadar} onUpdateRadar={updateRadar} onLifecycleRadar={lifecycleRadar} onSourceLists={sourceLists} onCreateSource={createSource} onBindSource={bindSource} onUnbindSource={unbindSource} onCollectSource={collectSource} onCollectionRun={collectionRun} onIntelligence={intelligence} onIntelligenceDetail={intelligenceDetail}/>
    : <Entry stage={stage} onContinue={() => setStage('login')} onBack={() => setStage('intro')} onDemo={enterDemo} onAuthenticate={authenticate} bridge={bridge}/>}</div></div>;
}
function Workspace({ mode, radars, setRadars, user, bridge, accountRequest, onBookmarkSignal, onLeave, onReplay, onRefresh, onCreateRadar, onGetRadar, onUpdateRadar, onLifecycleRadar, onSourceLists, onCreateSource, onBindSource, onUnbindSource, onCollectSource, onCollectionRun, onIntelligence, onIntelligenceDetail }: { mode: Mode; radars: UniverseRadar[]; setRadars: React.Dispatch<React.SetStateAction<UniverseRadar[]>>; user: User | null; bridge: BridgeUi; accountRequest:AccountRequest;onBookmarkSignal:(documentId:string)=>Promise<void>;onLeave: () => void; onReplay: () => void; onRefresh: () => Promise<void>; onCreateRadar: (input: RadarCreateInput) => Promise<void>; onGetRadar: (id: string) => Promise<RadarRecord>; onUpdateRadar: (id: string, input: RadarUpdateInput) => Promise<void>; onLifecycleRadar: (id: string, action: RadarLifecycleAction) => Promise<void>; onSourceLists:(id:string,a:number,b:number)=>Promise<{all:SourcePage;bound:SourcePage}>; onCreateSource:(input:SourceCreateInput)=>Promise<SourceRecord>; onBindSource:(r:string,s:string)=>Promise<void>; onUnbindSource:(r:string,s:string)=>Promise<void>; onCollectSource:(s:string,k:string)=>Promise<CollectionQueued>; onCollectionRun:(r:string,s:string)=>Promise<CollectionRun>; onIntelligence:(q:IntelligenceQuery)=>Promise<IntelligencePage>; onIntelligenceDetail:(id:string,r:string)=>Promise<IntelligenceDetail> }) {
  const { quiet, setQuiet, t } = usePreferences();
  const { value: page, change: setPage, phase: pagePhase, busy: pageBusy } = useScene<Page>('Canvas');
  const [resetKey, setResetKey] = useState(0);
  const [galaxyCount, setGalaxyCount] = useState(0);
  const [showGuide, setShowGuide] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [radarAction, setRadarAction] = useState<{ id: string; name: string; action: RadarLifecycleAction } | null>(null);
  const [sourceRadar, setSourceRadar] = useState<{id:string;name:string}|null>(null);
  const workspace = useRef<HTMLDivElement>(null);
  const guideButton = useRef<HTMLButtonElement>(null);
  const editTrigger = useRef<HTMLButtonElement | null>(null);
  const actionTrigger = useRef<HTMLButtonElement | null>(null);
  const deletionHandler = useRef<((id: string) => void) | null>(null);
  const applyLifecycle = async (id: string, action: RadarLifecycleAction) => {
    const cleanup = deletionHandler.current;
    await onLifecycleRadar(id, action);
    if (action === 'delete') cleanup?.(id);
  };
  const pendingActionFocus = useRef<{ action: RadarLifecycleAction | null; completed: boolean; trigger: HTMLButtonElement | null } | null>(null);
  const sourceTrigger = useRef<HTMLButtonElement | null>(null);
  const closeGuide = () => { setShowGuide(false); requestAnimationFrame(() => guideButton.current?.focus()); };
  const closeCreate = () => { setShowCreate(false); requestAnimationFrame(() => guideButton.current?.focus()); };
  const closeEdit = () => { setEditId(null); requestAnimationFrame(() => editTrigger.current?.focus()); };
  const openEdit = (id: string, trigger: HTMLButtonElement) => { editTrigger.current = trigger; setEditId(id); };
  const closeAction = (completed = false) => { pendingActionFocus.current = { action: radarAction?.action ?? null, completed, trigger: actionTrigger.current }; setRadarAction(null); };
  const openAction = (id: string, name: string, action: RadarLifecycleAction, trigger: HTMLButtonElement) => { actionTrigger.current = trigger; setRadarAction({ id, name, action }); };
  useLayoutEffect(() => {
    const pending = pendingActionFocus.current;
    const root = workspace.current;
    if (radarAction || !pending || !root) return;
    const target = pending.completed && pending.action === 'delete'
      ? root.querySelector<HTMLElement>('[data-testid="universe"]')
      : pending.completed && pending.action
        ? root.querySelector<HTMLElement>(`[data-lifecycle-action="${pending.action === 'pause' ? 'resume' : 'pause'}"]`)
        : pending.trigger;
    if (!target || target.closest('[inert]')) return;
    pendingActionFocus.current = null;
    target.focus({ preventScroll: true });
  }, [radarAction, radars]);
  useLayoutEffect(() => () => { pendingActionFocus.current = null; }, []);
  const openSources=(id:string,name:string,trigger:HTMLButtonElement)=>{sourceTrigger.current=trigger;setSourceRadar({id,name});}; const closeSources=()=>{setSourceRadar(null);requestAnimationFrame(()=>sourceTrigger.current?.focus());};
  const reset = () => { try { localStorage.removeItem(storageKey(DEMO_OWNER)); } catch { /* Universe reports storage refusal after remount. */ } setRadars(freshDemo()); setGalaxyCount(0); setResetKey(n => n + 1); setPage('Canvas'); };
  const demo = mode === 'demo';
  const spatialOwner = demo ? DEMO_OWNER : user?.id ?? '';
  return <div ref={workspace} className="app-shell" data-mode={mode}>
    <header className="app-header" inert={showGuide || showCreate || !!editId || !!radarAction || !!sourceRadar}>
      <a className="brand" href="#canvas" onClick={e => { e.preventDefault(); setPage('Canvas'); }} aria-label={t('FlowTracer，返回星图', 'FlowTracer, return to star map')}>
        <span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 56 56"><circle cx="28" cy="28" r="21"/><circle cx="28" cy="28" r="26" opacity=".2"/><path d="M28 0v56M0 28h56" opacity=".35"/><path className="brand-star" d="M28 15Q30 26 40 28Q30 30 28 41Q26 30 16 28Q26 26 28 15"/></svg></span>
        <span><span className="brand-name">FLOWTRACER</span><span className="brand-tagline">{t('个人情报宇宙', 'PERSONAL INTELLIGENCE UNIVERSE')}</span></span>
      </a>
      <nav className="main-nav" aria-label={t('主导航', 'Main navigation')}>{pages.map(item => <button key={item} aria-current={item === page ? 'page' : undefined} onClick={() => setPage(item)}>{t(pageNames[item], item)}</button>)}</nav>
      <div className="header-actions"><span className={`demo-badge${demo ? '' : ' live-badge'}`}>{demo ? t('离线演示', 'OFFLINE UX DEMO') : t('真实连接', 'LIVE CONNECTION')}</span><button ref={guideButton} className="icon-button" aria-label={demo ? t('查看演示说明', 'Demo guide') : t('新建 Radar', 'Create Radar')} onClick={() => demo ? setShowGuide(true) : setShowCreate(true)}><Icon name="plus"/></button>{demo && <button className="icon-button" aria-label={t('重置演示布局', 'Reset demo layout')} onClick={reset}><Icon name="reset"/></button>}</div>
    </header>
    <main className="app-main" inert={showGuide || showCreate || !!editId || !!radarAction || !!sourceRadar}>
      <div className="page-scene" data-motion={pagePhase} data-page={page} inert={pageBusy}>
      {page === 'Canvas' ? <Universe key={`${spatialOwner}-${resetKey}`} deletionHandler={deletionHandler} mode={mode} owner={spatialOwner} radars={radars} onChange={setRadars} onGalaxyCount={setGalaxyCount} onLoadDemo={demo ? reset : undefined} onEditRadar={demo ? undefined : openEdit} onLifecycleRadar={demo ? undefined : openAction} onSourcesRadar={demo?undefined:openSources}/> : page==='Signals'&&!demo?<SignalsPage radars={radars} onList={onIntelligence} onDetail={onIntelligenceDetail} onBookmark={onBookmarkSignal}/>:page==='Memory'&&!demo?<MemoryPage key={`memory-${spatialOwner}`} owner={spatialOwner} radars={radars} request={accountRequest}/>:page==='Opportunities'&&!demo?<OpportunityPage key={`opportunities-${spatialOwner}`} owner={spatialOwner} radars={radars} request={accountRequest}/>:<section className="utility-page" aria-labelledby="page-heading">
        <span className="eyebrow">FLOWTRACER / {t(pageNames[page], page.toUpperCase())}</span>
        <h1 id="page-heading">{page === 'Settings' ? t('让宇宙，适合你。', 'Make this universe yours.') : t(pageNames[page], page)}</h1>
        {page === 'Settings' ? <div className="settings-list">
          <div className="setting-row"><span><strong>{t('显示语言', 'Display language')}</strong><small>{t('立即生效并保存在本机；不改变 Radar 名称。', 'Saved on this device. Radar names remain unchanged.')}</small></span><LanguageSelect/></div>
          <label className="setting-row"><span><strong>{t('减少动态效果', 'Reduce motion')}</strong><small>{t('同时尊重系统的“减少动态效果”设置。', 'System reduced-motion preferences are also respected.')}</small></span><input type="checkbox" checked={quiet} onChange={e => setQuiet(e.target.checked)}/></label>
          {demo ? <div className="setting-row"><span><strong>{t('画布状态预览', 'Canvas previews')}</strong><small>{t('布局保存在隔离的本机演示空间，可随时重置。', 'Layout is saved in an isolated local demo space and can be reset.')}</small></span><div className="button-row"><button className="text-button" onClick={() => { setRadars([]); setPage('Canvas'); }}>{t('查看空画布', 'Empty canvas')}</button><button className="text-button" onClick={reset}>{t('恢复演示布局', 'Restore demo')}</button></div></div> : <div className="setting-row"><span><strong>{user?.displayName || user?.email}</strong><small>{t('令牌仅保存在原生内存；应用重开后需重新登录。', 'Tokens stay in native memory; app restart requires sign-in.')}</small></span><div className="button-row"><button className="text-button" disabled={bridge.busy} onClick={() => void onRefresh()}>{t('刷新会话', 'Refresh session')}</button><button className="text-button" onClick={onLeave}>{t('退出登录', 'Sign out')}</button></div></div>}
          <div className="setting-row"><span><strong>{t('启动与登录', 'Startup & sign-in')}</strong><small>{demo ? t('当前是持续标识的隔离演示。', 'This is a persistently labeled isolated demo.') : t('当前连接真实本机 API。', 'Connected to the real local API.')}</small></span><div className="button-row"><button className="text-button" onClick={onReplay}>{t('重播启动动画', 'Replay intro')}</button><button className="text-button" onClick={onLeave}>{demo ? t('返回演示登录', 'Return to demo sign-in') : t('退出登录', 'Sign out')}</button></div></div>
          <div><h2>{demo ? t('演示环境', 'Demo environment') : t('连接状态', 'Connection status')}</h2><p>{demo ? t('本地示例数据。未连接账户、后端或采集服务。', 'Local fixtures only. No account, backend or collection service is connected.') : t('当前候选已连接 Radar、Source、采集、Signals、Memory、Opportunity 与 REST 通知；G3 仍待产品验收。', 'The current candidate connects Radars, Sources, collection, Signals, Memory, Opportunities and REST notifications; G3 product acceptance remains pending.')}</p><span className="status-label">{demo ? t('仅限沙盒演示', 'SANDBOX ONLY') : bridge.ready ? t('本机 API 已就绪', 'LOCAL API READY') : t('本机 API 状态未知', 'LOCAL API STATUS UNKNOWN')}</span>{bridge.error && <p className="auth-error" role="alert">{bridge.error.message}</p>}</div>
          {!demo&&<NotificationsPanel key={`notifications-${spatialOwner}`} owner={spatialOwner} request={accountRequest}/>}
        </div> : <><div className="placeholder-symbol" aria-hidden="true"><Icon name="radar"/></div><p className="page-summary">{t('这片星域，尚未接入。', 'This constellation is not connected yet.')}</p><p className="muted">{demo ? t('当前为离线交互演示。此页面没有接入真实数据，也不会发起采集或写入请求。', 'This is an offline interaction demo. This page does not load live data, collect information or send writes.') : t('本轮只接入认证、用户、ready 与 Radar 读取；此页面仍为诚实占位。', 'This increment connects auth, user, readiness and Radar reads only. This page remains an explicit placeholder.')}</p><button className="text-button" onClick={() => setPage('Canvas')}>{t('返回星图', 'Return to star map')} <Icon name="arrow"/></button></>}
      </section>}
      </div>
    </main>
    {!demo && showCreate && <RadarCreatePanel onCreate={onCreateRadar} onClose={closeCreate}/>}
    {!demo && editId && <RadarEditPanel radarId={editId} onLoad={onGetRadar} onUpdate={onUpdateRadar} onClose={closeEdit}/>}
    {!demo && radarAction && <RadarActionPanel radarId={radarAction.id} radarName={radarAction.name} action={radarAction.action} onAction={applyLifecycle} onClose={closeAction}/>}
    {!demo&&sourceRadar&&<SourceCollectPanel radarId={sourceRadar.id} radarName={sourceRadar.name} onClose={closeSources} onLoad={onSourceLists} onCreate={onCreateSource} onBind={onBindSource} onUnbind={onUnbindSource} onCollect={onCollectSource} onRun={onCollectionRun}/>}
    <footer className="status-bar" inert={showGuide || showCreate || !!editId || !!radarAction || !!sourceRadar} aria-label={demo ? t('演示统计', 'Demo statistics') : t('真实连接状态', 'Live connection status')}><div><span className="stat-symbol" aria-hidden="true">◎</span><span><span className="stat-label">{demo ? t('雷达行星 · 演示', 'RADAR WORLDS · DEMO') : t('真实 RADAR', 'LIVE RADARS')}</span><strong>{radars.length}</strong></span></div><div><span className="stat-symbol" aria-hidden="true">✧</span><span><span className="stat-label">{demo ? t('星系 · 演示', 'GALAXIES · DEMO') : t('星系', 'GALAXIES')}</span><strong>{galaxyCount}</strong></span></div><div><span className="stat-symbol" aria-hidden="true">✦</span><span><span className="stat-label">{demo ? t('新信号 · 演示', 'NEW SIGNALS · DEMO') : t('新信号', 'NEW SIGNALS')}</span><strong>{demo ? radars.reduce((sum, radar) => sum + (radar.signals ?? 0), 0) : '—'}</strong></span></div><div><span className="stat-symbol" aria-hidden="true">◇</span><span><span className="stat-label">{t('状态', 'STATUS')}</span><strong className={demo ? 'sandbox-status' : 'live-status'}>{demo ? t('仅限沙盒演示', 'SANDBOX ONLY') : bridge.ready ? t('已就绪', 'READY') : t('未知', 'UNKNOWN')}</strong></span></div></footer>
    {showGuide && <div className="modal-scrim" onClick={e => { if (e.target === e.currentTarget) closeGuide(); }}><section className="guide-dialog" role="dialog" aria-modal="true" aria-labelledby="guide-title" onKeyDown={e => { if (e.key === 'Escape') closeGuide(); if (e.key === 'Tab') e.preventDefault(); }}>
      <button autoFocus className="panel-close icon-button" aria-label={demo ? t('关闭演示说明', 'Close demo guide') : t('关闭连接说明', 'Close connection guide')} onClick={closeGuide}><Icon name="close"/></button><span className="eyebrow">{demo ? t('离线交互演示', 'OFFLINE UX DEMO') : t('真实本机连接', 'LIVE LOCAL CONNECTION')}</span><h2 id="guide-title">{t('一张安静的情报星图。', 'A quiet map of your intelligence.')}</h2><p>{demo ? t('行星代表 Radar；Galaxy、位置和视图保存在独立演示空间。', 'Planets represent Radars; Galaxies, positions and view are saved in an isolated demo space.') : t('行星来自当前账户的真实 Radar；Galaxy、位置和视图按账户 UUID 隔离保存在本机。', 'Planets come from this account’s live Radars; Galaxies, positions and view are stored locally by account UUID.')}</p><p>{t('空白拖动框选，拖动行星，滚轮缩放，空格拖动画布。键盘可用 Shift + Enter 多选、G 建组、Escape 取消。', 'Drag empty space to marquee, drag planets, scroll to zoom, or Space-drag to pan. Keyboard users can use Shift+Enter to select, G to group and Escape to cancel.')}</p><p className="muted">{demo ? t('演示空间不连接账户、后端或采集服务。', 'The demo space connects to no account, backend or collection service.') : t('Galaxy 解散不会删除 Radar，也不会调用后端写接口。', 'Disbanding a Galaxy never deletes a Radar or calls a backend write API.')}</p></section></div>}
  </div>;
}
