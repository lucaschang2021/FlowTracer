import { useRef, useState } from 'react';
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
  const pending = useRef(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (pending.current) return;
    const input = { name: name.trim(), goal: goal.trim(), radarType, description: description.trim() || undefined };
    if (!input.name || input.name.length > 120 || !input.goal || input.goal.length > 4000) {
      setError(t('名称需为 1–120 字符，目标需为 1–4000 字符。', 'Name must be 1–120 characters and goal 1–4000 characters.'));
      return;
    }
    pending.current = true;
    setBusy(true);
    setError('');
    try { await onCreate(input); onClose(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : errorMessage(cause).message); }
    finally { pending.current = false; setBusy(false); }
  };
  return <div className="radar-create-scrim" data-ui><section className="radar-create-panel" role="dialog" aria-modal="true" aria-labelledby="radar-create-title">
    <button type="button" className="panel-close icon-button" aria-label={t('关闭新建 Radar', 'Close Create Radar')} disabled={busy} onClick={onClose}>×</button>
    <span className="eyebrow">FLOWTRACER / RADAR</span><h2 id="radar-create-title">{t('新建 Radar', 'Create Radar')}</h2>
    <p>{t('保存成功后才会把真实 Radar 放进星图。', 'The live Radar appears on the map only after the API confirms creation.')}</p>
    <form onSubmit={event => void submit(event)}>
      <label>{t('名称', 'Name')}<input autoFocus value={name} onChange={event => setName(event.target.value)} maxLength={120} required/></label>
      <label>{t('目标', 'Goal')}<textarea value={goal} onChange={event => setGoal(event.target.value)} maxLength={4000} required/></label>
      <label>{t('Radar 类型', 'Radar type')}<select value={radarType} onChange={event => setRadarType(event.target.value as RadarType)}>{choices.map(choice => <option key={choice.value} value={choice.value}>{t(choice.zh, choice.en)}</option>)}</select></label>
      <label>{t('补充说明（可选）', 'Description (optional)')}<textarea value={description} onChange={event => setDescription(event.target.value)}/></label>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <div className="button-row"><button type="button" className="text-button" disabled={busy} onClick={onClose}>{t('取消', 'Cancel')}</button><button type="submit" className="text-button" disabled={busy}>{busy ? t('正在创建…', 'Creating…') : t('创建 Radar', 'Create Radar')}</button></div>
    </form>
  </section></div>;
}
