import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent } from 'react';
import { usePreferences } from '../../app/Preferences';
import { useReducedMotion } from '../../app/motion';
import { Icon } from '../../app/Icon';
import { DEMO_GALAXY } from './demo';
import { Planet } from './Planet';
import { fitView, keepInView, movePoint, normalizedWheel, zoomAt } from './model';
import type { Point, Size, UniverseRadar, View } from './model';

type Props = { mode: 'live' | 'demo'; radars: UniverseRadar[]; onChange: (radars: UniverseRadar[]) => void; onLoadDemo?: () => void };
type Gesture = { pointerId: number; start: Point; view: View; radar?: UniverseRadar; moved: boolean; element?: HTMLButtonElement };
const PANEL_WIDTH = 370;
const typeLabels = { academic: '学术', business: '商业', technology: '技术', policy: '政策', market: '市场', custom: '自定义', opportunity: '机会', competitive: '竞争' };
const descriptions: Record<string, string> = {
  'demo-ai': 'Model infrastructure, inference efficiency and engineering practice.',
  'demo-policy': 'AI policy, public rules and industry governance.',
  'demo-market': 'Example interests in industry shifts and public market research.',
  'demo-research': 'Frontier papers, reproducible methods and research progress.',
  'demo-agent': 'Example Radar for agent collaboration and tool use.',
  'demo-opportunity': 'A visual map of opportunities. No automatic actions.',
};
const interactive = (target: EventTarget | null) => target instanceof Element && !!target.closest('button, input, a, select, textarea, [data-ui]');

export function Universe({ mode, radars, onChange, onLoadDemo }: Props) {
  const { t } = usePreferences();
  const reduced = useReducedMotion();
  const [projecting, setProjecting] = useState(!reduced);
  useEffect(() => {
    if (reduced) { setProjecting(false); return; }
    const timer = setTimeout(() => setProjecting(false), 1700);
    return () => clearTimeout(timer);
  }, [reduced]);
  const root = useRef<HTMLDivElement>(null);
  const layer = useRef<HTMLDivElement>(null);
  const zoomLabel = useRef<HTMLOutputElement>(null);
  const view = useRef<View>({ x: 0, y: 0, zoom: 1 });
  const size = useRef<Size>({ width: 1200, height: 700 });
  const nodes = useRef(new Map<string, HTMLButtonElement>());
  const gesture = useRef<Gesture | null>(null);
  const space = useRef(false);
  const suppressClick = useRef(false);
  const frame = useRef<number | null>(null);
  const panel = useRef<HTMLElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState(mode === 'demo' ? t('离线演示已载入。', 'Offline demo loaded.') : t('真实 Radar 星图已载入。', 'Live Radar map loaded.'));
  const selectedRadar = radars.find(r => r.id === selected);
  const galaxySelected = mode === 'demo' && selected === DEMO_GALAXY.id;
  const latest = useRef({ radars, selected, onChange });
  latest.current = { radars, selected, onChange };

  const paint = useCallback(() => {
    frame.current = null;
    if (layer.current) {
      const v = view.current;
      layer.current.style.transform = `translate(${v.x}px, ${v.y}px) scale(${v.zoom})`;
      layer.current.style.setProperty('--inverse-scale', String(1 / v.zoom));
    }
    if (zoomLabel.current) zoomLabel.current.value = `${Math.round(view.current.zoom * 100)}%`;
  }, []);
  const updateView = useCallback((next: View) => {
    view.current = next;
    if (frame.current === null) frame.current = requestAnimationFrame(paint);
  }, [paint]);
  const fit = useCallback(() => {
    updateView(fitView(latest.current.radars, size.current, latest.current.selected ? PANEL_WIDTH : 0));
    setAnnouncement(mode === 'demo' ? t('画布已适配全部演示行星。', 'View fitted to all demo planets.') : t('画布已适配全部 Radar。', 'View fitted to all Radars.'));
  }, [mode, updateView, t]);

  useLayoutEffect(() => {
    const element = root.current;
    if (!element) return;
    const resize = () => {
      size.current = { width: element.clientWidth, height: element.clientHeight };
      view.current = fitView(latest.current.radars, size.current, latest.current.selected ? PANEL_WIDTH : 0);
      paint();
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    return () => { observer.disconnect(); if (frame.current !== null) cancelAnimationFrame(frame.current); };
  }, [paint]);

  useEffect(() => {
    const element = root.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      if (event.target instanceof Element && event.target.closest('[data-ui]')) return;
      event.preventDefault();
      if (gesture.current) return;
      const bounds = element.getBoundingClientRect();
      const delta = normalizedWheel(event.deltaY, event.deltaMode, size.current.height);
      updateView(zoomAt(view.current, { x: event.clientX - bounds.left, y: event.clientY - bounds.top }, Math.exp(-delta * .0018)));
    };
    const keyDown = (event: KeyboardEvent) => {
      if (event.code === 'Space' && !interactive(event.target)) {
        event.preventDefault(); space.current = true; element.classList.add('pan-ready');
      }
    };
    const release = () => { space.current = false; element.classList.remove('pan-ready'); };
    const keyUp = (event: KeyboardEvent) => { if (event.code === 'Space') release(); };
    element.addEventListener('wheel', wheel, { passive: false });
    window.addEventListener('keydown', keyDown);
    window.addEventListener('keyup', keyUp);
    window.addEventListener('blur', release);
    return () => { element.removeEventListener('wheel', wheel); window.removeEventListener('keydown', keyDown); window.removeEventListener('keyup', keyUp); window.removeEventListener('blur', release); };
  }, [updateView]);

  const select = (id: string) => {
    setSelected(id);
    const point = radars.find(r => r.id === id) ?? (mode === 'demo' ? DEMO_GALAXY : undefined);
    if (!point) return;
    updateView(keepInView(view.current, point, size.current, PANEL_WIDTH));
    setAnnouncement(t(`已选择 ${point.name}。`, `Selected ${point.name}.`));
  };
  const closePanel = () => {
    const id = selected;
    setSelected(null);
    if (id) nodes.current.get(id)?.focus({ preventScroll: true });
  };
  useEffect(() => { if (selected) panel.current?.focus({ preventScroll: true }); }, [selected]);

  const pointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || !event.isPrimary || gesture.current) return;
    suppressClick.current = false;
    const target = event.target as Element;
    if (target.closest('[data-ui]')) return;
    const node = target.closest<HTMLButtonElement>('[data-radar]');
    const radar = node ? radars.find(r => r.id === node.dataset.radar) : undefined;
    if (!radar && !space.current) return;
    suppressClick.current = false;
    gesture.current = { pointerId: event.pointerId, start: { x: event.clientX, y: event.clientY }, view: { ...view.current }, radar: space.current ? undefined : radar, moved: false, element: node ?? undefined };
    event.currentTarget.setPointerCapture(event.pointerId);
    event.currentTarget.classList.add('is-dragging');
  };
  const pointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const active = gesture.current;
    if (!active || active.pointerId !== event.pointerId) return;
    const delta = { x: event.clientX - active.start.x, y: event.clientY - active.start.y };
    if (!active.moved && Math.hypot(delta.x, delta.y) < 5) return;
    active.moved = true;
    if (active.radar && active.element) {
      const point = movePoint(active.radar, delta, active.view.zoom);
      active.element.style.left = `${point.x}px`; active.element.style.top = `${point.y}px`;
    } else updateView({ ...active.view, x: active.view.x + delta.x, y: active.view.y + delta.y });
  };
  const pointerEnd = (event: ReactPointerEvent<HTMLDivElement>, cancelled = false) => {
    const active = gesture.current;
    if (!active || active.pointerId !== event.pointerId) return;
    gesture.current = null;
    event.currentTarget.classList.remove('is-dragging');
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    // Pointer capture retargets the synthetic click to the canvas. Consume it
    // after a node gesture so selecting a node cannot immediately deselect it.
    suppressClick.current = !!active.radar || active.moved || cancelled;
    if (active.radar && active.element) {
      if (cancelled) { active.element.style.left = `${active.radar.x}px`; active.element.style.top = `${active.radar.y}px`; }
      else if (active.moved) {
        const point = movePoint(active.radar, { x: event.clientX - active.start.x, y: event.clientY - active.start.y }, active.view.zoom);
        onChange(radars.map(r => r.id === active.radar?.id ? { ...r, ...point } : r));
        setAnnouncement(t(`${active.radar.name} 已移动；布局仅保留在当前会话。`, `${active.radar.name} moved; layout lasts only for this session.`));
      } else if (!space.current) select(active.radar.id);
    } else if (cancelled) updateView(active.view);
  };
  const keyboard = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape' && selected) { event.preventDefault(); closePanel(); return; }
    if (event.target !== event.currentTarget) return;
    const delta: Record<string, Point> = { ArrowLeft: { x: 40, y: 0 }, ArrowRight: { x: -40, y: 0 }, ArrowUp: { x: 0, y: 40 }, ArrowDown: { x: 0, y: -40 } };
    const offset = delta[event.key];
    if (offset) { event.preventDefault(); updateView({ ...view.current, x: view.current.x + offset.x, y: view.current.y + offset.y }); }
    if (event.key.toLowerCase() === 'f') { event.preventDefault(); fit(); }
  };

  return <div ref={root} className={`universe${projecting && !reduced ? ' is-projecting' : ''}`} data-projection={projecting && !reduced ? 'opening' : 'ready'} data-testid="universe" data-mode={mode} tabIndex={0} aria-label={mode === 'demo' ? t('离线星图画布，方向键平移，F 适配视图', 'Offline star map. Arrow keys to pan, F to fit.') : t('真实 Radar 星图，方向键平移，F 适配视图', 'Live Radar map. Arrow keys to pan, F to fit.')} onKeyDown={keyboard} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={event => pointerEnd(event)} onPointerCancel={event => pointerEnd(event, true)} onLostPointerCapture={event => { if (gesture.current) pointerEnd(event, true); }} onClick={event => {
    if (suppressClick.current) { suppressClick.current = false; return; }
    if (event.target === event.currentTarget) setSelected(null);
  }}>
    <div className="map-frame" aria-hidden="true"/>
    <div className="map-heading"><h1 className="eyebrow">{t('宇宙 / 雷达星图', 'UNIVERSE / RADAR MAP')}</h1><p>{t('循着信号，探索你的宇宙。', 'Follow the signals. Explore your universe.')}</p></div>
    <div className="holo-projection" aria-hidden="true"><i/><i/><span/></div>
    {radars.length > 0 ? <div className="projection-field"><div ref={layer} className="world-layer" data-testid="world-layer">
      {mode === 'demo' && <button className={`galaxy-outline${galaxySelected ? ' selected' : ''}`} style={{ left: DEMO_GALAXY.x, top: DEMO_GALAXY.y }} ref={el => { if (el) nodes.current.set(DEMO_GALAXY.id, el); else nodes.current.delete(DEMO_GALAXY.id); }} aria-label={t('查看 AI Research Galaxy 演示结构', 'View AI Research Galaxy demo structure')} onClick={() => { if (!suppressClick.current) select(DEMO_GALAXY.id); }}><span>AI RESEARCH GALAXY<small>{t('演示星系结构', 'DEMO STRUCTURE')}</small></span></button>}
      {radars.map(radar => <button key={radar.id} ref={el => { if (el) nodes.current.set(radar.id, el); else nodes.current.delete(radar.id); }} data-radar={radar.id} className={`radar-node world-${radar.color}${selected === radar.id ? ' selected' : ''}`} style={{ left: radar.x, top: radar.y }} aria-label={mode === 'demo' ? t(`查看 ${radar.name}，${radar.type}，演示信号 ${radar.signals} 条`, `View ${radar.name}, ${radar.type}, ${radar.signals} demo signals`) : t(`查看真实 Radar ${radar.name}，${radar.type}`, `View live Radar ${radar.name}, ${radar.type}`)} onClick={event => { if (event.detail === 0) select(radar.id); }} onKeyDown={event => {
        if (!event.altKey || !event.key.startsWith('Arrow')) return;
        const deltas: Record<string, Point> = { ArrowLeft: { x: -16, y: 0 }, ArrowRight: { x: 16, y: 0 }, ArrowUp: { x: 0, y: -16 }, ArrowDown: { x: 0, y: 16 } };
        const delta = deltas[event.key];
        if (delta) { event.preventDefault(); const point = movePoint(radar, delta, view.current.zoom); onChange(radars.map(r => r.id === radar.id ? { ...r, ...point } : r)); setAnnouncement(t(`${radar.name} 已移动。`, `${radar.name} moved.`)); }
      }}><Planet id={radar.id} color={radar.color}/><span className="radar-name">{radar.name}</span><span className="radar-meta"><i className={radar.status === 'active' ? '' : radar.status}/>{t(typeLabels[radar.type], radar.type.toUpperCase())} · {mode === 'demo' ? t('演示', 'DEMO') : t('真实', 'LIVE')}</span></button>)}
    </div></div> : <div className="empty-state" data-ui><span className="empty-orbit" aria-hidden="true">✧</span><span className="eyebrow">{t('你的宇宙，从这里开始', 'YOUR UNIVERSE STARTS HERE')}</span><h1>{t('一片安静的星空。', 'A quiet sky.')}</h1>{mode === 'demo' ? <><p>{t('当前没有演示 Radar。载入示例，探索星图交互。', 'No demo Radars here. Load examples to explore the star map.')}</p><button className="text-button" onClick={onLoadDemo}>{t('载入演示 Radar', 'Load demo Radars')} <Icon name="arrow"/></button><small>{t('仅加载本地示例，不创建真实 Radar。', 'Loads local examples only; no real Radars are created.')}</small></> : <><p>{t('此账户目前没有 Radar。G2 本轮仅接入读取；创建功能尚未实现。', 'This account has no Radars. This G2 increment is read-only; creation is not implemented yet.')}</p><small>{t('没有加载演示数据，也没有编造统计。', 'No demo data or invented statistics are shown.')}</small></>}</div>}
    {selected && <aside ref={panel} tabIndex={-1} className="detail-panel" data-ui aria-labelledby="detail-title" data-testid="detail-panel">
      <button className="panel-close icon-button" aria-label={t('关闭详情', 'Close details')} onClick={closePanel}><Icon name="close"/></button>
      <span className="eyebrow">{galaxySelected ? t('星系 / 结构', 'GALAXY / STRUCTURE') : t('雷达 / 行星', 'RADAR / WORLD')}</span>
      <h2 id="detail-title">{selectedRadar?.name ?? DEMO_GALAXY.name}</h2><p className="panel-summary">{selectedRadar ? t(selectedRadar.description, descriptions[selectedRadar.id] ?? selectedRadar.description) : t('由两个演示 Radar 构成的星系结构。', 'A Galaxy composed of two demo Radars.')}</p>
      <dl className="detail-facts"><div><dt>{galaxySelected ? t('组内行星', 'Member worlds') : t('Radar 类型', 'Radar type')}</dt><dd>{galaxySelected ? 2 : selectedRadar && t(typeLabels[selectedRadar.type], selectedRadar.type)}</dd></div><div><dt>{mode === 'demo' ? t('演示新信号', 'Demo signals') : t('新信号', 'New signals')}</dt><dd>{galaxySelected ? 9 : selectedRadar?.signals ?? t('未获取', 'Not fetched')}</dd></div><div><dt>{t('数据来源', 'Data source')}</dt><dd>{mode === 'demo' ? t('本地演示', 'LOCAL DEMO') : t('本机 API', 'LOCAL API')}</dd></div></dl>
      {galaxySelected ? <section className="galaxy-members"><h3>{t('星系结构', 'GALAXY STRUCTURE')}</h3>{radars.filter(r => DEMO_GALAXY.members.some(id => id === r.id)).map(radar => <button key={radar.id} onClick={() => select(radar.id)}><span>✧ {radar.name}</span><small>{t(typeLabels[radar.type], radar.type.toUpperCase())} · RADAR</small><Icon name="arrow"/></button>)}</section> : selectedRadar && <div className="radar-detail-art"><Planet id={`detail-${selectedRadar.id}`} color={selectedRadar.color}/><span className="status-label">{t(selectedRadar.status === 'active' ? '活跃' : selectedRadar.status === 'paused' ? '已暂停' : '已归档', selectedRadar.status.toUpperCase())} · {mode === 'demo' ? t('演示', 'DEMO') : t('真实', 'LIVE')}</span></div>}
      <p className="scope-note">{galaxySelected ? t('仅展示分组结构；重命名、解散与持久化尚未接入。', 'Structure preview only. Rename, disband and persistence are not connected.') : mode === 'demo' ? t('示例状态，不代表真实采集任务。可拖动行星；键盘聚焦行星后按 Alt + 方向键移动。', 'Demo status, not a real collection task. Drag planets or focus one and use Alt + arrows.') : t('Radar 来自真实本机 API；CRUD、Source、采集和 Signals 将由后续 lease 接入。', 'Radar data comes from the local API. CRUD, Sources, collection and Signals require later leases.')}<br/>{t('所有布局变动仅保留于当前会话。', 'Layout changes last only for this session.')}</p>
      <button className="text-button panel-fit" onClick={fit}><Icon name="fit"/>{t('适配全部行星', 'Fit all planets')}</button>
    </aside>}
    <div className="canvas-help" data-ui><p>{t('拖动行星 · 滚轮缩放 · 空格 + 拖动平移', 'Drag planets · Scroll to zoom · Space + drag to pan')}</p><p>{t('Tab / Enter 查看 · Alt + 方向键移动行星 · F 适配', 'Tab / Enter to inspect · Alt + arrows to move · F to fit')}</p></div>
    <div className="zoom-controls" data-ui aria-label={t('画布缩放', 'Canvas zoom')}><button aria-label={t('缩小星图', 'Zoom out')} onClick={() => updateView(zoomAt(view.current, { x: size.current.width / 2, y: size.current.height / 2 }, 1 / 1.2))}><Icon name="minus"/></button><output ref={zoomLabel} aria-label={t('当前缩放', 'Current zoom')}>100%</output><button aria-label={t('放大星图', 'Zoom in')} onClick={() => updateView(zoomAt(view.current, { x: size.current.width / 2, y: size.current.height / 2 }, 1.2))}><Icon name="plus"/></button><button aria-label={t('适配全部行星', 'Fit all planets')} title={t('适配全部行星（F）', 'Fit all planets (F)')} onClick={fit}><Icon name="fit"/></button></div>
    <div className="sr-only" role="status" aria-live="polite">{announcement}</div>
  </div>;
}
