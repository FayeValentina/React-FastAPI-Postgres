# `auth.py` (endpoints) 文档

此文件定义了所有与用户认证、注册和密码管理相关的API端点。这些端点构成了系统的核心安全门户。

## Router 配置
- **`prefix`**: `/auth`
- **`tags`**: `["auth"]`

## Endpoints

### `POST /login`
- **功能**: 用户登录。
- **请求体**: `LoginRequest` (包含 `username`, `password`, `remember_me`)。
- **响应模型**: `Token` (包含 `access_token`, `refresh_token`, `expires_at`)。
- **逻辑**: 调用 `auth_service.login`，该服务会验证用户凭据，并在成功后创建并返回一对新的令牌，同时吊销该用户之前的所有会话。

### `POST /refresh`
- **功能**: 使用刷新令牌获取新的访问令牌。
- **请求体**: `RefreshTokenRequest` (包含 `refresh_token`)。
- **响应模型**: `Token`。
- **逻辑**: 调用 `auth_service.refresh_token`，该服务会验证刷新令牌的有效性，并执行“令牌轮换”（Token Rotation）：吊销旧的刷新令牌，颁发一对全新的访问令牌和刷新令牌。

### `POST /register`
- **功能**: 注册一个新用户。
- **请求体**: `UserCreate`。
- **响应模型**: `User`。
- **缓存**: 使用 `@invalidate([CacheTags.USER_LIST])` 装饰器。当新用户注册成功后，会自动使所有与用户列表相关的缓存失效，确保用户列表的API能返回最新的数据。
- **逻辑**: 调用 `auth_service.register_user`，该服务会处理用户信息的验证和持久化。

### `POST /logout`
- **功能**: 用户登出。
- **依赖**: `Depends(get_current_active_user)`，需要用户已登录。
- **逻辑**: 调用 `auth_service.logout`，该服务会吊销当前用户的所有刷新令牌，使其在所有设备上的会话都失效。

### `GET /me`
- **功能**: 获取当前登录用户的个人信息。
- **依赖**: `Depends(get_current_active_user)`。
- **响应模型**: `User`。
- **缓存**: 使用 `@cache([CacheTags.USER_ME], ...)` 装饰器。当前用户的个人信息会被缓存起来，以提高后续请求的响应速度。
- **逻辑**: 调用 `auth_service.get_me`。

### `POST /forgot-password`
- **功能**: 请求发送密码重置邮件。
- **请求体**: `PasswordResetRequest` (包含 `email`)。
- **逻辑**: 调用 `auth_service.forgot_password`，该服务会处理令牌生成和邮件发送的逻辑。

### `POST /reset-password`
- **功能**: 使用重置令牌来设置新密码。
- **请求体**: `PasswordResetConfirm` (包含 `token`, `new_password`)。
- **逻辑**: 调用 `auth_service.reset_password`，该服务会验证令牌，更新密码，并吊销用户的所有旧会话。

### `POST /verify-reset-token`
- **功能**: 验证一个密码重置令牌是否仍然有效。
- **请求参数**: `token` (作为查询参数或表单数据)。
- **逻辑**: 调用 `auth_service.verify_reset_token`。
