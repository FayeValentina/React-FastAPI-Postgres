export type AdminSettingKey =
  | 'RAG_TOP_K'
  | 'RAG_STRATEGY_ENABLED'
  | 'RAG_STRATEGY_LLM_CLASSIFIER_ENABLED'
  | 'RAG_MIN_SIM'
  | 'RAG_MMR_LAMBDA'
  | 'RAG_PER_DOC_LIMIT'
  | 'RAG_OVERSAMPLE'
  | 'RAG_MAX_CANDIDATES'
  | 'RAG_RERANK_ENABLED'
  | 'RAG_RERANK_CANDIDATES'
  | 'RAG_RERANK_SCORE_THRESHOLD'
  | 'RAG_RERANK_MAX_BATCH'
  | 'RAG_SAME_LANG_BONUS'
  | 'RAG_CONTEXT_TOKEN_BUDGET'
  | 'RAG_CONTEXT_MAX_EVIDENCE'
  | 'RAG_CHUNK_TARGET_TOKENS_EN'
  | 'RAG_CHUNK_TARGET_TOKENS_CJK'
  | 'RAG_CHUNK_TARGET_TOKENS_DEFAULT'
  | 'RAG_CHUNK_OVERLAP_RATIO'
  | 'RAG_CODE_CHUNK_MAX_LINES'
  | 'RAG_CODE_CHUNK_OVERLAP_LINES'
  | 'RAG_IVFFLAT_PROBES'
  | 'RAG_USE_LINGUA'
  | 'RAG_STRATEGY_LLM_CLASSIFIER_CONFIDENCE_THRESHOLD';

export type AdminSettingValue = number | string | boolean | null;

export interface AdminSettingsResponse {
  defaults: Record<string, AdminSettingValue>;
  overrides: Record<string, AdminSettingValue>;
  effective: Record<string, AdminSettingValue>;
  updated_at: string | null;
  redis_status: 'ok' | 'unavailable';
}

export type AdminSettingsUpdate = Partial<Record<AdminSettingKey, number | boolean>>;
