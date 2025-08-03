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