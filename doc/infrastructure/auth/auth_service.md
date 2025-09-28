# `auth_service.py` 文档

此文件定义了 `AuthRedisService` 类，专门用于处理与认证相关的、存储在Redis中的数据，特别是刷新令牌（Refresh Tokens）的管理。

## `AuthRedisService(RedisBase)` 类

这个类继承自 `RedisBase`，利用其提供的Redis连接池和基本操作，实现了针对认证场景的特定逻辑。

### 数据结构设计

`AuthRedisService` 在Redis中维护了两种主要的数据结构来管理刷新令牌：

1.  **令牌数据 (String)**:
    - **键 (Key)**: `auth:token:<token_string>`
    - **值 (Value)**: 一个JSON字符串，包含 `user_id`, `created_at`, `expires_at` 等信息。
    - **用途**: 存储每个刷新令牌的具体信息。
    - **TTL**: 设置了与令牌有效期相同的过期时间，确保令牌能自动从Redis中删除。

2.  **用户令牌集合 (Set)**:
    - **键 (Key)**: `auth:user_tokens:<user_id>`
    - **值 (Value)**: 一个集合（Set），包含了该用户所有有效的刷新令牌字符串。
    - **用途**: 能够快速查询某个用户拥有的所有令牌，方便实现“撤销所有会话”的功能。
    - **TTL**: 同样设置了过期时间，以防止在没有令牌时，这个集合键永久存在。

### 主要方法

#### `store_refresh_token(self, token, user_id, ...)`
- **功能**: 存储一个新的刷新令牌。
- **事务性操作**: 使用Redis的 `pipeline` 来确保以下操作的原子性：
    1.  创建一个字符串键来存储令牌的详细数据。
    2.  将令牌字符串添加到一个集合（Set）中，该集合属于对应的用户。
    3.  为用户的令牌集合设置或续期TTL。

#### `revoke_token(self, token)`
- **功能**: 撤销（删除）一个指定的刷新令牌。
- **事务性操作**: 使用 `pipeline` 执行：
    1.  删除存储令牌数据的字符串键。
    2.  从所属用户的令牌集合中移除该令牌字符串。

#### `revoke_all_user_tokens(self, user_id)`
- **功能**: 撤销一个用户的所有刷新令牌，实现“登出所有设备”的功能。
- **实现**: 
    1.  首先从用户的令牌集合中获取所有令牌字符串。
    2.  然后使用 `pipeline` 一次性删除所有这些令牌对应的数据键以及用户令牌集合本身。

#### `is_token_valid(self, token)`
- **功能**: 检查一个令牌是否存在于Redis中，并且其内部记录的 `expires_at` 时间戳尚未过期。

#### `get_refresh_token_payload(self, token)`
- **功能**: 获取并解析存储在Redis中的令牌数据（JSON）。

#### `cleanup_expired_tokens(self)`
- **功能**: 一个维护性方法，可以扫描所有令牌键，并主动删除那些已经过期的令牌。这可以作为一个定时任务来运行，用于清理那些因为某些原因（如服务重启）未能通过TTL自动删除的令牌。

## 全局实例和依赖项

- `auth_redis_service = AuthRedisService()`: 创建了一个全局唯一的服务实例。
- `get_auth_redis_service()`: 一个FastAPI依赖项函数，用于在API路由中注入 `auth_redis_service` 实例。
