// 任务状态枚举
export type TaskStatus = 
  | 'running'
  | 'scheduled'
  | 'paused'
  | 'stopped'
  | 'failed'
  | 'idle'
  | 'timeout'
  | 'misfired';

// 执行状态枚举
export type ExecutionStatus = 'success' | 'failed' | 'timeout' | 'running';

// 任务信息
export interface JobInfo {
  id: string;
  name: string;
  trigger: string;
  next_run_time: string | null;
  pending: boolean;
  status: TaskStatus;
  
  // 详细信息（可选）
  func?: string;
  args?: any[];
  kwargs?: Record<string, any>;
  executor?: string;
  max_instances?: number;
  misfire_grace_time?: number;
  coalesce?: boolean;
}

// 任务执行历史
export interface TaskExecutionResponse {
  id: number;
  job_id: string;
  job_name: string;
  status: ExecutionStatus;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  result: Record<string, any> | null;
  error_message: string | null;
  created_at: string;
}

// 任务统计
export interface JobStatsResponse {
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  success_rate: number;
  avg_duration_seconds: number;
}

// 创建任务请求
export interface JobCreateRequest {
  func: string;
  name: string;
  trigger: string;
  trigger_args: Record<string, any>;
  args?: any[];
  kwargs?: Record<string, any>;
  max_retries?: number;
  timeout?: number;
}

// 更新任务调度
export interface JobScheduleUpdate {
  trigger?: string;
  trigger_args?: Record<string, any>;
}

// 系统信息
export interface SystemInfo {
  stats?: {
    total_jobs: number;
    active_jobs: number;
    paused_jobs: number;
    task_types: Record<string, number>;
    scheduler_running: boolean;
  };
  health?: {
    total_jobs: number;
    healthy_jobs: number;
    unhealthy_jobs: Array<{
      job_id: string;
      name: string;
      status: TaskStatus;
      next_run_time: string | null;
    }>;
    scheduler_running: boolean;
    health_score: number;
  };
}

// 任务过滤条件
export interface TaskFilters {
  status?: TaskStatus;
  search?: string;
}

// ============== 增强类型定义 ==============

// 增强的调度任务信息
export interface EnhancedSchedule {
  schedule_id: string;
  name: string;
  next_run_time: string | null;
  trigger: string;
  pending: boolean;
  config: Record<string, any>;
  computed_status?: TaskStatus;
  execution_summary?: JobExecutionSummary;
}

// 任务执行摘要
export interface JobExecutionSummary {
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  success_rate: number;
  avg_duration: number;
  last_run: string | null;
  last_status: string | null;
  last_error: string | null;
}

// 调度事件
export interface ScheduleEvent {
  id: number;
  job_id: string;
  job_name: string;
  event_type: string;
  result: Record<string, any> | null;
  error_message: string | null;
  error_traceback: string | null;
  created_at: string;
}

// 活跃的worker任务
export interface ActiveTask {
  worker: string;
  task_id: string;
  name: string;
  args: any[];
  kwargs: Record<string, any>;
  time_start: string;
}

// 系统分析报告
export interface SystemAnalysis {
  schedule_distribution: {
    total_bot_schedules: number;
    time_distribution: Record<string, number>;
    peak_hours: number[];
    max_tasks_per_hour: number;
    optimization_needed: boolean;
    recommendations: string[];
  };
  config_stats: Record<string, any>;
  queue_status: Record<string, any>;
}

// 清理配置
export interface CleanupConfig {
  action: 'trigger' | 'create' | 'update' | 'remove';
  days_old?: number;
  schedule_id?: string;
  cron_expression?: string;
}

// 批量更新配置
export interface BatchUpdateConfig {
  schedule_ids: string[];
  updates: Record<string, any>;
}

// 任务详情响应
export interface JobDetailResponse {
  job_info: JobInfo;
  execution_summary: JobExecutionSummary;
  recent_events: ScheduleEvent[];
  execution_history: TaskExecutionResponse[];
}

// 执行统计响应
export interface ExecutionStatsResponse {
  time_series: Array<{
    date: string;
    successful_runs: number;
    failed_runs: number;
    total_runs: number;
    avg_duration: number;
  }>;
  summary: {
    total_executions: number;
    successful_executions: number;
    failed_executions: number;
    overall_success_rate: number;
    avg_execution_time: number;
    most_active_jobs: Array<{
      job_id: string;
      job_name: string;
      execution_count: number;
    }>;
  };
}