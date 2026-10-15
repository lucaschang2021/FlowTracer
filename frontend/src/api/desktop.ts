import { invoke } from '@tauri-apps/api/core';

export type BridgeError = {
  kind: string;
  message: string;
  status?: number;
  code?: string;
  requestId?: string;
};

export type BridgeStatus = { available: boolean; origin?: string; error?: BridgeError };
export type User = { id: string; email: string; displayName: string; isActive: boolean };
export type Session = { authenticated: boolean; user?: User };
export type RadarType = 'academic' | 'business' | 'technology' | 'market' | 'policy' | 'competitive' | 'custom' | 'opportunity';
export type ResourceStatus = 'active' | 'paused' | 'archived';
export type RadarRecord = {
  id: string;
  name: string;
  description?: string | null;
  goal: string;
  radarType: RadarType;
  categories: string[];
  keywords: string[];
  status: ResourceStatus;
  notificationThreshold: number;
};
export type RadarPage = { items: RadarRecord[]; page: number; pageSize: number; total: number };

export const isDesktopBridge = () => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

function normalizeError(value: unknown): BridgeError {
  if (value && typeof value === 'object') {
    const candidate = value as Partial<BridgeError>;
    if (typeof candidate.kind === 'string' && typeof candidate.message === 'string') {
      return { kind: candidate.kind, message: candidate.message, status: candidate.status, code: candidate.code, requestId: candidate.requestId };
    }
  }
  return { kind: 'bridge_failure', message: 'The desktop bridge request failed.' };
}

async function call<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  if (!isDesktopBridge()) throw { kind: 'bridge_unavailable', message: 'Desktop bridge is unavailable in browser preview.' } satisfies BridgeError;
  try { return await invoke<T>(command, args); }
  catch (error) { throw normalizeError(error); }
}

export const desktopApi = {
  status: () => call<BridgeStatus>('bridge_status'),
  ready: () => call<{ ready: boolean }>('health_ready'),
  login: (email: string, password: string) => call<Session>('auth_login', { input: { email, password } }),
  register: (email: string, password: string, displayName: string) => call<Session>('auth_register', { input: { email, password, displayName } }),
  refresh: () => call<Session>('auth_refresh'),
  logout: () => call<void>('auth_logout'),
  me: () => call<User>('users_me'),
  radars: () => call<RadarPage>('radars_list'),
};

export const errorMessage = (error: unknown) => normalizeError(error);
