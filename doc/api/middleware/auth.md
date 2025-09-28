# `auth.py` 文档

此文件定义了 `AuthMiddleware`，一个用于JWT（JSON Web Token）认证的FastAPI中间件。

## `AuthMiddleware` 类

这是一个继承自 `BaseHTTPMiddleware` 的中间件，用于保护API端点，确保只有经过认证的请求才能访问受保护的资源。

### `__init__(self, app, exclude_paths, exclude_path_regexes)`

构造函数用于初始化中间件。

- **功能**：
    - 接收一个 `exclude_paths` 列表，其中包含不需要认证的精确路径（如 `/v1/auth/login`）。
    - 接收一个 `exclude_path_regexes` 列表，包含用于匹配豁免路径的正则表达式。
    - 如果没有提供 `exclude_paths`，则使用 `DEFAULT_EXCLUDE_PATHS` 默认列表。

### `async dispatch(self, request: Request, call_next: Callable)`

这是中间件的核心处理逻辑，每个请求都会经过这里。

- **功能**：
    1.  首先调用 `_should_exclude` 检查当前请求的路径是否在豁免列表中。如果是，则直接进入下一个请求处理器，不进行认证。
    2.  如果需要认证，则从请求头中提取 `Authorization` 字段。
    3.  验证 `Authorization` 头的格式是否为 `Bearer <token>`。
    4.  调用 `app.core.security.verify_token` 函数来验证令牌的有效性（签名和过期时间）。
    5.  检查令牌的类型是否为 `access_token`，确保刷新令牌不能用于API访问。
    6.  如果所有验证都通过，将解码后的令牌载荷（payload）存入 `request.state.user_payload`，以便后续的依赖项（如 `get_current_user`）可以使用。
- **失败情况**：在任何验证步骤失败时（如缺少令牌、格式错误、令牌无效或过期），中间件会立即返回一个 `HTTP 401 Unauthorized` 的JSON响应，并终止请求处理流程。

### `_should_exclude(self, request: Request) -> bool`

一个内部辅助方法，用于判断当前请求的路径是否应该被豁免认证。

- **功能**：
    - 它会自动处理FastAPI的 `root_path` 配置，将请求路径转换为相对于应用根的路径，以实现解耦。
    - 检查转换后的路径是否与 `self.exclude_paths` 中的任何精确路径或前缀路径 (`*`) 匹配。
    - 检查路径是否与 `self.exclude_path_regexes` 中的任何正则表达式匹配。
- **返回值**：如果路径应该被豁免，则返回 `True`，否则返回 `False`。
