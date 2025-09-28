# `schemas.py` (auth) 文档

此文件定义了与用户认证和管理功能相关的、所有用于API数据交换的Pydantic模型。这些模型负责定义API的请求体（Request Body）和响应体（Response Body）的结构，并利用Pydantic的强大功能进行数据验证。

## 设计理念

- **单一职责**: 每个模型都有明确的用途。例如，`UserCreate` 仅用于创建用户，`UserUpdate` 仅用于更新，`UserResponse` 仅用于作为API响应返回用户信息。
- **数据验证**: 模型利用了Pydantic的字段类型（如 `EmailStr`）和 `Field` 函数来进行声明式的数据验证。例如，`username: str = Field(..., min_length=3, pattern="...")` 强制要求 `username` 字段必须提供，长度至少为3，并且匹配指定的正则表达式。这在API的入口处就保证了数据的基本有效性。
- **安全性**: 严格区分了输入和输出模型。例如，`UserCreate` 包含 `password` 字段，但 `UserResponse`（返回给客户端的模型）绝不包含密码字段，防止敏感信息泄露。
- **ORM兼容性**: 响应模型（如 `UserResponse`）中设置了 `model_config = {"from_attributes": True}`。这个配置允许Pydantic模型直接从SQLAlchemy的ORM实例（如 `User` 模型对象）创建，极大地简化了从数据库对象到API响应的转换过程。

## 主要模型分类

### 用户管理模型
- **`UserBase`**: 一个基础模型，包含了用户的通用字段（如 `email`, `full_name`）。其他用户模型都继承自它，以减少代码重复。
- **`UserCreate`**: 用于创建新用户的请求体。它要求 `email`, `password`, `username` 都是必需的，并对它们进行了严格的格式验证。
- **`UserUpdate`**: 用于更新用户信息的请求体。所有字段都是可选的（`Optional`），允许客户端只发送需要修改的字段（部分更新，HTTP PATCH的典型用例）。
- **`UserResponse`**: 作为API响应返回给客户端的用户信息模型。它包含了用户的ID和时间戳等数据库生成的信息，但不包含密码。
- **`User`**: 一个简化的用户模型，也用于API响应，结构与 `UserResponse` 类似。

### 认证流程模型
- **`LoginRequest`**: 用户登录时发送的请求体，包含 `username`（或邮箱）、`password` 和一个可选的 `remember_me` 标志。
- **`Token`**: 成功登录后，API返回的响应体，包含了 `access_token`（访问令牌）、`refresh_token`（刷新令牌）和 `expires_at`（过期时间）。
- **`RefreshTokenRequest`**: 当访问令牌过期后，客户端用于请求新令牌的请求体，只包含 `refresh_token`。
- **`TokenRevocationRequest`**: 用于吊销（注销）一个令牌的请求体。

### 密码重置模型
- **`PasswordResetRequest`**: 用户请求重置密码时发送的请求体，只包含用户的 `email`。
- **`PasswordResetConfirm`**: 用户点击邮件中的链接后，在新页面提交的请求体，包含了重置令牌 `token` 和 `new_password`。
- **`PasswordResetResponse`**: 密码重置成功后返回的简单响应。

### `@register_pydantic_model` 装饰器
- 几个响应模型（`PasswordResetResponse`, `UserResponse`, `User`）被此装饰器标记，以便它们可以被缓存系统 `CacheSerializer` 正确地处理。
