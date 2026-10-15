import { useState } from 'react';
import type { FormEvent } from 'react';
import type { BridgeError } from '../../api/desktop';
import { usePreferences } from '../../app/Preferences';
import { Icon } from '../../app/Icon';

type Credentials = { email: string; password: string; displayName?: string };
type Props = {
  available: boolean;
  origin?: string;
  ready: boolean | null;
  busy: boolean;
  error?: BridgeError;
  onAuthenticate: (kind: 'login' | 'register', credentials: Credentials) => Promise<void>;
  onDemo: () => void;
};

export function AuthPanel({ available, origin, ready, busy, error, onAuthenticate, onDemo }: Props) {
  const { t } = usePreferences();
  const [kind, setKind] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const secret = password;
    setPassword('');
    await onAuthenticate(kind, { email: email.trim(), password: secret, displayName: displayName.trim() || undefined });
  };
  return <section className="demo-login auth-panel" aria-labelledby="login-heading">
    <span className="eyebrow">{t('真实账户 / 本机 API', 'REAL ACCOUNT / LOCAL API')}</span>
    <h1 id="login-heading">{t('欢迎回来。', 'Welcome back.')}</h1>
    <p>{t('默认连接本机 FlowTracer。凭据只交给原生桥。', 'Connect to local FlowTracer by default. Credentials go only to the native bridge.')}</p>
    <div className="auth-tabs" role="tablist" aria-label={t('账户操作', 'Account action')}>
      <button type="button" role="tab" aria-selected={kind === 'login'} onClick={() => setKind('login')}>{t('登录', 'Sign in')}</button>
      <button type="button" role="tab" aria-selected={kind === 'register'} onClick={() => setKind('register')}>{t('注册', 'Register')}</button>
    </div>
    <form onSubmit={submit} className="auth-form">
      {kind === 'register' && <label><span>{t('显示名称', 'Display name')}</span><input autoComplete="name" required maxLength={80} value={displayName} onChange={event => setDisplayName(event.target.value)}/></label>}
      <label><span>{t('邮箱', 'Email')}</span><input type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)}/></label>
      <label><span>{t('密码', 'Password')}</span><input type="password" autoComplete={kind === 'login' ? 'current-password' : 'new-password'} required minLength={10} maxLength={128} value={password} onChange={event => setPassword(event.target.value)}/></label>
      <button className="login-enter" disabled={!available || busy}>{busy ? t('连接中…', 'Connecting…') : kind === 'login' ? t('登录并载入星图', 'Sign in and load map') : t('创建账户并载入', 'Create account and load')}<Icon name="arrow"/></button>
    </form>
    <div className="connection-state" role="status">
      <span className={`status-dot ${ready === true ? 'ready' : ready === false ? 'down' : ''}`}/>
      {available ? ready === true ? t('本机 API 已就绪', 'Local API ready') : ready === false ? t('本机 API 未就绪', 'Local API not ready') : t('正在检查本机 API', 'Checking local API') : t('普通网页预览无法使用桌面桥', 'Desktop bridge unavailable in browser preview')}
      {origin && <small>{origin}</small>}
    </div>
    {error && <p className="auth-error" role="alert">{error.message}{error.requestId ? <small>Request ID: {error.requestId}</small> : null}</p>}
    <div className="demo-divider"><span>{t('或进入隔离演示', 'OR USE ISOLATED DEMO')}</span></div>
    <button type="button" className="demo-enter" onClick={onDemo}>{t('进入演示星图', 'Enter demo universe')}<Icon name="arrow"/></button>
    <p className="demo-login-note">{t('演示模式使用本地示例并持续标识；连接失败不会自动切换。', 'Demo uses labeled local fixtures. Connection failures never switch modes automatically.')}</p>
  </section>;
}
