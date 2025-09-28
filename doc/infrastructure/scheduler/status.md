# `status.py` (scheduler) 文档

此文件定义了 `ScheduleHistoryRedisService`，一个专门用于在Redis中管理和记录调度任务**运行时状态**的服务。它的设计完全以 `schedule_id` 为核心，将每个调度实例的状态、元数据和历史事件独立存储。

## `ScheduleStatus(str, Enum)`
这是一个简单的枚举类，定义了调度实例可能处于的几种状态：
- `INACTIVE`: 非活动状态，通常是任务刚创建或已被注销。
- `ACTIVE`: 活动状态，表示任务已在 `TaskIQ` 中注册并等待调度。
- `PAUSED`: 已暂停，任务已从 `TaskIQ` 中移除，但其配置和历史仍然保留。
- `ERROR`: 错误状态，表示在获取状态时发生了问题。

## `ScheduleHistoryRedisService(RedisBase)` 类

这个类继承自 `RedisBase`，利用其提供的通用Redis操作，实现了针对调度状态管理的特定逻辑。

### 数据结构设计 (Redis)

服务在 `schedule:` 命名空间下维护了以下几种数据结构：

1.  **索引 (Set)**:
    - **键**: `schedule:index:config:<config_id>`
    - **值**: 一个集合，包含了由该 `config_id` 创建的所有 `schedule_id`。
    - **用途**: 能够快速地从一个配置模板找到其下所有的运行实例。

2.  **状态 (String)**:
    - **键**: `schedule:status:<schedule_id>`
    - **值**: 一个字符串，表示该实例的当前状态（如 `"active"`, `"paused"`）。
    - **用途**: 快速查询单个实例的运行状态。

3.  **元数据 (JSON String)**:
    - **键**: `schedule:meta:<schedule_id>`
    - **值**: 一个JSON字符串，存储了该实例在注册时的配置快照（任务名称、参数、调度规则等）。
    - **用途**: 在恢复任务或进行调试时，能够了解任务的原始配置。

4.  **历史记录 (List)**:
    - **键**: `schedule:history:<schedule_id>`
    - **值**: 一个Redis列表，每个元素都是一个记录了历史事件（如 `task_registered`, `status_changed`）的JSON字符串。
    - **用途**: 跟踪每个实例的生命周期事件。
    - **自动修剪**: 在添加新事件时，会自动使用 `LTRIM` 命令将列表长度限制在 `self.max_history` (例如100条)，防止历史记录无限增长。

### 主要方法

#### 索引管理
- `add_schedule_to_index(config_id, schedule_id)`: 将 `schedule_id` 添加到 `config_id` 的索引集合中。
- `remove_schedule_from_index(config_id, schedule_id)`: 从索引中移除。
- `list_schedule_ids(config_id)`: 列出某个 `config_id` 下的所有 `schedule_id`。

#### 状态管理
- `set_schedule_status(schedule_id, status)`: 设置一个实例的状态，并自动记录一条 `status_changed` 的历史事件。
- `get_schedule_status(schedule_id)`: 获取单个实例的状态。
- `get_all_schedule_statuses()`: 使用 `SCAN` 命令获取所有已知实例的状态，返回一个 `{schedule_id: status}` 的字典。

#### 元数据管理
- `set_schedule_metadata(schedule_id, metadata)`: 将配置快照以JSON格式存入Redis，并设置默认的TTL（例如7天）。
- `get_schedule_metadata(schedule_id)`: 获取并解析元数据。

#### 历史事件
- `add_schedule_history_event(schedule_id, event_data)`: 将一个事件（字典）序列化为JSON，并从左侧推入（`LPUSH`）到对应的历史记录列表中。同时，它会修剪列表并为键续期。
- `get_schedule_history(schedule_id, limit)`: 获取最近的N条历史记录。

#### 综合查询
- `get_schedule_full_info(schedule_id, ...)`: 一个便捷方法，用于一次性获取某个 `schedule_id` 的所有相关信息（状态、元数据、最近的历史记录）。
- `get_scheduler_summary()`: 统计所有实例中处于各个状态（active, paused等）的数量，提供一个全局概览。

#### 清理方法
- `purge_schedule_artifacts(schedule_id)`: 彻底删除与某个 `schedule_id` 相关的所有Redis键（状态、元数据、历史等）。
- `cleanup_legacy_config_scoped_keys()`: 一个维护方法，用于查找并删除在代码重构前使用的、基于 `config_id` 的旧格式键。
