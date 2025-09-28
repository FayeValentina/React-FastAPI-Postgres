# `security.py` 文档

此文件包含了与安全相关的核心功能，主要集中在密码哈希和JWT（JSON Web Tokens）的创建与验证。

## `pwd_context`
- **定义**：`CryptContext(schemes=["bcrypt"], deprecated="auto")`
- **功能**：这是一个 `passlib` 库的实例，专门用于处理密码的哈希和验证。
- **算法**：配置为使用 `bcrypt` 算法，这是一种公认的安全哈希算法，能够有效抵抗暴力破解和彩虹表攻击。

## 主要函数

### `get_password_hash(password: str) -> str`
- **功能**：接收一个明文密码，并使用 `pwd_context.hash()` 方法返回其 `bcrypt` 哈希值。
- **用途**：在用户注册或重置密码时，用于将用户的明文密码安全地存储到数据库中。

### `verify_password(plain_password: str, hashed_password: str) -> bool`
- **功能**：接收一个明文密码和一个哈希过的密码，并使用 `pwd_context.verify()` 方法来比较它们是否匹配。
- **用途**：在用户登录时，用于验证用户输入的密码是否与数据库中存储的哈希密码一致。

### `create_access_token(subject: str | Any, ...) -> str`
- **功能**：创建一个JWT访问令牌（Access Token）。
- **令牌内容 (Payload)**：
    - `exp`: 过期时间。默认从配置中读取（例如30分钟）。
    - `sub`: 令牌的主题，通常是用户的ID。
    - `iat`: 令牌的签发时间。
    - `type`: 明确标记为 `access_token`。
    - `jti`: 一个唯一的UUID，可用于实现令牌吊销列表。
- **签名**：使用 `settings.security.SECRET_KEY` 和 `settings.security.ALGORITHM` (如 HS256) 进行签名。

### `create_refresh_token(subject: str | Any, ...) -> str`
- **功能**：创建一个JWT刷新令牌（Refresh Token）。
- **与访问令牌的区别**：
    - **过期时间**：通常有更长的有效期（例如7天），从配置中读取。
    - **类型**：Payload 中的 `type` 字段被标记为 `refresh_token`。
- **用途**：当访问令牌过期后，客户端可以使用刷新令牌来获取一个新的访问令牌，而无需用户重新登录。

### `verify_token(token: str) -> Tuple[bool, Optional[Dict], Optional[str]]`
- **功能**：验证一个给定的JWT令牌的有效性。
- **验证内容**：检查令牌的签名是否正确以及是否在有效期内。
- **返回值**：一个元组 `(is_valid, payload, error_type)`
    - `is_valid` (bool): 令牌是否有效。
    - `payload` (dict | None): 如果有效，则返回解码后的令牌载荷。
    - `error_type` (str | None): 如果无效，返回错误类型。特别地，它能区分 `expired` (已过期) 和 `invalid` (其他所有错误，如签名无效)。

### `create_token_pair(subject: str | Any, remember_me: bool) -> Tuple[str, str, datetime]`
- **功能**：一个便捷函数，用于一次性创建访问令牌和刷新令牌对。
- **`remember_me` 参数**：如果用户选择了“记住我”，访问令牌的有效期会被延长（例如，从30分钟延长到1天），以提供更长的登录会话时间。
- **返回值**：返回一个包含访问令牌、刷新令牌和访问令牌确切过期时间的元组。
