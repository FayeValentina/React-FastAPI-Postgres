# `redis_pool.py` 文档

此文件定义了 `RedisConnectionManager`，一个采用单例模式（Singleton Pattern）的Redis连接池管理器。它的核心职责是创建、维护和监控一个全局共享的Redis连接池，确保整个应用程序能够高效、可靠地与Redis服务器通信。

## `RedisConnectionManager` 类

### 单例模式
- **实现**: 通过重写 `__new__` 方法，确保在整个应用的生命周期中，`RedisConnectionManager` 只有一个实例存在。
- **目的**: 保证所有Redis操作都共享同一个连接池，避免资源浪费和管理混乱。

### 核心属性
- `_pool`: 存储 `redis-py` 库的异步连接池对象。
- `_config`: 存储从 `settings.redis_pool` 加载的连接池配置 (`RedisPoolConfig`)。
- `_is_healthy`: 一个布尔标志，表示当前连接池是否处于健康状态。
- `_last_health_check`: 记录上次成功进行健康检查的时间。
- `_health_check_lock`: 一个 `asyncio.Lock`，用于防止在多任务并发场景下同时执行多个健康检查。

### 主要方法

#### `initialize(self, ...)`
- **功能**: 初始化连接池。这是管理器最先被调用的方法之一。
- **流程**:
    1.  如果连接池 (`_pool`) 尚未创建，则执行初始化。
    2.  使用 `redis.from_url` 并结合配置文件中的 `CONNECTION_URL` 和 `RedisPoolConfig` 来创建一个 `redis-py` 的异步连接池实例。
    3.  创建后，立即执行一次 `_health_check()` 来验证连接是否成功。
    4.  如果初始化过程中发生任何错误，会将 `_is_healthy` 标记为 `False` 并抛出异常。

#### `get_client(self)`
- **功能**: 获取一个可用的Redis客户端（实际上就是连接池对象本身，因为 `redis-py` 的设计就是将连接池作为客户端使用）。
- **流程**:
    1.  如果连接池未初始化，则先调用 `initialize()`。
    2.  调用 `_periodic_health_check()` 来决定是否需要执行一次新的健康检查。
    3.  如果连接池不健康，则直接抛出 `ConnectionError`。
    4.  返回连接池实例。

#### `get_connection(self)`
- **功能**: 一个异步上下文管理器，为 `RedisBase` 类提供了一种安全获取和使用Redis连接的方式。
- **用法**: `async with manager.get_connection() as client:`
- **流程**: 
    1.  调用 `get_client()` 获取连接池。
    2.  使用 `yield` 将连接池对象提供给上下文内的代码块。
    3.  如果在代码块中发生异常，它会捕获异常，将连接池标记为不健康 (`_is_healthy = False`)，然后重新抛出异常。

#### `_health_check(self)`
- **功能**: 执行一次实际的健康检查。
- **实现**: 向Redis服务器发送 `PING` 命令。如果能在配置的超时时间内收到 `PONG` 响应，则认为连接是健康的，并更新 `_is_healthy` 和 `_last_health_check` 状态。

#### `_periodic_health_check(self)`
- **功能**: 决定是否需要触发一次新的健康检查。
- **逻辑**: 检查当前时间与 `_last_health_check` 的时间差，如果超过了配置的 `health_check_interval`（例如30秒），则会获取锁并执行一次 `_health_check`。使用锁和双重检查机制是为了防止并发请求导致不必要的重复检查。

#### `get_pool_info(self)`
- **功能**: 提供一个用于监控和调试的方法，返回一个包含连接池当前状态的字典（如健康状况、最大连接数、可用连接数、正在使用的连接数等）。

#### `reset_pool(self)` / `close(self)`
- **功能**: 用于手动重置或关闭连接池。这在测试或需要强制重新建立所有连接的场景中非常有用。

## 全局实例

- `redis_connection_manager = RedisConnectionManager()`: 创建了 `RedisConnectionManager` 的全局单例实例。应用的所有部分都通过这个实例与Redis连接池交互。
