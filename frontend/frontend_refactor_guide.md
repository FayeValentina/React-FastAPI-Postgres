我发现后端的任务管理API已经非常丰富，但前端还没有充分利用这些功能。让我为您制定一个全面的重构方案。

# 任务管理前端重构方案

## 一、后端API端点分析

经过分析 `backend/app/api/v1/routes/task_routes.py`，我发现以下关键端点：

### 现有端点清单
1. **GET /tasks** - 获取系统状态
2. **GET /tasks/schedules** - 获取调度任务列表（支持增强模式）
3. **GET /tasks/active-tasks** - 获取活跃的Celery任务
4. **GET /tasks/jobs/{job_id}** - 获取任务详细信息
5. **POST /tasks/cleanup** - 清理任务管理
6. **GET /tasks/tasks/{task_id}** - 获取Celery任务状态
7. **POST /tasks/tasks/{task_id}/cancel** - 取消任务
8. **GET /tasks/events** - 获取调度事件
9. **GET /tasks/executions** - 获取执行历史和统计
10. **POST /tasks/schedules/batch-update** - 批量更新调度
11. **GET /tasks/analysis** - 获取系统分析报告

## 二、重构方案

### 1. 文件结构调整

```
frontend/src/
├── pages/
│   ├── TaskManagementPage.tsx (重构)
│   └── SystemMonitoringPage.tsx (新增)
├── components/
│   ├── Layout/
│   │   └── ManagementLayout.tsx (更新)
│   └── Tasks/
│       ├── index.ts (更新)
│       ├── TaskCard.tsx (重构)
│       ├── TaskDetailDialog.tsx (新增)
│       ├── SystemHealthPanel.tsx (重构)
│       ├── TaskHistoryDialog.tsx (废弃，功能合并到TaskDetailDialog)
│       ├── ActiveTasksPanel.tsx (新增)
│       ├── ScheduleEventsPanel.tsx (新增)
│       ├── ExecutionStatsPanel.tsx (新增)
│       ├── SystemAnalysisPanel.tsx (新增)
│       ├── CleanupManagerDialog.tsx (新增)
│       └── BatchUpdateDialog.tsx (新增)
└── types/
    └── task.ts (扩展)
```

### 2. 组件功能规划

#### 2.1 TaskManagementPage.tsx (重构)
**改动要点：**
- 使用新的 `/tasks/schedules?enhanced=true` 端点获取更丰富的任务信息
- 集成批量操作功能
- 添加清理任务管理界面
- 改进任务卡片展示，显示执行摘要

#### 2.2 SystemMonitoringPage.tsx (新增)
**功能：**
- 显示系统整体健康状态
- 展示活跃的Celery任务
- 显示执行统计图表
- 系统分析和优化建议
- 事件日志查看器

#### 2.3 组件详细设计

##### TaskDetailDialog.tsx (新增)
替代原有的 TaskHistoryDialog，提供更全面的任务详情：
- 基本任务信息
- 执行摘要统计
- 最近事件列表
- 执行历史图表
- 任务配置查看/编辑

##### ActiveTasksPanel.tsx (新增)
- 实时显示正在执行的Celery任务
- 支持取消/终止操作
- 显示任务进度和队列信息

##### ScheduleEventsPanel.tsx (新增)
- 显示调度事件时间线
- 支持按任务ID筛选
- 错误事件高亮显示

##### ExecutionStatsPanel.tsx (新增)
- 执行统计图表（成功率、平均耗时等）
- 支持时间范围选择
- 对比不同任务的性能

##### SystemAnalysisPanel.tsx (新增)
- 调度分布分析
- 队列状态监控
- 优化建议展示

##### CleanupManagerDialog.tsx (新增)
- 手动触发清理
- 管理清理调度（创建/更新/删除）
- 查看清理历史

##### BatchUpdateDialog.tsx (新增)
- 批量选择任务
- 批量更新调度配置
- 预览更改效果

### 3. ManagementLayout.tsx 更新

```typescript
const menuSections = [
  {
    title: '爬虫管理',
    items: [
      // ... 保持不变
    ],
  },
  {
    title: '系统管理',
    items: [
      {
        text: '任务调度',
        icon: <TaskIcon />,
        path: '/management/tasks',
        implemented: true,
      },
      {
        text: '系统监控',
        icon: <DashboardIcon />,
        path: '/management/monitoring',
        implemented: true, // 改为true
      },
      {
        text: '系统设置',
        icon: <SettingsIcon />,
        path: '/management/settings',
        implemented: false,
      },
    ],
  },
];
```

### 4. 类型定义扩展 (task.ts)

```typescript
// 新增类型定义
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

export interface ActiveTask {
  worker: string;
  task_id: string;
  name: string;
  args: any[];
  kwargs: Record<string, any>;
  time_start: string;
}

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

export interface CleanupConfig {
  action: 'trigger' | 'create' | 'update' | 'remove';
  days_old?: number;
  schedule_id?: string;
  cron_expression?: string;
}
```

### 5. API调用更新

在 `api-store.ts` 中，所有API调用保持现有模式，但需要适配新端点：

```typescript
// 示例：获取增强的调度列表
const schedulesUrl = '/v1/tasks/schedules?enhanced=true';

// 示例：获取任务详情
const jobDetailUrl = `/v1/tasks/jobs/${jobId}?hours=72&events_limit=20`;

// 示例：批量更新
await postData('/v1/tasks/schedules/batch-update', updates);
```

## 三、实施步骤

### 第一阶段：基础重构
1. 更新类型定义文件 `task.ts`
2. 重构 `TaskManagementPage.tsx`，使用增强的API
3. 创建 `TaskDetailDialog.tsx` 替代原有的历史对话框

### 第二阶段：新增监控页面
1. 创建 `SystemMonitoringPage.tsx`
2. 实现 `ActiveTasksPanel.tsx`
3. 实现 `ScheduleEventsPanel.tsx`
4. 实现 `ExecutionStatsPanel.tsx`

### 第三阶段：高级功能
1. 实现 `SystemAnalysisPanel.tsx`
2. 创建 `CleanupManagerDialog.tsx`
3. 创建 `BatchUpdateDialog.tsx`
4. 更新 `ManagementLayout.tsx`

### 第四阶段：优化和完善
1. 添加实时刷新功能（WebSocket或轮询）
2. 添加数据可视化图表
3. 优化用户体验和交互

## 四、关键功能亮点

### 1. 任务调度页面增强
- **执行摘要卡片**：直接在任务卡片上显示成功率、平均耗时等关键指标
- **批量操作**：支持多选任务进行批量暂停、恢复、删除
- **快速筛选**：按状态、类型、性能指标筛选任务

### 2. 系统监控页面
- **实时监控面板**：显示当前执行的任务、队列长度、系统负载
- **性能趋势图**：展示任务执行趋势、成功率变化
- **告警提示**：失败任务、队列堵塞等异常情况提醒

### 3. 清理管理
- **一键清理**：快速清理旧数据
- **定时清理配置**：可视化配置清理计划
- **清理历史**：查看历史清理记录和效果

### 4. 系统分析
- **调度优化建议**：基于任务分布提供优化建议
- **性能瓶颈分析**：识别执行缓慢或频繁失败的任务
- **资源使用报告**：展示系统资源使用情况

## 五、技术实现要点

1. **状态管理**：继续使用现有的 `api-store` 模式
2. **实时更新**：对于监控页面，使用轮询机制（每5-10秒）更新数据
3. **性能优化**：使用 React.memo 和 useMemo 优化渲染性能
4. **错误处理**：统一的错误提示和重试机制
5. **图表库**：建议使用 recharts 或 Chart.js 展示统计数据

## 六、预期效果

完成重构后，任务管理系统将具备：
- **全面的任务管理**：从调度到执行的完整生命周期管理
- **实时系统监控**：及时发现和处理系统问题
- **数据驱动决策**：基于统计分析优化任务调度
- **便捷的批量操作**：提高管理效率
- **直观的可视化**：通过图表快速了解系统状态