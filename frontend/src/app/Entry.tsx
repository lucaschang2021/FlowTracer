import { useEffect, useRef, useState } from 'react';
import { LanguageSelect, usePreferences } from './Preferences';
import { Icon } from './Icon';
import emblemUrl from '../assets/intro-emblem.webp';
import { animateInk } from './ink';
import { OriginalBackdrop } from './OriginalBackdrop';

export function CelestialBackground() {
  return <div className="celestial-background" aria-hidden="true"><div className="nebula-cloud"/><div className="stellar-flow"/><svg className="celestial-grid" viewBox="0 0 1000 1000">
    <g fill="none" stroke="currentColor" strokeWidth=".5">{[90, 170, 255, 340, 420, 485].map(r => <circle key={r} cx="500" cy="500" r={r}/>)}
      {Array.from({ length: 12 }, (_, i) => <path key={i} d="M500 15V985" transform={`rotate(${i * 15} 500 500)`}/>)}
      <circle cx="500" cy="500" r="468" strokeDasharray="1 7"/><circle cx="500" cy="500" r="350" strokeDasharray="22 100 3 70" strokeWidth="2"/>
      <path d="M80 500Q500 120 920 500Q500 880 80 500M500 80Q120 500 500 920Q880 500 500 80"/>
    </g></svg><div className="cosmic-vignette"/></div>;
}

function IntroArtwork({ reduced }: { reduced: boolean }) {
  const word = useRef<HTMLCanvasElement>(null);
  const emblem = useRef<HTMLCanvasElement>(null);
  useEffect(() => { if (word.current && emblem.current) return animateInk(word.current, emblem.current, emblemUrl, reduced); }, [reduced]);
  return <div className="intro-art"><canvas ref={word} width="2024" height="248" className="intro-wordmark" role="img" aria-label="FLOWTRACER">FLOWTRACER</canvas><canvas ref={emblem} width="512" height="512" className="intro-emblem" aria-hidden="true"/></div>;
}

export function Entry({ stage, onContinue, onBack }: { stage: 'intro' | 'login'; onContinue: () => void; onBack: () => void }) {
  const { t, quiet } = usePreferences();
  const [systemQuiet, setSystemQuiet] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
  const entry = useRef<HTMLDivElement>(null);
  useEffect(() => { const media = matchMedia('(prefers-reduced-motion: reduce)'); const change = () => setSystemQuiet(media.matches); media.addEventListener('change', change); return () => media.removeEventListener('change', change); }, []);
  useEffect(() => { entry.current?.focus(); }, [stage]);
  return <main className={`entry-screen entry-${stage}`} ref={entry} tabIndex={-1} aria-label={t(stage === 'intro' ? '启动画面' : '演示登录', stage === 'intro' ? 'Startup screen' : 'Demo sign-in')} onKeyDown={event => {
    if (stage !== 'intro' || event.target !== event.currentTarget || event.repeat || event.ctrlKey || event.altKey || event.metaKey || ['Tab', 'Shift', 'Control', 'Alt', 'Meta', 'Escape'].includes(event.key)) return;
    event.preventDefault(); onContinue();
  }}>
    <OriginalBackdrop reduced={quiet || systemQuiet}/>
    <header className="entry-toolbar"><span className="eyebrow">FLOWTRACER <span className="entry-version">/ 0.1 ALPHA</span></span><LanguageSelect/></header>
    {stage === 'intro' ? <><IntroArtwork reduced={quiet || systemQuiet}/><button className="intro-start" onClick={onContinue}>{t('按任意键开始', 'PRESS ANY KEY TO START')}</button><button className="entry-skip" onClick={onContinue}>{t('跳过动画', 'Skip intro')} <Icon name="arrow"/></button></> :
      <section className="demo-login" aria-labelledby="login-heading"><span className="eyebrow">{t('你的情报宇宙', 'YOUR INTELLIGENCE UNIVERSE')}</span><h1 id="login-heading">{t('欢迎回来。', 'Welcome back.')}</h1><p>{t('从信息中，找到值得关注的信号。', 'Find the signals worth paying attention to.')}</p>
        <div className="demo-identity"><span className="identity-mark" aria-hidden="true">F</span><div><strong>{t('探索者', 'Explorer')}</strong><small>{t('本地演示身份', 'Local demo identity')}</small></div><span className="demo-badge">{t('演示', 'DEMO')}</span></div>
        <p className="demo-login-note">{t('当前仅预览登录流程，无需账号或密码；不会进行真实登录或连接后端。', 'Preview the sign-in flow without an account or password. No real authentication or backend connection.')}</p>
        <button autoFocus className="login-enter" onClick={onContinue}>{t('进入演示星图', 'Enter demo universe')}<Icon name="arrow"/></button><button className="login-back" onClick={onBack}>{t('返回启动画面', 'Back to startup')}</button>
      </section>}
    <footer className="entry-footer"><span>{t('离线演示 · 未连接后端', 'OFFLINE DEMO · NO BACKEND CONNECTION')}</span><span>{t('启动 / 登录 / 星图', 'INTRO / SIGN-IN / UNIVERSE')}</span></footer>
  </main>;
}
