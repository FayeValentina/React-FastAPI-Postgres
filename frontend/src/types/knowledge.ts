// Knowledge base types matching backend Pydantic schemas

export interface KnowledgeDocumentBase {
  source_type?: string | null;
  source_ref?: string | null;
  title?: string | null;
  language?: string | null;
  mime?: string | null;
  checksum?: string | null;
  meta?: Record<string, unknown> | null;
  tags?: string[] | null;
  created_by?: string | null;
}

export type KnowledgeDocumentCreate = KnowledgeDocumentBase;

export type KnowledgeDocumentUpdate = KnowledgeDocumentBase;

export interface KnowledgeDocumentRead extends KnowledgeDocumentBase {
  id: number;
  created_at: string; // ISO datetime
}

export interface KnowledgeDocumentIngestRequest {
  content: string;
  overwrite: boolean;
}

export interface KnowledgeIngestResult {
  document_id: number;
  chunks: number;
}

export interface KnowledgeChunkRead {
  id: number;
  document_id?: number | null;
  chunk_index?: number | null;
  content: string;
  created_at: string; // ISO datetime
}

export interface KnowledgeSearchRequest {
  query: string;
  top_k?: number; // default 5 on backend
}
