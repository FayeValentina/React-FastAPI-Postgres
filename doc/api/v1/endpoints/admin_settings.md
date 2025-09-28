# `admin_settings.py` (endpoints) 文档

此文件定义了与动态管理员设置相关的API端点。所有这些端点都在 `/api/v1/admin/settings` 路径下，并且被保护，只有超级管理员（Superuser）才能访问。

## Router 配置
- **`prefix`**: `/admin/settings`
- **`tags`**: `["admin-settings"]` (用于API文档分组)
- **`dependencies`**: `[Depends(get_current_superuser)]`
    - 这是一个在整个路由器级别上应用的核心依赖项。它确保了任何访问此路由器下端点的请求，都必须经过 `get_current_superuser` 的验证，即请求者必须是已登录的超级管理员用户。

## Endpoints

### `GET /`
- **功能**: 读取所有动态管理员设置的当前状态。
- **响应模型**: `AdminSettingsResponse`
- **逻辑**: 调用 `admin_settings_service.read_settings` 方法，获取设置的默认值、Redis中的覆盖值、最终生效的值以及最后更新时间等信息，并将其返回。

### `PUT /`
- **功能**: 更新一个或多个动态管理员设置。
- **请求体**: `AdminSettingsUpdate`
- **响应模型**: `AdminSettingsResponse`
- **逻辑**: 
    1.  接收一个 `AdminSettingsUpdate` 类型的请求体，其中包含了需要更新的字段和值。Pydantic会自动验证这些值的类型和范围。
    2.  调用 `admin_settings_service.update_settings` 方法，将这些更新持久化到Redis中。
    3.  返回更新后的最新设置状态。

### `POST /reset`
- **功能**: 将一个或多个动态设置重置为其默认值。
- **请求体**: `AdminSettingsResetRequest`
- **响应模型**: `AdminSettingsResponse`
- **逻辑**: 
    1.  接收一个 `AdminSettingsResetRequest` 请求体，其中可以包含一个可选的 `keys` 列表。
    2.  调用 `admin_settings_service.reset_settings` 方法。
        - 如果 `keys` 列表存在，则只重置指定的键。
        - 如果 `keys` 列表不存在，则重置所有动态设置。
    3.  返回重置后的最新设置状态。
