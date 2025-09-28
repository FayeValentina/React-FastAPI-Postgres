# `keyspace.py` 文档

此文件是Redis键空间（Keyspace）管理的“单一事实来源”（Single Source of Truth）。它的核心目的是将Redis中存储的各种键的命名规则进行集中化和标准化。

## 核心设计理念

1.  **集中管理**: 将所有Redis键的格式和前缀定义在一个地方，避免在代码中到处硬编码字符串，如 `"auth:token:"`。
2.  **命名空间 (Namespace)**: 通过嵌套的类结构，将键的命名按照其所属的业务领域（如 `auth`, `cache`, `scheduler`）进行组织，使得键的用途一目了然。
3.  **解耦与兼容**: 
    - `RedisBase` 基类通过 `key_prefix` 参数负责顶层的命名空间（如 `auth:`）。
    - 本文件中的辅助类则负责定义该命名空间下的子键格式（如 `token:<token_string>`）。
    - 这种设计使得键的生成逻辑与Redis的底层操作完全解耦。

## 结构

文件定义了一个主类 `RedisKeys`，它包含了多个嵌套的、代表不同业务领域的内部类。每个内部类都提供了一系列方法，用于生成特定用途的Redis键名。

### `_AuthKeys`
- **命名空间**: `auth:`
- **用途**: 管理与用户认证（特别是刷新令牌）相关的键。
- **方法**:
    - `token(token)`: 生成存储令牌数据的键，例如 `auth:token:xyz...`。
    - `user_tokens(user_id)`: 生成存储用户所有令牌集合的键，例如 `auth:user_tokens:123`。

### `_CacheKeys`
- **命名空间**: `cache:`
- **用途**: 管理基于标签的缓存系统所使用的键。
- **方法**:
    - `tag(tag)`: 生成存储“标签-缓存键”映射关系的集合键，例如 `cache:tag:user_profile`。

### `_SchedulerKeys`
- **命名空间**: `schedule:`
- **用途**: 管理与后台任务调度器（TaskIQ）相关的状态、历史、统计等数据的键。
- **方法**: 提供了多种方法来生成与特定调度任务（`schedule_id`）相关的键，如 `schedule_status(id)`, `schedule_history(id)` 等。
- **`build_schedule_id(...)`**: 一个重要的辅助方法，用于根据任务配置ID（`config_id`）和一个唯一标识（`uid`）来构建一个全局唯一的 `schedule_id`。

### `_AppKeys`
- **命名空间**: `app:`
- **用途**: 管理应用级别的、全局共享的键。
- **方法**:
    - `dynamic_settings()`: 生成存储动态配置的键，例如 `app:dynamic_settings`。
    - `dynamic_settings_metadata()`: 生成存储动态配置元数据的键，例如 `app:dynamic_settings:meta`。

## `redis_keys` 单例

- **定义**: `redis_keys = RedisKeys()`
- **功能**: 在文件末尾创建了一个 `RedisKeys` 的全局单例实例。
- **使用**: 在应用的其他任何地方，都可以通过 `from app.infrastructure.redis.keyspace import redis_keys` 来导入这个实例，并以一种清晰、类型安全的方式来生成键名，例如 `redis_keys.auth.token("abc")` 或 `redis_keys.scheduler.schedule_status("xyz")`。

这种方式极大地提高了代码的可读性和可维护性，当需要修改某个键的命名规则时，只需在此文件中修改一处即可。
