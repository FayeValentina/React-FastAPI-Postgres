# `service.py` (tasks) 文档

此文件定义了 `TaskService`，它是任务系统的核心业务逻辑层。这个服务作为一个高级外观（Facade），整合了底层的仓库（`crud_task_config`, `crud_task_execution`）和调度服务（`scheduler_service`），为API路由提供了一个统一、简洁的接口来管理任务的全生命周期。

## `TaskService` 类

### 设计理念
- **业务逻辑封装**: 将创建、更新、删除任务配置等操作的完整业务流程封装在此。例如，在删除一个任务配置时，它不仅会删除数据库记录，还会负责调用调度服务来取消所有与该配置关联的正在运行的调度实例。
- **数据聚合与丰富**: 在返回数据给API层之前，它会聚合来自不同数据源的信息。例如，在获取任务配置列表时，它会为每个配置调用 `_aggregate_config_status` 方法，从调度服务（Redis）中获取其实时的运行状态，并将这个状态附加到从数据库中读取的配置信息上，从而为前端提供一个完整的视图。
- **异常处理**: 作为直接服务于API路由的层，它将底层服务或仓库抛出的各种异常（数据库错误、调度错误等）捕获，并统一转换为FastAPI的 `HTTPException`，确保API总能返回格式正确的HTTP错误响应。

### 主要方法分类

#### 任务配置管理
- **`create_task_config(...)`**: 创建一个新的任务配置，并根据 `auto_schedule` 参数决定是否立即为其创建一个调度实例。
- **`list_task_configs(...)`**: 调用仓库的 `get_by_query` 方法获取分页和排序后的配置列表，并为每个配置聚合其当前的调度状态。
- **`get_task_config(...)`**: 获取单个任务配置的详细信息，并可选地包含其历史执行统计。
- **`update_task_config(...)`**: 更新一个任务配置。
- **`delete_task_config(...)`**: 删除一个任务配置，并确保先注销其所有关联的调度实例。

#### 调度实例管理
- **`create_schedule_instance(...)`**: 为一个已存在的任务配置手动创建一个新的运行实例。
- **`unregister_schedule(...)`**: 完全注销并删除一个调度实例。
- **`pause_schedule(...)` / `resume_schedule(...)`**: 暂停或恢复一个调度实例。
- **`get_all_schedules()`**: 获取 `TaskIQ` 中所有当前已调度的任务列表。
- **`get_schedule_info(...)`**: 获取单个调度实例的完整聚合信息（状态、元数据、历史）。

#### 任务执行历史与统计
- **`get_config_executions(...)`**: 获取某个配置下的执行历史列表。
- **`get_recent_executions(...)` / `get_failed_executions(...)`**: 获取最近的或失败的执行历史。
- **`get_execution_stats(...)`**: 获取全局或单个配置的执行统计数据。
- **`cleanup_execution_history(...)`**: 清理旧的执行历史记录。

#### 系统监控与维护
- **`get_system_status(...)` / `get_system_health(...)`**: 提供关于系统各组件（数据库、Redis、调度器）健康状况的聚合信息。
- **`get_system_enums(...)`**: 向前端提供系统中使用的所有枚举值。
- **`get_task_info()`**: 从任务注册表 (`tr`) 中获取所有已注册任务的详细元信息（包括用于动态生成UI的参数信息）。
- **`get_system_dashboard(...)`**: 为前端仪表盘提供聚合后的高级统计数据。
- **`list_orphans()` / `cleanup_orphans()` / `cleanup_legacy()`**: 提供一系列管理和维护工具，用于清理无效的或遗留的调度数据。

## 全局实例
- `task_service = TaskService()`: 创建了一个全局唯一的服务实例，供所有与任务相关的API端点调用。
