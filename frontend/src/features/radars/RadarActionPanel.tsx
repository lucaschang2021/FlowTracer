import { useEffect, useRef, useState } from 'react';
import { errorMessage } from '../../api/desktop';
import { usePreferences } from '../../app/Preferences';

export type RadarLifecycleAction = 'pause' | 'resume' | 'delete';

export function RadarActionPanel({ radarId, radarName, action, onAction, onClose }: { radarId: string; radarName: string; action: RadarLifecycleAction; onAction: (id: string, action: RadarLifecycleAction) => Promise<void>; onClose: (completed?: boolean) => void }) {
  const { t } = usePreferences();
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const panel = useRef<HTMLElement>(null); const cancel = useRef<HTMLButtonElement>(null); const lastFocused = useRef<HTMLElement | null>(null);
  const pending = useRef(false); const busyRef = useRef(false); const mounted = useRef(true); const closeRef = useRef(onClose); closeRef.current = onClose;
  const focusable = () => Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])') ?? []);
  useEffect(() => {
    mounted.current = true; cancel.current?.focus();
    const dialog = panel.current;
    const focusGuard = (event: FocusEvent) => {
      if (!dialog) return;
      if (event.target instanceof HTMLElement && dialog.contains(event.target)) { lastFocused.current = event.target; return; }
      const targets = focusable(); (lastFocused.current && targets.includes(lastFocused.current) ? lastFocused.current : targets[0])?.focus();
    };
    document.addEventListener('focusin', focusGuard);
    return () => { mounted.current = false; document.removeEventListener('focusin', focusGuard); };
  }, []);
  const keyboard = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape') { if (busyRef.current) return; event.preventDefault(); closeRef.current(); return; }
    if (event.key !== 'Tab') return; const targets = focusable(); if (!targets.length) { event.preventDefault(); return; }
    const first = targets[0], last = targets[targets.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  const confirm = async () => {
    if (pending.current) return;
    pending.current = true; busyRef.current = true; setBusy(true); setError('');
    try { await onAction(radarId, action); if (mounted.current) onClose(true); }
    catch (cause) { if (mounted.current) setError(cause instanceof Error ? cause.message : errorMessage(cause).message); }
    finally { pending.current = false; busyRef.current = false; if (mounted.current) setBusy(false); }
  };
  const labels = action === 'pause'
    ? { title: t('暂停 Radar', 'Pause Radar'), body: t(`确认暂停“${radarName}”？后端确认后星图状态才会更新。`, `Pause “${radarName}”? The map changes only after backend confirmation.`), confirm: t('确认暂停', 'Confirm pause'), pending: t('正在暂停…', 'Pausing…') }
    : action === 'resume'
      ? { title: t('恢复 Radar', 'Resume Radar'), body: t(`确认恢复“${radarName}”？后端确认后星图状态才会更新。`, `Resume “${radarName}”? The map changes only after backend confirmation.`), confirm: t('确认恢复', 'Confirm resume'), pending: t('正在恢复…', 'Resuming…') }
      : { title: t('移除 Radar', 'Remove Radar'), body: t(`确认移除“${radarName}”？这会请求服务端软删除；记录可能仍按服务端保留策略保存。`, `Remove “${radarName}”? This requests a server-side soft delete; records may remain under server retention policy.`), confirm: t(`确认移除“${radarName}”`, `Confirm removal of “${radarName}”`), pending: t('正在移除…', 'Removing…') };
  return <div className="radar-create-scrim" data-ui><section ref={panel} className="radar-create-panel" role="dialog" aria-modal="true" aria-labelledby="radar-action-title" aria-describedby="radar-action-description" onKeyDown={keyboard}>
    <span className="eyebrow">FLOWTRACER / RADAR</span><h2 id="radar-action-title">{labels.title}</h2><p id="radar-action-description">{labels.body}</p>
    {error && <p className="auth-error" role="alert">{error}</p>}
    <div className="button-row"><button ref={cancel} type="button" className="text-button" disabled={busy} onClick={() => onClose()}>{t('取消', 'Cancel')}</button><button type="button" className="text-button" disabled={busy} onClick={() => void confirm()}>{busy ? labels.pending : labels.confirm}</button></div>
  </section></div>;
}
