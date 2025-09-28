# `tasks.py` (endpoints) 文档

此文件是整个后台任务和系统监控模块的API入口点。它定义了大量的HTTP端点，用于管理任务配置、控制调度、查询执行历史以及监控系统健康状态。所有端点都依赖于 `get_current_superuser`，意味着只有管理员才能访问这些功能。

## Router 配置
- **`prefix`**: `/tasks`
- **`tags`**: `["tasks"]`
- **依赖**: `[Depends(get_current_superuser)]` (在 `main.py` 中应用)

## 端点分组与功能

### 一、任务配置管理 (`/configs`)
这组端点用于任务模板的增删改查。

- `POST /configs`: 创建一个新的任务配置模板。
- `GET /configs`: 分页、排序、筛选任务配置列表。
- `GET /configs/{config_id}`: 获取单个配置的详细信息，可选包含其执行统计。
- `PATCH /configs/{config_id}`: 部分更新一个已存在的任务配置。
- `DELETE /configs/{config_id}`: 删除一个任务配置，并会自动注销其下所有正在运行的调度实例。

### 二、调度实例管理 (`/schedules` & `/configs/.../schedules`)
这组端点用于管理从任务配置模板创建的具体运行实例。

- `POST /configs/{config_id}/schedules`: 从一个配置模板创建一个新的、独立的调度实例。
- `DELETE /schedules/{schedule_id}`: 完全注销并删除一个调度实例。
- `POST /schedules/{schedule_id}/pause`: 暂停一个调度实例。
- `POST /schedules/{schedule_id}/resume`: 恢复一个已暂停的调度实例。
- `GET /schedules`: 获取 `TaskIQ` 中所有当前正在调度的任务列表。
- `GET /schedules/{schedule_id}`: 获取单个调度实例的完整聚合信息（状态、元数据、历史）。
- `GET /schedules/summary`: 获取调度器的全局状态摘要（如活跃、暂停的实例总数）。

### 三、执行历史管理 (`/executions`)
这组端点用于查询和管理任务的历史执行记录。

- `GET /executions/configs/{config_id}`: 获取某个特定配置下的所有执行记录。
- `GET /executions/recent`: 获取最近N小时内的所有执行记录。
- `GET /executions/failed`: 获取最近N天内所有失败的执行记录。
- `GET /executions/stats`: 获取全局或单个配置的执行统计数据（成功率、平均时长等）。
- `GET /executions/{task_id}`: 通过 `TaskIQ` 的唯一任务ID查询单次执行的详细记录。
- `DELETE /executions/cleanup`: 清理超过指定天数的旧执行记录。

### 四、系统监控 (`/system`)
这组端点用于提供关于整个应用健康状况和配置的元信息。

- `GET /system/status`: 获取系统各组件（数据库、Redis等）状态和核心指标的快照。
- `GET /system/health`: 对各组件进行实时健康检查。
- `GET /system/enums`: 返回系统中使用的所有枚举值，供前端动态构建UI。
- `GET /system/task-info`: **核心端点**。返回所有已注册任务的完整元数据，包括它们的参数、类型、默认值以及用于前端渲染的UI提示。这是实现“后端驱动UI”的关键。
- `GET /system/dashboard`: 为前端仪表盘提供聚合后的高级统计数据。

### 五、管理员维护 (`/system/cleanup` & `/system/orphans`)
这组端点提供了手动触发的系统维护功能。

- `GET /system/orphans`: 列出那些在调度器中存在，但其父配置已被删除的“孤儿”调度实例。
- `POST /system/cleanup/orphans`: 清理所有找到的孤儿实例。
- `POST /system/cleanup/legacy`: 清理因版本迭代而遗留下来的、使用旧格式的Redis键或调度ID。

## 缓存策略
- **`@cache`**: 多个 `GET` 端点（如 `list_task_configs`, `get_system_status`）都使用了 `@cache` 装饰器，将它们的返回结果缓存起来，以减少数据库负载和提高响应速度。
- **`@invalidate`**: 所有会改变系统状态的 `POST`, `PATCH`, `DELETE` 端点都使用了 `@invalidate` 装饰器。当这些操作成功后，它们会自动清除相关的缓存（如 `CacheTags.TASK_CONFIGS`, `CacheTags.SYSTEM_STATUS`），确保后续的 `GET` 请求能获取到最新的数据。
