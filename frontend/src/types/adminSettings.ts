export type AdminSettingKey =
  | 'RAG_TOP_K'
  | 'RAG_STRATEGY_ENABLED'
  | 'RAG_MIN_SIM'
  | 'RAG_MMR_LAMBDA'
  | 'RAG_PER_DOC_LIMIT'
  | 'RAG_OVERSAMPLE'
  | 'RAG_MAX_CANDIDATES'
  | 'RAG_RERANK_ENABLED'
  | 'RAG_RERANK_CANDIDATES'
  | 'RAG_RERANK_SCORE_THRESHOLD'
  | 'RAG_CONTEXT_TOKEN_BUDGET'
  | 'RAG_CONTEXT_MAX_EVIDENCE'
  | 'RAG_IVFFLAT_PROBES'
  | 'RAG_USE_LINGUA'
  | 'RAG_STRATEGY_LLM_CLASSIFIER_CONFIDENCE_THRESHOLD'
  | 'BM25_TOP_K'
  | 'BM25_WEIGHT'
  | 'BM25_MIN_RANK';

export type AdminSettingValue = number | string | boolean | null;

export interface AdminSettingsResponse {
  defaults: Record<string, AdminSettingValue>;
  overrides: Record<string, AdminSettingValue>;
  effective: Record<string, AdminSettingValue>;
  updated_at: string | null;
  redis_status: 'ok' | 'unavailable';
}

export type AdminSettingsUpdate = Partial<Record<AdminSettingKey, number | boolean>>;
