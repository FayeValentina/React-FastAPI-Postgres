# `redis_base.py` 文档

此文件定义了 `RedisBase` 类，它是与Redis进行交互的基石。这个类封装了所有底层的、通用的Redis命令，并提供了连接管理、命名空间隔离和健壮的错误处理。

## 核心设计

1.  **共享连接池**: 它不自己创建连接，而是依赖于一个全局的、共享的 `redis_connection_manager`。这确保了整个应用程序高效地复用Redis连接，避免了频繁创建和销毁连接的开销。

2.  **上下文管理器**: 所有操作都通过 `async with self._connection_manager.get_connection() as client:` 的模式执行。这确保了每次操作都能从连接池中安全地获取一个连接，并在操作完成后自动将其释放回连接池，即使发生异常也能保证连接的正确回收。

3.  **命名空间隔离**: 
    - `__init__(self, key_prefix: str = "")`: 构造函数接收一个 `key_prefix` 参数。
    - `_make_key(self, key: str)`: 这是一个内部辅助方法，它会自动将 `key_prefix` 添加到所有操作的键名之前。
    - **效果**: 不同的服务（如 `AuthRedisService`, `CacheRedisService`）可以继承 `RedisBase` 并传入不同的前缀（如 `"auth:"`, `"cache:"`），从而在逻辑上将它们的键隔离开，避免键名冲突。

4.  **健壮的错误处理**: 每个Redis操作都被包裹在 `try...except` 块中。如果发生任何与Redis通信的异常，它会记录一个详细的错误日志，并返回一个安全的默认值（如 `None`, `False`, `0`, `[]`），防止因Redis故障导致整个应用崩溃。

5.  **异步原生**: 所有方法都是 `async` 的，与FastAPI的异步特性完美集成。

## 主要方法分类

`RedisBase` 提供了对Redis常用数据结构的全面封装：

### 字符串 (String) 操作
- `set(key, value, ttl)`: 设置一个字符串值，可附带过期时间。
- `get(key)`: 获取一个字符串值。
- `delete(*keys)`: 删除一个或多个键。
- `exists(*keys)`: 检查一个或多个键是否存在。
- `expire(key, ttl)`: 为一个已存在的键设置过期时间。

### JSON 操作
- `set_json(key, data, ttl)`: 将一个Python字典自动序列化为JSON字符串后存入Redis。
- `get_json(key)`: 从Redis获取一个JSON字符串并自动反序列化为Python字典。

### 哈希 (Hash) 操作
- `hset(name, mapping)`: 在一个哈希中设置一个或多个字段。
- `hget(name, key)`: 获取哈希中的单个字段值。
- `hgetall(name)`: 获取哈希中的所有字段和值。
- `hdel(name, *keys)`: 删除哈希中的一个或多个字段。

### 集合 (Set) 操作
- `sadd(name, *values)`: 向集合中添加一个或多个成员。
- `srem(name, *values)`: 从集合中移除一个或多个成员。
- `smembers(name)`: 获取集合中的所有成员。
- `sismember(name, value)`: 判断一个值是否存在于集合中。
- `scard(name)`: 获取集合的成员数量（基数）。

### 列表 (List) 操作
- `lpush(name, *values)`: 从列表左侧推入一个或多个值。
- `rpush(name, *values)`: 从列表右侧推入一个或多个值。
- `lrange(name, start, end)`: 获取列表指定范围内的所有元素。

### SCAN 操作 (非阻塞)
- **背景**: `KEYS` 命令在处理大量键时会阻塞Redis服务器。`SCAN` 提供了一种安全、非阻塞的替代方案。
- `scan_keys(pattern, ...)`: 使用 `SCAN` 命令迭代地查找匹配 `pattern` 的所有键。
- `scan_count(pattern, ...)`: 使用 `SCAN` 统计匹配模式的键的数量。
- `scan_delete(pattern, ...)`: 使用 `SCAN` 安全地查找并删除所有匹配的键。

### Pipeline / 事务
- `pipeline(transaction: bool = True)`: 提供一个异步上下文管理器，用于执行多个Redis命令。如果 `transaction=True`，这些命令会被包裹在 `MULTI/EXEC` 块中，以原子方式执行。

### 工具方法
- `ping()`: 测试与Redis服务器的连接是否正常。
- `flushdb()`: 清空当前数据库（**危险操作，慎用**）。

## 总结

`RedisBase` 是一个设计良好、功能完备的Redis操作基类。它通过封装底层细节、提供健壮的错误处理和连接管理，使得上层服务（如 `AuthRedisService`, `CacheRedisService`）可以更专注于自身的业务逻辑，而无需关心与Redis交互的具体实现。
