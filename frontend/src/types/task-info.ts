// Task-info types returned by /v1/tasks/system/task-info

export interface TypeInfo {
  type: string;
  args?: TypeInfo[];
}

export interface UIMetaInfo {
  exclude_from_ui?: boolean;
  ui_hint?: string;
  choices?: unknown[];
  label?: string;
  description?: string;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
  pattern?: string;
  example?: unknown;
}

export interface TaskParameterInfo {
  name: string;
  type: string;
  type_info: TypeInfo;
  default?: string | null;
  required: boolean;
  kind: string;
  ui?: UIMetaInfo;
}

export interface TaskInfo {
  name: string;
  worker_name: string;
  queue: string;
  doc: string;
  parameters: TaskParameterInfo[];
  has_parameters: boolean;
}

export interface TaskInfoResponse {
  tasks: TaskInfo[];
  total_count: number;
  generated_at: string;
}
