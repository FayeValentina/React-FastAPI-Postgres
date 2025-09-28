# `service.py` (auth) 文档

此文件定义了 `AuthService`，它是处理所有与用户认证、授权和管理相关的核心业务逻辑的服务层。它作为API路由（Controller）和底层数据仓库（Repository）、外部服务（如Email）之间的协调者。

## `AuthService` 类

### 认证流程方法

#### `login(db, login_data, auth_redis)`
- **功能**: 处理用户登录逻辑。
- **流程**:
    1.  尝试通过用户名或邮箱从数据库中查找用户。
    2.  如果找不到用户，或密码验证失败（使用 `security.verify_password`），则抛出 `InvalidCredentialsError`。
    3.  如果验证成功，调用 `security.create_token_pair` 创建一个新的访问令牌和刷新令牌。
    4.  **关键安全步骤**: 调用 `auth_redis.revoke_all_user_tokens` 将该用户之前的所有刷新令牌全部吊销。这确保了每次登录都会使其他所有设备上的会话失效，增强了安全性。
    5.  将新的刷新令牌存储到Redis中。
    6.  返回包含新令牌对的 `Token` 对象。

#### `refresh_token(db, refresh_data, auth_redis)`
- **功能**: 使用一个有效的刷新令牌来获取一个新的访问令牌和刷新令牌。
- **流程**:
    1.  验证传入的 `refresh_token` 的签名、类型和过期时间。
    2.  检查该刷新令牌是否存在于Redis中（防止已被吊销的令牌被重用）。
    3.  如果全部有效，则从Redis中删除（吊销）这个旧的刷新令牌。
    4.  创建一对全新的访问令牌和刷新令牌，并将新的刷新令牌存入Redis。
    5.  返回新的 `Token` 对象（令牌轮换机制）。

#### `logout(current_user, auth_redis)`
- **功能**: 用户登出。
- **实现**: 调用 `auth_redis.revoke_all_user_tokens`，吊销当前用户的所有刷新令牌，从而使其所有会话失效。

### 密码重置流程

#### `forgot_password(db, request_data)`
- **功能**: 处理“忘记密码”请求。
- **流程**:
    1.  根据邮箱查找用户。**安全提示**: 无论是否找到用户，都返回一个模糊的成功消息，以防止攻击者通过响应来探测系统中是否存在某个邮箱。
    2.  如果用户存在，调用 `crud_password_reset.create` 在数据库中创建一个新的密码重置记录。
    3.  调用 `email_service.send_password_reset_email` 发送包含重置链接的邮件。

#### `reset_password(db, reset_data, auth_redis)`
- **功能**: 处理用户点击重置链接后提交新密码的请求。
- **流程**:
    1.  验证 `reset_data.token` 的有效性（是否存在、未被使用、未过期）。
    2.  如果有效，更新用户的 `hashed_password`。
    3.  将该重置令牌标记为“已使用”。
    4.  **关键安全步骤**: 吊销该用户的所有刷新令牌，强制所有设备重新登录。
    5.  提交数据库事务。

### 用户管理方法

#### `register_user(db, user_in)` / `create_user(db, user_data)`
- **功能**: 注册或创建一个新用户。
- **实现**: 直接委托给 `crud_user.create_with_validation` 方法来处理。

#### `update_user(db, user_id, user_update, current_user)`
- **功能**: 更新用户信息。
- **权限检查**: 
    - 普通用户只能更新自己的信息。
    - 只有超级管理员 (`is_superuser`) 才能更新其他用户的信息。
    - 只有超级管理员才能修改 `is_superuser` 字段。
- **实现**: 权限检查通过后，委托给 `crud_user.update` 方法。

#### `get_users(db, current_user, ...)`
- **功能**: 获取用户列表，支持多种过滤和排序条件。
- **权限检查**: 普通用户只能看到 `is_active=True` 的用户，而超级管理员可以看到所有用户。
- **实现**: 动态构建一个SQLAlchemy查询，根据传入的参数（`name`, `email`, `sort_by` 等）添加 `where` 和 `order_by` 子句。

#### `get_user(db, user_id, current_user)` / `get_me(current_user)`
- **功能**: 获取单个用户的详细信息或当前登录用户的信息。
- **权限检查**: 普通用户只能获取自己的信息，超级管理员可以获取任何人的信息。

#### `delete_user(db, user_id, current_user)`
- **功能**: 删除一个用户。
- **权限检查**: 用户不能删除自己的账户。
- **实现**: 委托给 `crud_user.delete` 方法。

## 全局实例
- `auth_service = AuthService()`: 创建了一个全局唯一的服务实例，供API路由层调用。
