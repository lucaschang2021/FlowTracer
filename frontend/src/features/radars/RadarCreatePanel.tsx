import { useEffect, useRef, useState } from 'react';
import { errorMessage } from '../../api/desktop';
import type { RadarCreateInput, RadarType } from '../../api/desktop';
import { usePreferences } from '../../app/Preferences';

const choices: { value: RadarType; zh: string; en: string }[] = [
  { value: 'academic', zh: '学术', en: 'Academic' },
  { value: 'business', zh: '商业', en: 'Business' },
  { value: 'technology', zh: '技术', en: 'Technology' },
  { value: 'market', zh: '市场', en: 'Market' },
  { value: 'policy', zh: '政策', en: 'Policy' },
  { value: 'competitive', zh: '竞争', en: 'Competitive' },
  { value: 'custom', zh: '自定义', en: 'Custom' },
  { value: 'opportunity', zh: '机会', en: 'Opportunity' },
];

export function RadarCreatePanel({ onCreate, onClose }: { onCreate: (input: RadarCreateInput) => Promise<void>; onClose: () => void }) {
  const { t } = usePreferences();
  const [name, setName] = useState('');
  const [goal, setGoal] = useState('');
  const [description, setDescription] = useState('');
  const [radarType, setRadarType] = useState<RadarType>('custom');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const panel = useRef<HTMLElement>(null);
  const nameInput = useRef<HTMLInputElement>(null);
  const lastFocused = useRef<HTMLElement | null>(null);
  const pending = useRef(false);
  const busyRef = useRef(false);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const focusable = () => Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [href], [tabindex]:not([tabindex="-1"])') ?? []);
  useEffect(() => {
    const dialog = panel.current;
    if (!dialog) return;
    nameInput.current?.focus();
    const focusGuard = (event: FocusEvent) => {
      if (event.target instanceof HTMLElement && dialog.contains(event.target)) { lastFocused.current = event.target; return; }
      const targets = focusable();
      const target = lastFocused.current && targets.includes(lastFocused.current) ? lastFocused.current : targets[0];
      target?.focus();
    };
    document.addEventListener('focusin', focusGuard);
    return () => document.removeEventListener('focusin', focusGuard);
  }, []);
  const keyboard = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape') {
      if (busyRef.current) return;
      event.preventDefault();
      closeRef.current();
      return;
    }
    if (event.key !== 'Tab') return;
    const targets = focusable();
    if (!targets.length) { event.preventDefault(); return; }
    const first = targets[0], last = targets[targets.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (pending.current) return;
    const input = { name: name.trim(), goal: goal.trim(), radarType, description: description.trim() || undefined };
    if (!input.name || input.name.length > 120 || !input.goal || input.goal.length > 4000) {
      setError(t('名称需为 1–120 字符，目标需为 1–4000 字符。', 'Name must be 1–120 characters and goal 1–4000 characters.'));
      return;
    }
    pending.current = true;
    busyRef.current = true;
    setBusy(true);
    setError('');
    try { await onCreate(input); onClose(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : errorMessage(cause).message); }
    finally { pending.current = false; busyRef.current = false; setBusy(false); }
  };
  return <div className="radar-create-scrim" data-ui><section ref={panel} className="radar-create-panel" role="dialog" aria-modal="true" aria-labelledby="radar-create-title" onKeyDown={keyboard}>
    <button type="button" className="panel-close icon-button" aria-label={t('关闭新建 Radar', 'Close Create Radar')} disabled={busy} onClick={onClose}>×</button>
    <span className="eyebrow">FLOWTRACER / RADAR</span><h2 id="radar-create-title">{t('新建 Radar', 'Create Radar')}</h2>
    <p>{t('保存成功后才会把真实 Radar 放进星图。', 'The live Radar appears on the map only after the API confirms creation.')}</p>
    <form onSubmit={event => void submit(event)}>
      <label>{t('名称', 'Name')}<input ref={nameInput} value={name} onChange={event => setName(event.target.value)} maxLength={120} required/></label>
      <label>{t('目标', 'Goal')}<textarea value={goal} onChange={event => setGoal(event.target.value)} maxLength={4000} required/></label>
      <label>{t('Radar 类型', 'Radar type')}<select value={radarType} onChange={event => setRadarType(event.target.value as RadarType)}>{choices.map(choice => <option key={choice.value} value={choice.value}>{t(choice.zh, choice.en)}</option>)}</select></label>
      <label>{t('补充说明（可选）', 'Description (optional)')}<textarea value={description} onChange={event => setDescription(event.target.value)}/></label>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <div className="button-row"><button type="button" className="text-button" disabled={busy} onClick={onClose}>{t('取消', 'Cancel')}</button><button type="submit" className="text-button" disabled={busy}>{busy ? t('正在创建…', 'Creating…') : t('创建 Radar', 'Create Radar')}</button></div>
    </form>
  </section></div>;
}
