# `dependencies.py` 文档

此文件包含用于FastAPI依赖项注入的函数，主要用于用户认证和权限验证。

## 函数说明

### `get_current_user_from_request(request: Request, db: AsyncSession) -> User`

从HTTP请求中获取当前用户。它依赖于在之前的中间件（`AuthMiddleware`）中已经验证过的JWT令牌。

- **功能**：从请求状态 `request.state.user_payload` 中解析用户ID，并从数据库中检索用户对象。
- **失败情况**：
    - 如果请求中没有用户信息，则抛出 `AuthenticationError`。
    - 如果在数据库中找不到对应的用户，则抛出 `UserNotFoundError`。

### `get_current_active_user(current_user: User) -> User`

获取当前已登录且处于“活跃”状态的用户。

- **功能**：检查 `get_current_user_from_request` 返回的用户对象的 `is_active` 属性。
- **失败情况**：如果用户不活跃，则抛出 `InactiveUserError`。

### `get_optional_current_user(request: Request, db: AsyncSession) -> Optional[User]`

尝试获取当前用户，但如果用户未认证或不活跃，则返回 `None` 而不是抛出异常。

- **功能**：这是一个可选的依赖项，适用于那些对认证用户和匿名用户都开放的API端点。
- **返回值**：如果用户成功认证，则返回 `User` 对象；否则返回 `None`。

### `get_current_superuser(current_user: User) -> User`

获取当前用户并验证其是否为超级用户（管理员）。

- **功能**：检查 `get_current_active_user` 返回的用户对象的 `is_superuser` 属性。
- **失败情况**：如果用户不是超级用户，则抛出 `InsufficientPermissionsError`。

### `get_current_user_from_ws(ws: WebSocket, db: AsyncSession) -> User`

从WebSocket连接中获取并验证当前用户。

- **功能**：
    1.  优先从查询参数 `?token=` 中获取访问令牌。
    2.  如果查询参数中没有，则尝试从 `Authorization: Bearer <token>` HTTP头中获取。
    3.  验证令牌的有效性、类型（必须是 `access_token`）和过期时间。
    4.  从数据库中检索用户，并检查其是否活跃。
- **失败情况**：在令牌无效、用户不存在或用户不活跃等任何验证失败的情况下，它会关闭WebSocket连接并抛出相应的认证错误。
