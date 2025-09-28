# `models.py` (auth) 文档

此文件定义了与用户认证和授权相关的SQLAlchemy ORM模型，即数据库中的 `users` 和 `password_resets` 表所对应的Python类。

## `User(Base)` 模型

这个类代表了系统中的一个用户，映射到 `users` 表。

### `@register_sqlalchemy_model`
- **装饰器**: 这个类被 `@register_sqlalchemy_model` 装饰器标记。
- **目的**: 将 `User` 模型注册到缓存序列化器 (`CacheSerializer`) 中。这使得 `User` 的ORM实例可以被缓存系统正确地序列化和反序列化。

### 主要字段
- `id: Mapped[int]`: 用户的主键ID。
- `email: Mapped[str]`: 用户的电子邮箱，唯一且有索引，用于登录和通信。
- `username: Mapped[str]`: 用户的唯一用户名，有索引，用于登录。
- `hashed_password: Mapped[str]`: 存储用户密码的哈希值，绝不存储明文密码。
- `full_name: Mapped[Optional[str]]`: 用户的全名（可选）。
- `is_active: Mapped[bool]`: 一个布尔标志，用于表示账户是否被激活。可以用于实现账户的软删除或禁用功能。
- `is_superuser: Mapped[bool]`: 一个布尔标志，表示用户是否为管理员，拥有特殊权限。
- `created_at` / `updated_at`: 时间戳字段，使用 `server_default` 和 `server_onupdate`，让数据库自动管理记录的创建和更新时间。

### 关联关系
- `password_resets: Mapped[List["PasswordReset"]]`: 定义了与 `PasswordReset` 模型的一对多关系。这意味着一个用户可以有多个密码重置记录。
    - `back_populates="user"`: 在 `PasswordReset` 模型中建立反向关系。
    - `cascade="all, delete-orphan"`: 级联操作。当一个 `User` 对象被删除时，所有与之关联的 `PasswordReset` 记录也会被自动删除。

## `PasswordReset(Base)` 模型

这个类代表了一次密码重置请求，映射到 `password_resets` 表。

### 主要字段
- `id: Mapped[str]`: 主键，使用 `uuid4` 生成一个唯一的字符串ID。
- `user_id: Mapped[int]`: 外键，关联到 `users` 表的 `id`，指明这次重置请求属于哪个用户。
- `token: Mapped[str]`: 一个唯一的、随机生成的、用于验证密码重置请求的令牌。
- `is_used: Mapped[bool]`: 标志位，表示这个重置令牌是否已经被使用过。
- `expires_at: Mapped[datetime]`: 令牌的过期时间。
- `used_at: Mapped[Optional[datetime]]`: 令牌被使用的时间（可选）。

### 属性 (Properties)
- `@property is_expired(self) -> bool`: 一个计算属性，通过比较当前时间和 `expires_at` 字段，动态地判断令牌是否已过期。
- `@property is_valid(self) -> bool`: 一个计算属性，综合判断令牌是否仍然有效（即**未被使用**且**未过期**）。

### 类方法 (Class Method)
- `@classmethod create(cls, user_id, token, ...)`: 一个工厂方法，用于方便地创建一个新的 `PasswordReset` 实例。它会自动计算 `expires_at` 过期时间（默认为1小时后）。
