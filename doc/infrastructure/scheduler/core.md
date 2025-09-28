# `core.py` (scheduler) 文档

此文件定义了 `SchedulerCoreService`，它是与 `TaskIQ` 调度器进行直接交互的核心服务。它的职责被严格限定在任务的注册、注销和查询上，而不关心任务的状态管理。

## `SchedulerCoreService` 类

### 职责划分
- **负责**: 
    - 管理 `TaskIQ` 的调度器实例 (`schedule_source`)。
    - 向 `TaskIQ` 添加（注册）新的定时任务。
    - 从 `TaskIQ` 删除（注销）现有的定时任务。
    - 查询当前所有已调度的任务信息。
- **不负责**: 
    - 任务执行历史的记录。
    - 任务成功/失败的状态跟踪。
    - 任务执行的统计数据。（这些由 `HistoryService` 等其他服务处理）

### 主要方法

#### `initialize(self)` / `shutdown(self)`
- **功能**: 分别用于在应用启动和关闭时，安全地启动和关闭 `TaskIQ` 的 `schedule_source`。这确保了调度器与应用的生命周期同步。

#### `register_task(self, config: TaskConfig, ...)`
- **功能**: 将一个数据库中的任务配置 (`TaskConfig` ORM模型) 转换为一个 `TaskIQ` 的 `ScheduledTask` 对象，并将其添加到调度器中。
- **流程**:
    1.  根据 `config.task_type` 从任务注册表 (`task_registry_decorators`) 中找到对应的可执行任务函数。
    2.  调用 `_build_scheduled_task` 方法来构建一个 `ScheduledTask` 对象。
    3.  调用 `self.schedule_source.add_schedule()` 将任务提交给 `TaskIQ`。
- **返回值**: 返回成功注册后由 `TaskIQ` 分配或由内部生成的唯一 `schedule_id`。

#### `unregister_task(self, schedule_id: str)`
- **功能**: 根据 `schedule_id` 从 `TaskIQ` 调度器中删除一个已注册的任务。

#### `get_all_schedules(self)`
- **功能**: 从 `TaskIQ` 获取所有当前已调度的任务列表，并将其转换为一个包含关键信息（如 `schedule_id`, `task_name`, `next_run` 等）的字典列表。

#### `is_schedule_present(self, schedule_id: str)`
- **功能**: 一个便捷方法，用于检查具有特定 `schedule_id` 的任务当前是否存在于调度器中。

### 内部辅助方法

#### `_build_scheduled_task(self, config, ...)`
- **功能**: 这是任务注册逻辑的核心。它负责将数据库中的 `TaskConfig` 模型转换为 `TaskIQ` 能理解的 `ScheduledTask` 对象。
- **关键步骤**:
    1.  **参数校验**: 检查 `TaskConfig` 中定义的 `parameters` 是否满足任务函数所声明的所有必需参数。
    2.  **生成 `schedule_id`**: 调用 `redis_keys.scheduler.build_schedule_id` 生成一个全局唯一的、包含配置ID和UUID的 `schedule_id`。
    3.  **构建 `labels`**: 创建一个包含元数据（如 `config_id`, `task_type`）的 `labels` 字典。这些标签会被 `TaskIQ` 传递给任务执行器，用于上下文识别和日志记录。
    4.  **获取调度参数**: 调用 `_get_schedule_params` 将数据库中的调度配置（如 `{"cron_expression": "0 0 * * *"}`）转换为 `TaskIQ` 需要的参数（如 `{"cron": "0 0 * * *"}`）。
    5.  **实例化 `ScheduledTask`**: 将所有准备好的参数（任务名、参数、标签、调度规则等）传递给 `ScheduledTask` 的构造函数。

#### `_get_schedule_params(self, ...)`
- **功能**: 根据调度类型（`CRON` 或 `DATE`）和存储在数据库中的JSON配置，生成 `TaskIQ` 所需的 `cron` 或 `time` 参数。

#### `_get_next_run_time(self, scheduled_task)`
- **功能**: 根据 `ScheduledTask` 对象中的 `cron` 或 `time` 属性，计算并返回下一次任务预计的运行时间。它使用了 `croniter` 库来处理CRON表达式的计算。
