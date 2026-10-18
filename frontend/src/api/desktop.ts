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
export type RadarCreateInput = { name: string; goal: string; radarType: RadarType; description?: string };
export type RadarUpdateInput = { name: string; goal: string; radarType: RadarType; description: string | null; notificationThreshold: number };
export type SourceType = 'rss' | 'url' | 'api';
export type SourceRecord = { id: string; name: string; sourceType: SourceType; url: string; normalizedUrl: string; pollIntervalMinutes: number; status: ResourceStatus };
export type SourcePage = { items: SourceRecord[]; page: number; pageSize: number; total: number };
export type SourceCreateInput = { name: string; sourceType: 'rss' | 'url'; url: string; pollIntervalMinutes: number };
export type CollectionRunStatus = 'queued' | 'running' | 'succeeded' | 'partial' | 'failed';
export type CollectionQueued = { runId: string; status: CollectionRunStatus };
export type CollectionRun = { id: string; sourceId: string; status: CollectionRunStatus; fetchedCount: number; createdCount: number; duplicateCount: number; failedCount: number; errorCode?: string | null; errorMessage?: string | null };
export type AnalysisStatus = 'pending' | 'running' | 'completed' | 'failed';
export type Recommendation = 'must_read' | 'read' | 'monitor' | 'archive';
export type IntelligenceQuery = { page: number; pageSize: number; radarId?: string | null; status?: AnalysisStatus | null; recommendation?: Recommendation | null; category?: string | null; minScore?: number | null };
export type IntelligenceItem = { id:string;documentId:string;radarId:string;title:string;canonicalUrl:string;summary?:string|null;category?:string|null;relevance?:number|null;importance?:number|null;novelty?:number|null;impact?:number|null;radarScore?:number|null;recommendation?:Recommendation|null;reason?:string|null;status:AnalysisStatus;errorCode?:string|null;errorMessage?:string|null;pipelineVersion:string;promptVersion:string;provider?:string|null;model?:string|null;bookmarked:boolean;createdAt:string;updatedAt:string };
export type IntelligencePage = { items:IntelligenceItem[];page:number;pageSize:number;total:number };
export type IntelligenceDetail = IntelligenceItem & { content:string;author?:string|null;language?:string|null;wordCount:number };

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
  createRadar: (input: RadarCreateInput) => call<RadarRecord>('radars_create', { input }),
  radar: (radarId: string) => call<RadarRecord>('radars_get', { radarId }),
  updateRadar: (radarId: string, input: RadarUpdateInput) => call<RadarRecord>('radars_update', { radarId, input }),
  pauseRadar: (radarId: string) => call<RadarRecord>('radars_pause', { radarId }),
  resumeRadar: (radarId: string) => call<RadarRecord>('radars_resume', { radarId }),
  deleteRadar: (radarId: string) => call<void>('radars_delete', { radarId }),
  sources: (page = 1, pageSize = 20) => call<SourcePage>('sources_list', { page, pageSize }),
  radarSources: (radarId: string, page = 1, pageSize = 20) => call<SourcePage>('radar_sources_list', { radarId, page, pageSize }),
  createSource: (input: SourceCreateInput) => call<SourceRecord>('sources_create', { input }),
  bindSource: (radarId: string, sourceId: string) => call<void>('radar_sources_bind', { radarId, sourceId }),
  unbindSource: (radarId: string, sourceId: string) => call<void>('radar_sources_unbind', { radarId, sourceId }),
  collectSource: (sourceId: string, idempotencyKey: string) => call<CollectionQueued>('sources_collect', { sourceId, idempotencyKey }),
  collectionRun: (runId: string, sourceId: string) => call<CollectionRun>('collection_runs_get', { runId, sourceId }),
  intelligence: (input:IntelligenceQuery) => call<IntelligencePage>('intelligence_list', { input }),
  intelligenceDetail: (analysisId:string, radarId:string) => call<IntelligenceDetail>('intelligence_get', { analysisId, radarId }),
};

export const errorMessage = (error: unknown) => normalizeError(error);
