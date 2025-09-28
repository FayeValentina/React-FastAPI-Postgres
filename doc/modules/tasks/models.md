# `models.py` (tasks) 文档

此文件定义了与后台任务系统相关的SQLAlchemy ORM模型，主要包括 `TaskConfig`（任务配置）和 `TaskExecution`（任务执行历史）。

## `TaskConfig(Base)` 模型

这个类是任务系统的核心，它代表了一个可配置、可调度的任务**模板**，映射到 `task_configs` 表。

### `@register_sqlalchemy_model`
- **装饰器**: 将 `TaskConfig` 模型注册到缓存序列化器中，使其ORM实例可以被缓存。

### 主要字段
- **`id: Mapped[int]`**: 主键。
- **`name: Mapped[str]`**: 任务的可读名称，用于在UI中展示。
- **`task_type: Mapped[str]`**: 任务的类型标识符（例如 `"reddit_scraper"`）。这个字符串与 `@task` 装饰器中定义的 `name` 相对应，用于将配置与具体的任务执行函数关联起来。
- **`scheduler_type: Mapped[SchedulerType]`**: 调度类型，是一个枚举（`CRON`, `DATE`, `MANUAL`），决定了任务是按CRON表达式、在特定日期还是只能手动触发。
- **`parameters: Mapped[Dict]`**: 一个JSONB字段，以键值对的形式存储了执行该任务所需的**业务参数**（例如，对于Reddit抓取任务，这里可能存储 `{"subreddit": "python", "limit": 100}`）。使用JSONB使得模型可以灵活地为不同类型的任务存储不同的参数。
- **`schedule_config: Mapped[Dict]`**: 一个JSONB字段，存储与**调度行为**相关的参数。例如，对于CRON任务，这里可能存储 `{"cron_expression": "0 0 * * *"}`。
- **`max_retries`, `timeout_seconds`, `priority`**: 任务执行的控制参数，分别定义了最大重试次数、超时时间（秒）和执行优先级。

### 关联关系
- **`task_executions: Mapped[List["TaskExecution"]]`**: 定义了与 `TaskExecution` 模型的一对多关系。当一个 `TaskConfig` 被删除时，所有与之关联的执行历史记录也会被级联删除。

### 属性与方法
- **`is_scheduled`**: 一个方便的计算属性，用于判断该任务是否为需要自动调度的任务。
- **`get_parameter(...)` / `update_parameters(...)`**: 用于安全地获取或更新 `parameters` 字典中的值。

## `TaskExecution(Base)` 模型

这个类用于记录每一次任务执行的历史，映射到 `task_executions` 表。

### `@register_sqlalchemy_model`
- **装饰器**: 同样将 `TaskExecution` 模型注册到缓存序列化器。

### 主要字段
- **`id: Mapped[int]`**: 主键。
- **`config_id: Mapped[Optional[int]]`**: 外键，关联到 `task_configs` 表。它指明了这次执行是由哪个任务配置（模板）发起的。
    - `ondelete="SET NULL"`: 一个重要的设置。如果一个 `TaskConfig` 被删除了，与之关联的执行历史记录的 `config_id` 字段会被设置为 `NULL`，但历史记录本身**不会被删除**。这确保了即使任务配置被删，我们依然可以保留其执行历史以供审计。
- **`task_id: Mapped[str]`**: 由 `TaskIQ` 在任务执行时生成的唯一ID（通常是UUID）。这个ID是每次具体执行的唯一标识。
- **`is_success: Mapped[bool]`**: 标志位，表示本次执行是成功还是失败。
- **`started_at`, `completed_at`, `duration_seconds`**: 记录了任务的开始时间、结束时间以及总耗时，用于性能监控。
- **`result: Mapped[Optional[Dict]]`**: 一个JSONB字段，用于存储任务成功执行后的返回值（如果任务有返回值的话）。
- **`error_message`, `error_traceback`**: 如果任务执行失败，这两个字段分别用于存储简短的错误信息和完整的Python堆栈跟踪，非常便于调试。

### 关联关系
- **`task_config: Mapped["TaskConfig"]`**: 定义了与 `TaskConfig` 模型的多对一关系，方便从执行历史记录直接访问其所属的任务配置信息。
