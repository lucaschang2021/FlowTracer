import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
export type Locale = 'zh-CN' | 'en';
export const PREFERENCE_KEY = 'flowtracer.demo.preferences.v1';
export function readPreferences(storage: Pick<Storage, 'getItem'>): { locale: Locale; quiet: boolean } {
  try { const value = JSON.parse(storage.getItem(PREFERENCE_KEY) ?? '{}'); return { locale: value?.locale === 'en' ? 'en' : 'zh-CN', quiet: value?.quiet === true }; }
  catch { return { locale: 'zh-CN', quiet: false }; }
}
type Preferences = { locale: Locale; quiet: boolean; setLocale: (locale: Locale) => void; setQuiet: (quiet: boolean) => void; t: (zh: string, en: string) => string };
const Context = createContext<Preferences | null>(null);
export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState(() => { try { return readPreferences(window.localStorage); } catch { return { locale: 'zh-CN' as Locale, quiet: false }; } });
  const { locale, quiet } = preferences;
  useEffect(() => { document.documentElement.lang = locale; try { window.localStorage.setItem(PREFERENCE_KEY, JSON.stringify(preferences)); } catch { /* Optional storage in restricted WebViews. */ } }, [preferences, locale]);
  const t = useCallback((zh: string, en: string) => locale === 'en' ? en : zh, [locale]);
  return <Context.Provider value={{ locale, quiet, t, setLocale: value => setPreferences(p => ({ ...p, locale: value })), setQuiet: value => setPreferences(p => ({ ...p, quiet: value })) }}>{children}</Context.Provider>;
}
export function usePreferences() { const value = useContext(Context); if (!value) throw new Error('PreferencesProvider is required'); return value; }
export function LanguageSelect() {
  const { locale, setLocale, t } = usePreferences();
  return <label className="language-select"><span>{t('语言', 'Language')}</span><select value={locale} onChange={event => setLocale(event.target.value as Locale)}><option value="zh-CN">简体中文</option><option value="en">English</option></select></label>;
}
