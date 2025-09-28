# `users.py` (endpoints) 文档

此文件定义了与用户管理（CRUD - 创建、读取、更新、删除）相关的API端点。

## Router 配置
- **`prefix`**: `/users`
- **`tags`**: `["users"]`

## Endpoints

### `POST /`
- **功能**: 创建一个新用户。
- **依赖**: `Depends(get_current_superuser)`，只有超级管理员才能创建新用户。
- **请求体**: `UserCreate`。
- **响应模型**: `UserResponse`。
- **缓存**: 使用 `@invalidate([CacheTags.USER_LIST])` 装饰器，确保在创建新用户后，用户列表的缓存会失效。
- **逻辑**: 调用 `auth_service.create_user` 处理用户的创建和持久化。

### `GET /`
- **功能**: 获取用户列表，支持多种过滤和排序条件。
- **依赖**: `Depends(get_current_active_user)`，任何已登录的活跃用户都可以访问。
- **查询参数**: 提供了 `name`, `email`, `age`, `is_active`, `sort_by` 等多种用于过滤和排序的参数。
- **响应模型**: `List[UserResponse]`。
- **缓存**: 使用 `@cache([CacheTags.USER_LIST], ...)` 装饰器，将用户列表的查询结果缓存起来，以提高性能。
- **逻辑**: 调用 `auth_service.get_users`，该服务会根据传入的查询参数动态构建数据库查询。

### `GET /{user_id}`
- **功能**: 获取指定ID用户的详细信息。
- **依赖**: `Depends(get_current_active_user)`。
- **响应模型**: `UserResponse`。
- **缓存**: 使用 `@cache([CacheTags.USER_PROFILE], ...)` 装饰器，将单个用户的个人资料缓存起来。
- **逻辑**: 调用 `auth_service.get_user`。该服务内部包含了权限检查逻辑：普通用户只能获取自己的信息，而超级管理员可以获取任何人的信息。

### `PATCH /{user_id}`
- **功能**: 更新指定ID用户的信息（支持部分更新）。
- **依赖**: `Depends(get_current_active_user)`。
- **请求体**: `UserUpdate`。
- **响应模型**: `UserResponse`。
- **缓存**: 使用 `@invalidate([CacheTags.USER_PROFILE, CacheTags.USER_LIST])` 装饰器，在更新用户信息后，同时使用户的个人资料缓存和用户列表缓存失效。
- **逻辑**: 调用 `auth_service.update_user`。该服务内部包含了权限检查逻辑：普通用户只能更新自己的信息，而超级管理员可以更新任何人。

### `DELETE /{user_id}`
- **功能**: 删除一个指定ID的用户。
- **依赖**: `Depends(get_current_superuser)`，只有超级管理员才能删除用户。
- **响应模型**: `UserResponse` (返回被删除的用户信息)。
- **缓存**: 使用 `@invalidate([CacheTags.USER_PROFILE, CacheTags.USER_LIST])` 装饰器，在删除用户后，同时使其个人资料缓存和用户列表缓存失效。
- **逻辑**: 调用 `auth_service.delete_user`。该服务会处理删除操作，并包含防止用户删除自己的逻辑。
