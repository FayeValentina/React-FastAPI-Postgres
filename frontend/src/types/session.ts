export interface ScrapeSessionBase {
  session_type: string;
  status: string;
}

export interface ScrapeSessionResponse extends ScrapeSessionBase {
  id: number;
  bot_config_id: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  total_posts_found: number;
  total_comments_found: number;
  quality_comments_count: number;
  published_count: number;
  error_message: string | null;
  error_details: Record<string, unknown> | null;
  config_snapshot: Record<string, unknown> | null;
  created_at: string;
}

export interface ScrapeSessionStats {
  period_days: number;
  total_sessions: number;
  successful_sessions: number;
  success_rate: number;
  total_posts_found: number;
  total_comments_found: number;
  quality_comments_found: number;
  total_published: number;
  avg_duration_seconds: number;
}

export interface ScrapeTriggerResponse {
  session_id: number;
  status: string;
  message: string;
}

// 会话状态类型
export type SessionStatus = 'pending' | 'running' | 'completed' | 'failed';

// 会话类型
export type SessionType = 'manual' | 'scheduled' | 'auto';

// 过滤条件
export interface SessionFilters {
  status?: SessionStatus;
  session_type?: SessionType;
  date_range?: {
    start: string;
    end: string;
  };
  bot_config_id?: number;
}