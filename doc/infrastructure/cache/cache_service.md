# `cache_service.py` 文档

此文件定义了 `CacheRedisService` 类，它作为与Redis进行缓存操作的专用服务层。同时，它还定义了 `CacheConfig` 类，用于集中管理缓存的TTL（Time To Live，存活时间）常量。

## `CacheConfig` 类

这是一个配置类，不包含任何逻辑，仅用于定义和组织与缓存过期时间相关的常量。

- **目的**: 
    - **标准化**: 提供一组预定义的、有意义的TTL名称（如 `SHORT_TTL`, `LONG_TTL`），使得在代码中设置过期时间时更加清晰和一致。
    - **集中管理**: 将所有TTL值集中在一个地方，方便未来统一调整缓存策略。
- **分类**: 
    - **通用TTL**: 定义了从短到长的通用过期时间。
    - **特定类型TTL**: 为不同业务数据（如用户信息、API列表、统计数据）定义了特定的过期时间。
    - **标签TTL (`TAG_TTL`)**: 为存储缓存键的“标签集合”本身设置一个较长的过期时间（24小时），确保即使没有新的缓存写入，标签集合也不会过早消失。

## `CacheRedisService(RedisBase)` 类

这个类继承自 `RedisBase`，专门为基于标签的缓存系统提供底层的Redis操作。它的设计是轻量级的，将复杂的缓存键生成逻辑保留在装饰器中，自身只负责与Redis的直接交互。

### 数据结构设计

`CacheRedisService` 依赖于两种Redis数据结构来工作：

1.  **缓存数据 (String)**:
    - **键**: 由 `@cache` 装饰器生成的唯一键，例如 `cache:user_profile:abcdef123...`。
    - **值**: 经过 `CacheSerializer` 序列化后的二进制数据。
    - **用途**: 存储实际的缓存内容。

2.  **标签集合 (Set)**:
    - **键**: `cache:tag:<tag_name>`，例如 `cache:tag:user_profile`。
    - **值**: 一个集合（Set），包含了所有被打上该标签的缓存数据键。
    - **用途**: 这是实现“按标签批量失效”功能的核心。当需要使 `user_profile` 相关的缓存全部失效时，只需找到这个集合，然后删除集合中记录的所有键即可。

### 主要方法

#### `get_binary_data(self, cache_key)`
- **功能**: 根据缓存键从Redis中获取原始的、未经反序列化的缓存数据。
- **返回值**: 返回字符串格式的数据（因为Redis连接池配置了 `decode_responses=True`）。

#### `set_binary_data(self, cache_key, data, ttl)`
- **功能**: 将序列化后的二进制数据存入Redis，并设置指定的TTL。

#### `add_key_to_tag(self, tag, cache_key)`
- **功能**: 将一个缓存键关联到一个标签上。
- **事务性操作**: 使用Redis的 `pipeline` 来确保以下两个操作的原子性：
    1.  将 `cache_key` 添加到对应的标签集合（Set）中。
    2.  为该标签集合续期（`expire`），以防止它过早被Redis删除。

#### `invalidate_by_tag(self, tag)`
- **功能**: 实现缓存的批量失效。
- **流程**:
    1.  根据 `tag` 找到对应的标签集合键。
    2.  使用 `SMEMBERS` 命令获取该集合中的所有缓存键。
    3.  如果集合不为空，使用 `DELETE` 命令一次性删除所有这些缓存键。
    4.  最后，删除该标签集合本身。
    - **返回值**: 返回被成功删除的缓存键的数量。

## 全局实例

- `cache_redis_service = CacheRedisService()`: 创建了一个全局唯一的服务实例，供缓存装饰器和应用的其他部分使用。
