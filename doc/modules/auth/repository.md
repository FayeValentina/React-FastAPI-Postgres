# `repository.py` (auth) 文档

此文件实现了“仓库模式”（Repository Pattern），定义了 `CRUDUser` 和 `CRUDPasswordReset` 两个类。这些类封装了与用户（`User`）和密码重置（`PasswordReset`）模型相关的、所有与数据库交互的底层逻辑（CRUD - 创建、读取、更新、删除）。

## 设计理念
- **关注点分离 (Separation of Concerns)**: 将数据访问逻辑（如何编写SQLAlchemy查询）与业务逻辑（在Service层或API路由中）分离开来。这使得代码更清晰、更易于测试和维护。
- **封装查询**: 将所有SQLAlchemy的查询语句（如 `select`, `update`, `delete`）封装在仓库方法内部。上层服务只需调用如 `crud_user.get(db, id=1)` 这样的方法，而无需关心底层的SQLAlchemy语法。
- **异常转换**: 仓库层负责捕获底层的数据库异常（如 `IntegrityError`），并将其转换为更具体的、与业务相关的自定义异常（如 `EmailAlreadyRegisteredError`, `DatabaseError`），然后向上层抛出。

## `CRUDUser` 类

这个类处理所有与 `User` 模型相关的数据库操作。

### 主要方法
- **`get(db, id)`**: 根据主键ID获取单个用户。
- **`get_by_email(db, email)`**: 根据邮箱地址获取单个用户。
- **`get_by_username(db, username)`**: 根据用户名获取单个用户。
- **`create(db, obj_in)`**: 创建一个新用户。
    - **前置检查**: 在插入数据前，会先检查邮箱和用户名是否已存在，如果存在则抛出相应的业务异常。
    - **密码哈希**: 在创建 `User` 对象时，会调用 `get_password_hash()` 将明文密码转换为哈希值再存入数据库。
- **`create_with_validation(db, obj_in)`**: 一个增强版的创建方法。
    - **功能**: 在调用 `create` 方法之前，增加了对输入数据的额外验证，如用户名的格式、密码的最小长度、年龄的范围等。如果验证失败，则抛出 `ValidationError`。
- **`update(db, db_obj, obj_in)`**: 更新一个已存在的用户信息。
    - **密码处理**: 如果更新数据中包含了 `password` 字段，它会先将其哈希化，然后再更新到数据库模型中。
- **`delete(db, id)`**: 根据ID删除一个用户。

## `CRUDPasswordReset` 类

这个类处理所有与 `PasswordReset` 模型相关的数据库操作。

### 主要方法
- **`create(db, user_id, ...)`**: 为指定用户创建一个新的密码重置记录。
    - **关键逻辑**: 在创建新令牌之前，它会先调用 `invalidate_user_tokens` 将该用户所有**未使用的**旧令牌全部标记为“已使用”。这确保了在任何时候，一个用户只有一个有效的密码重置链接。
- **`get_by_token(db, token)`**: 根据令牌字符串获取密码重置记录。
- **`use_token(db, token)`**: 将一个令牌标记为“已使用”。这是一个 `UPDATE` 操作，会设置 `is_used = True` 和 `used_at` 时间戳。
- **`invalidate_user_tokens(db, user_id)`**: 将某个用户的所有未使用的令牌批量标记为“已使用”。
- **`cleanup_expired(db, days_old)`**: 一个维护方法，用于清理数据库。
    - **功能**: 删除那些创建时间早于 `days_old` 天，并且已经失效（即已使用或已过期）的密码重置记录，防止 `password_resets` 表无限增长。

## 全局实例
- `crud_user = CRUDUser()`
- `crud_password_reset = CRUDPasswordReset()`

文件末尾创建了这两个仓库类的全局单例实例，方便在应用的其他地方直接导入和使用。
