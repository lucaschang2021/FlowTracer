import { useEffect, useRef, useState } from 'react';
import { LanguageSelect, usePreferences } from './Preferences';
import { Icon } from './Icon';
import emblemUrl from '../assets/intro-emblem.webp';
import { animateInk } from './ink';
import { AuthPanel } from '../features/auth/AuthPanel';
import type { BridgeError } from '../api/desktop';

function IntroArtwork({ reduced }: { reduced: boolean }) {
  const word = useRef<HTMLCanvasElement>(null);
  const emblem = useRef<HTMLCanvasElement>(null);
  useEffect(() => { if (word.current && emblem.current) return animateInk(word.current, emblem.current, emblemUrl, reduced); }, [reduced]);
  return <div className="intro-art"><canvas ref={word} width="2024" height="248" className="intro-wordmark" role="img" aria-label="FLOWTRACER">FLOWTRACER</canvas><canvas ref={emblem} width="512" height="512" className="intro-emblem" aria-hidden="true"/></div>;
}

type Credentials = { email: string; password: string; displayName?: string };
type EntryProps = {
  stage: 'intro' | 'login';
  onContinue: () => void;
  onBack: () => void;
  onDemo: () => void;
  onAuthenticate: (kind: 'login' | 'register', credentials: Credentials) => Promise<void>;
  bridge: { available: boolean; origin?: string; ready: boolean | null; busy: boolean; error?: BridgeError };
};

export function Entry({ stage, onContinue, onBack, onDemo, onAuthenticate, bridge }: EntryProps) {
  const { t, quiet } = usePreferences();
  const [systemQuiet, setSystemQuiet] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
  const entry = useRef<HTMLDivElement>(null);
  useEffect(() => { const media = matchMedia('(prefers-reduced-motion: reduce)'); const change = () => setSystemQuiet(media.matches); media.addEventListener('change', change); return () => media.removeEventListener('change', change); }, []);
  useEffect(() => { entry.current?.focus(); }, [stage]);
  return <main className={`entry-screen entry-${stage}`} ref={entry} tabIndex={-1} aria-label={t(stage === 'intro' ? '启动画面' : '账户登录', stage === 'intro' ? 'Startup screen' : 'Account sign-in')} onKeyDown={event => {
    if (stage !== 'intro' || event.target !== event.currentTarget || event.repeat || event.ctrlKey || event.altKey || event.metaKey || ['Tab', 'Shift', 'Control', 'Alt', 'Meta', 'Escape'].includes(event.key)) return;
    event.preventDefault(); onContinue();
  }}>
    <header className="entry-toolbar"><span className="eyebrow">FLOWTRACER <span className="entry-version">/ 0.1 ALPHA</span></span><LanguageSelect/></header>
    {stage === 'intro' ? <><IntroArtwork reduced={quiet || systemQuiet}/><button className="intro-start" onClick={onContinue}>{t('按任意键开始', 'PRESS ANY KEY TO START')}</button><button className="entry-skip" onClick={onContinue}>{t('跳过动画', 'Skip intro')} <Icon name="arrow"/></button></> : <><AuthPanel {...bridge} onAuthenticate={onAuthenticate} onDemo={onDemo}/><button className="login-back" onClick={onBack}>{t('返回启动画面', 'Back to startup')}</button></>}
    <footer className="entry-footer"><span>{stage === 'intro' ? t('启动画布', 'STARTUP CANVAS') : bridge.available ? t('真实模式 · 本机 API', 'LIVE MODE · LOCAL API') : t('网页预览 · 桌面桥不可用', 'WEB PREVIEW · DESKTOP BRIDGE UNAVAILABLE')}</span><span>{t('启动 / 登录 / 星图', 'INTRO / SIGN-IN / UNIVERSE')}</span></footer>
  </main>;
}
