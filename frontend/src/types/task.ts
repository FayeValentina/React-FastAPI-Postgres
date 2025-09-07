// ============== 任务配置相关类型 ==============
export interface TaskConfig {
  id: number;
  name: string;
  description?: string;
  task_type: string;
  scheduler_type: 'manual' | 'cron' | 'date';
  parameters: Record<string, unknown>;
  schedule_config: Record<string, unknown>;
  max_retries: number;
  timeout_seconds?: number;
  priority: number;
  created_at: string;
  updated_at?: string;
  // 来自Redis的调度状态
  schedule_status?: string;
  is_scheduled?: boolean;
  status_consistent?: boolean;
  recent_history?: ScheduleHistoryEvent[];
}

export interface TaskConfigCreate {
  name: string;
  description?: string;
  task_type: string;
  scheduler_type: 'manual' | 'cron' | 'date';
  parameters: Record<string, unknown>;
  schedule_config: Record<string, unknown>;
  max_retries?: number;
  timeout_seconds?: number;
  priority?: number;
}

export type TaskConfigUpdate = Partial<Omit<TaskConfigCreate, 'task_type' | 'scheduler_type'>>;

// ============== 调度相关类型 ==============
export interface ScheduleInfo {
  schedule_id: string;
  task_name: string;
  config_id?: number;
  schedule: string;
  labels: Record<string, string>;
  next_run?: string;
}

export interface ScheduleHistoryEvent {
  event: string;
  timestamp: string;
  success?: boolean;
  task_name?: string;
  error?: string;
}

export interface ScheduleSummary {
  total_schedules: number;
  active_schedules: number;
  paused_schedules: number;
  inactive_schedules: number;
  error_schedules: number;
  last_updated: string;
}

export interface ConfigSchedulesResponse {
  config_id: number;
  schedule_ids: string[];
}

export interface ScheduleOperationResponse {
  success: boolean;
  message: string;
  schedule_id: string;
}

// ============== 执行相关类型 ==============
export interface TaskExecution {
  id: number;
  task_id: string;
  config_id: number;
  config_name?: string;
  task_type?: string;
  is_success: boolean;
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  result?: Record<string, unknown>;
  error_message?: string;
  error_traceback?: string;
  created_at: string;
}

export interface ExecutionStats {
  period_days: number;
  total_executions: number;
  success_count: number;
  failed_count: number;
  success_rate: number;
  failure_rate: number;
  avg_duration_seconds: number;
  type_breakdown: Record<string, number>;
  timestamp: string;
}

// ============== 系统监控相关类型 ==============
export interface SystemStatus {
  system_time: string;
  scheduler_status: string;
  database_status: string;
  redis_status: string;
  config_stats: {
    total_configs: number;
    by_type: Record<string, number>;
  };
  schedule_summary: ScheduleSummary;
  execution_stats: ExecutionStats;
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  components: Record<string, {
    status: string;
    message: string;
  }>;
  error?: string;
}

export interface SystemEnums {
  scheduler_types: string[];
  schedule_actions: string[];
  task_types: string[];
  schedule_statuses: string[];
}

export interface SystemDashboard {
  dashboard: {
    config_stats: {
      total_configs: number;
      by_type: Record<string, number>;
    };
    schedule_summary: ScheduleSummary;
    execution_stats: {
      last_7_days: ExecutionStats;
      last_30_days: ExecutionStats;
    };
    generated_at: string;
  };
}
