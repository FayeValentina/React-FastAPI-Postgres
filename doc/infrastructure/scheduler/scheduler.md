# `scheduler.py` 文档

此文件定义了 `SchedulerService`，这是一个统一的、高级的调度服务。它作为应用层与底层调度功能之间的主要接口，整合了 `SchedulerCoreService`（负责与TaskIQ交互）和 `ScheduleHistoryRedisService`（负责状态管理），并提供了完整的任务生命周期管理功能。

## `SchedulerService` 类

### 架构
- **组合模式**: 它不自己实现底层逻辑，而是通过组合（Composition）的方式，将职责委托给两个专门的子服务：
    - `self.core = SchedulerCoreService()`: 负责与 `TaskIQ` 调度器直接通信，处理任务的注册和注销。
    - `self.state = ScheduleHistoryRedisService()`: 负责在Redis中记录和管理任务的状态、元数据、历史事件和索引。
- **`schedule_id` 为核心**: 所有的运行时操作（暂停、恢复、删除）都以 `schedule_id` 作为唯一标识符，而不是数据库中的 `config_id`。这允许同一个任务配置（模板）可以有多个独立的运行实例。

### 核心生命周期方法

#### `register_task(self, config: TaskConfig)`
- **功能**: 从一个任务配置模板 (`TaskConfig`) 创建并注册一个新的调度实例。
- **流程**:
    1.  调用 `self.core.register_task()` 在 `TaskIQ` 中创建一个新的调度任务，并获取返回的 `schedule_id`。
    2.  如果成功，接着调用 `self.state` 的多个方法，在Redis中记录该 `schedule_id` 的状态（`ACTIVE`）、元数据（配置快照）、历史事件（`task_registered`），并将其加入到 `config_id` 的索引中。

#### `unregister(self, schedule_id: str)`
- **功能**: 完全地、永久地删除一个调度实例。
- **流程**:
    1.  从Redis中读取元数据以获取 `config_id`。
    2.  调用 `self.core.unregister_task()` 从 `TaskIQ` 中删除调度。
    3.  调用 `self.state.remove_schedule_from_index()` 从配置索引中移除该实例。
    4.  调用 `self.state.purge_schedule_artifacts()` 从Redis中彻底清除与该 `schedule_id` 相关的所有数据（状态、元数据、历史）。

#### `pause(self, schedule_id: str)`
- **功能**: 暂停一个正在运行的调度实例。
- **实现**: 这实际上是一个“伪暂停”。它调用 `self.core.unregister_task()` 将任务从 `TaskIQ` 的调度队列中移除，然后调用 `self.state.set_schedule_status()` 将其在Redis中的状态更新为 `PAUSED`。任务的所有元数据和历史记录都被保留。

#### `resume(self, schedule_id: str)`
- **功能**: 恢复一个已暂停的调度实例。
- **流程**:
    1.  从Redis中读取该 `schedule_id` 的元数据，找到其原始的 `config_id`。
    2.  使用 `config_id` 从数据库中重新加载最新的 `TaskConfig` 模板。
    3.  调用 `self.core.register_task()` 并**强制传入原始的 `schedule_id`**，将任务重新注册到 `TaskIQ` 中。
    4.  将Redis中的状态更新回 `ACTIVE`。

### 查询方法
- `get_schedule_full_info(schedule_id)`: 获取单个调度实例的完整信息（状态、元数据、历史等）。
- `get_all_schedules()`: 获取 `TaskIQ` 中所有当前已调度的任务列表。
- `get_scheduler_summary()`: 获取一个包含调度器整体统计信息的摘要。
- `list_config_schedules(config_id)`: 根据配置模板ID，列出其下所有正在运行的调度实例的 `schedule_id`。

### 维护与清理方法

#### `find_orphan_schedule_ids()` / `cleanup_orphan_schedules()`
- **功能**: 用于系统维护。它能找出那些在 `TaskIQ` 中存在，但其对应的 `TaskConfig` 模板已在数据库中被删除的“孤儿”调度实例，并能将它们彻底清理掉。

#### `cleanup_legacy_artifacts()`
- **功能**: 用于清理在代码重构前遗留下来的、使用旧命名格式的Redis键和调度ID。

#### `ensure_default_instances()`
- **功能**: 一个非常有用的启动或维护任务。它会遍历数据库中所有的 `TaskConfig`，并检查每个需要自动调度的配置是否至少有一个正在运行的实例。如果没有，它会自动为其创建一个。

## 全局实例
- `scheduler_service = SchedulerService()`: 创建了一个全局唯一的服务实例，作为整个应用与调度系统交互的统一入口。
