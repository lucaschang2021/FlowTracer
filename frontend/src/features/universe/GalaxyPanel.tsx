import { useEffect, useRef, useState } from 'react';
import { Icon } from '../../app/Icon';
import { usePreferences } from '../../app/Preferences';
import type { Galaxy } from './layout';
import type { UniverseRadar } from './model';

type Props = { galaxy: Galaxy; radars: UniverseRadar[]; onClose: () => void; onRename: (name: string) => void; onMember: (id: string) => void; onDisband: () => void };
export function GalaxyPanel({ galaxy, radars, onClose, onRename, onMember, onDisband }: Props) {
  const { t } = usePreferences(); const [editing, setEditing] = useState(false); const [name, setName] = useState(galaxy.name); const panel = useRef<HTMLElement>(null);
  const members = radars.filter(radar => galaxy.members.includes(radar.id));
  useEffect(() => { panel.current?.focus({ preventScroll: true }); }, []);
  return <aside ref={panel} tabIndex={-1} className="detail-panel galaxy-panel" data-ui data-testid="galaxy-panel" aria-label={t(`Galaxy ${galaxy.name}`, `Galaxy ${galaxy.name}`)}>
    <button className="panel-close icon-button" aria-label={t('关闭 Galaxy', 'Close Galaxy')} onClick={onClose}><Icon name="close"/></button><span className="eyebrow">{t('星系 / 本地空间', 'GALAXY / LOCAL SPACE')}</span>
    {editing ? <form className="galaxy-rename" onSubmit={event => { event.preventDefault(); const next = name.trim(); if (next) { onRename(next); setEditing(false); } }}><label htmlFor="galaxy-name">{t('Galaxy 名称', 'Galaxy name')}</label><input id="galaxy-name" autoFocus maxLength={64} value={name} onChange={event => setName(event.target.value)}/><div className="button-row"><button type="submit" className="text-button">{t('保存名称', 'Save name')}</button><button type="button" className="text-button" onClick={() => { setName(galaxy.name); setEditing(false); }}>{t('取消', 'Cancel')}</button></div></form> : <><h2 id="galaxy-title">{galaxy.name}</h2><button className="text-button" onClick={() => setEditing(true)}>{t('重命名 Galaxy', 'Rename Galaxy')}</button></>}
    <p className="panel-summary">{t(`包含 ${galaxy.members.length} 个 Radar；当前载入 ${members.length} 个。`, `${galaxy.members.length} Radars; ${members.length} currently loaded.`)}</p>
    <section className="galaxy-members"><h3>{t('成员导航', 'MEMBER NAVIGATION')}</h3>{members.map(radar => <button key={radar.id} onClick={() => onMember(radar.id)}><span>✧ {radar.name}</span><small>RADAR</small><Icon name="arrow"/></button>)}</section>
    {members.length < galaxy.members.length && <p className="scope-note">{t('未分页载入的成员引用会保留，不会被误删。', 'References not loaded on this page are retained, not deleted.')}</p>}
    <button className="text-button danger-button" onClick={onDisband}>{t('解散 Galaxy（保留 Radar）', 'Disband Galaxy (keep Radars)')}</button>
  </aside>;
}
