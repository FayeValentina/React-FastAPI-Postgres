# `service.py` (dynamic_settings) 文档

此文件定义了 `DynamicSettingsService`，一个核心服务，用于管理那些可以在应用程序运行时被动态修改的配置项。它使用Redis作为持久化后端，并提供了优雅的回退机制和内存缓存。

## 核心设计理念

- **动态性**: 允许管理员通过API或其他方式实时调整某些应用参数（例如RAG策略的开关、各种阈值等），而无需重新部署或重启服务。
- **持久化**: 所有被覆盖的配置项都存储在Redis中，因此即使应用重启，这些修改依然生效。
- **默认值回退**: 配置的“真实来源”是 `config.py` 中的 `Settings` 类。如果Redis不可用或其中没有存储任何覆盖值，服务会安全地回退到 `config.py` 中定义的默认值。
- **内存缓存**: 服务在内存中维护一个最新的配置快照 (`_latest_effective`)。这使得在请求处理期间访问配置项时，可以实现近乎零延迟的快速读取，而无需每次都查询Redis。
- **线程安全**: 使用 `threading.RLock` 来保护对内存缓存快照的读写，确保在多线程环境下的数据一致性。

## `DynamicSettingsService` 类

### 数据结构 (Redis)
- **配置键**: `app:dynamic_settings` - 一个Redis的 `String` (实际是JSON)，存储了所有被覆盖的配置项的键值对。
- **元数据键**: `app:dynamic_settings_metadata` - 另一个 `String` (JSON)，存储了最后更新的时间戳和被更新的字段列表。

### 主要方法

#### `defaults(self) -> dict`
- **功能**: 从 `settings.dynamic_settings_defaults()` 方法获取并返回一份全新的、基于 `config.py` 的默认动态配置字典。

#### `get_all(self) -> dict`
- **功能**: 这是获取当前生效配置的核心方法。
- **流程**:
    1.  获取默认配置。
    2.  尝试从Redis中读取已保存的覆盖配置。
    3.  如果Redis访问失败，则记录警告并返回默认配置。
    4.  如果成功，将Redis中的覆盖值合并到默认配置之上（即Redis中的值会覆盖默认值）。
    5.  将合并后的最终配置更新到内存缓存快照 (`_set_latest_effective`)。
    6.  返回合并后的配置。

#### `cached_value(self, key: str, default: Any) -> Any`
- **功能**: 从内存缓存快照中快速获取单个配置项的值。这是在应用中最常被调用的方法，因为它速度最快。

#### `update(self, payload: dict) -> dict`
- **功能**: 更新一个或多个动态配置项。
- **流程**:
    1.  获取当前所有配置。
    2.  将传入的 `payload` 合并到当前配置中。
    3.  将合并后的完整配置写回Redis。
    4.  更新元数据（最后更新时间等）。
    5.  更新内存缓存快照。

#### `reset(self, keys: Iterable[str] | None = None)`
- **功能**: 将配置项重置为默认值。
- **两种模式**:
    - **`keys` is `None`**: 删除Redis中存储的所有覆盖值，使配置完全恢复到 `config.py` 中的默认状态。
    - **`keys` is provided**: 只将指定列表中的配置项恢复为默认值，其他覆盖项保持不变。

#### `refresh(self) -> dict`
- **功能**: 强制从Redis重新加载所有配置，并更新内存缓存。这可以用于在外部直接修改了Redis后，通知应用来同步最新的配置。

## 单例模式和依赖注入

- **`_build_dynamic_settings_service()`**: 使用 `@lru_cache(maxsize=1)` 装饰器实现了一个线程安全的单例工厂。这确保了在整个应用程序的生命周期中，只有一个 `DynamicSettingsService` 实例存在。
- **`get_dynamic_settings_service()`**: 一个标准的FastAPI依赖项函数，用于在需要时将这个单例服务注入到API路由或其他服务中。
