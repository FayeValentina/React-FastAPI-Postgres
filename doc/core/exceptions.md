# `exceptions.py` 文档

此文件定义了应用程序中使用的所有自定义异常类。通过创建标准化的异常，可以使错误处理更加一致和可维护。

## 核心设计

1.  **基类 `ApiError`**：
    - 所有的自定义API异常都继承自这个类。
    - 它包含了 `status_code`（HTTP状态码）、`detail`（错误信息）和 `headers`（自定义响应头）三个核心属性。
    - 提供了一个 `to_http_exception()` 方法，可以方便地将自定义异常转换为FastAPI能够处理的 `HTTPException`。

2.  **继承与分类**：
    - 相关的异常被组织在一起，并从一个共同的父类继承。例如，所有与认证相关的错误都继承自 `AuthenticationError`，所有与用户相关的错误都继承自 `UserError`。
    - 这种结构使得在异常处理器中可以更容易地捕获一整类的错误。

3.  **标准化**：
    - 许多异常类的默认错误信息和状态码都直接从 `app.constant.constants` 中导入，确保了错误信息和状态码在整个应用中的一致性。

## 主要异常类

### `ApiError(Exception)`
- **描述**：所有API异常的基类。

### `AuthenticationError(ApiError)`
- **描述**：认证失败的基类。默认状态码为 `401 Unauthorized`，并会自动添加 `WWW-Authenticate: Bearer` 响应头。
- **子类**：
    - `InvalidCredentialsError`: 登录时用户名或密码错误。
    - `InvalidRefreshTokenError`: 提供的刷新令牌无效、过期或已被吊销。

### `UserError(ApiError)`
- **描述**：用户相关操作错误的基类。默认状态码为 `400 Bad Request`。
- **子类**：
    - `UserNotFoundError`: 在数据库中找不到指定的用户（状态码 `404`）。
    - `EmailAlreadyRegisteredError`: 注册时邮箱已被使用（状态码 `409 Conflict`）。
    - `UsernameTakenError`: 注册时用户名已被使用（状态码 `409 Conflict`）。
    - `InactiveUserError`: 尝试操作一个未激活的用户账户（状态码 `403 Forbidden`）。

### `InsufficientPermissionsError(ApiError)`
- **描述**：当用户尝试执行其没有权限的操作时抛出。状态码为 `403 Forbidden`。

### `DatabaseError(ApiError)`
- **描述**：数据库操作失败时的通用错误。状态码为 `500 Internal Server Error`。

### 资源相关异常
- `ResourceAlreadyExistsError`: 尝试创建已存在的资源（状态码 `409 Conflict`）。
- `ResourceNotFoundError`: 请求的资源不存在（状态码 `404 Not Found`）。

### `ValidationError(ApiError)`
- **描述**：当输入数据未能通过业务逻辑验证时抛出（区别于Pydantic的自动验证）。状态码为 `400 Bad Request`。
