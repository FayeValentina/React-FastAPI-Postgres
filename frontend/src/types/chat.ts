export interface ConversationResponse {
  id: string;
  title: string;
  summary?: string | null;
  model: string;
  temperature: number;
  system_prompt?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationListItem extends ConversationResponse {
  last_message_preview?: string | null;
}

export interface ConversationListResponse {
  items: ConversationListItem[];
  total: number;
}

export interface MessageResponse {
  id: number;
  message_index: number;
  role: 'user' | 'assistant';
  content: string;
  request_id: string;
  created_at: string;
  updated_at: string;
}

export interface MessageListResponse {
  messages: MessageResponse[];
  next_before_index?: number | null;
  next_before_created_at?: string | null;
}

export interface ConversationMessageCreate {
  content: string;
  model?: string | null;
  temperature?: number | null;
  system_prompt_override?: string | null;
  top_k?: number | null;
}

export interface MessageAcceptedResponse {
  conversation_id: string;
  request_id: string;
  status: 'accepted';
  queued_at: string;
  stream_url: string;
}

export interface ChatCitationPayload {
  key?: string | null;
  chunk_id?: number | null;
  document_id?: number | null;
  chunk_index?: number | null;
  title?: string | null;
  source_ref?: string | null;
  similarity?: number | null;
  score?: number | null;
  bm25_score?: number | null;
  retrieval_source?: string | null;
  content?: string | null;
}

export type ChatEventType = 'delta' | 'citations' | 'done' | 'error' | 'progress';

export interface ChatEventPayload {
  type: ChatEventType;
  conversation_id: string;
  request_id: string;
  timestamp: string;
  content?: string;
  citations?: ChatCitationPayload[];
  stage?: string;
  message?: string;
  detail?: string;
  token_usage?: {
    prompt?: number | null;
    completion?: number | null;
    total?: number | null;
  };
}
