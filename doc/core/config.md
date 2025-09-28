# `config.py` 文档

此文件是整个后端应用程序的配置中心。它使用 `pydantic-settings` 库来从环境变量或 `.env` 文件中加载配置，实现了类型安全和结构化的配置管理。

## 核心功能

1.  **动态环境加载**：通过 `get_env_file()` 函数，根据 `ENVIRONMENT` 环境变量（`production` 或 `development`）自动选择加载 `.env.prod` 或 `.env.dev` 文件。
2.  **结构化配置**：将不同模块的配置项分别组织在不同的 `BaseSettings` 子类中，如 `PostgresSettings`, `SecuritySettings`, `RedisSettings` 等，使得配置结构清晰。
3.  **类型验证**：Pydantic 会在加载配置时自动进行类型检查和验证（例如，`PostgresDsn`, `AnyHttpUrl`, `EmailStr`），确保配置项的格式正确。
4.  **集中管理**：最终所有的配置类都被组合到 `Settings` 主类中，应用程序的其他部分只需要从这个单一的实例 (`settings`) 中导入和使用配置即可。

## 主要配置类

### `PostgresSettings`
- **功能**：管理 PostgreSQL 数据库的连接信息。
- **关键字段**：`HOST`, `USER`, `PASSWORD`, `DB`, `PORT`。
- **自动生成URL**：通过 `@field_validator` 自动将分段的配置组合成一个完整的 `DATABASE_URL` (DSN)。
- **属性**：提供了 `SQLALCHEMY_DATABASE_URL` (异步) 和 `SYNC_DATABASE_URL` (同步，用于Alembic迁移) 两个方便的属性。

### `SecuritySettings`
- **功能**：管理与安全和认证相关的配置。
- **关键字段**：`SECRET_KEY` (用于JWT签名), `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `ALGORITHM`。

### `RabbitMQSettings` / `RedisSettings`
- **功能**：分别管理 RabbitMQ 和 Redis 的连接信息。
- **属性**：提供了 `URL` / `CONNECTION_URL` 属性，用于生成完整的连接字符串。

### `RedisPoolConfig`
- **功能**：这是一个使用 `@dataclass` 定义的配置类，专门用于配置 Redis 连接池的详细参数，如最大/最小连接数、超时、重试策略和健康检查等。
- **注意**：它不是从环境变量加载，而是在 `Settings` 类中作为默认配置实例化。

### `Settings` (主类)
- **功能**：这是所有配置的聚合器。
- **结构**：
    - 包含项目级别的基本配置，如 `PROJECT_NAME`, `ENVIRONMENT`。
    - 将所有其他的配置类（如 `postgres`, `security`, `redis`）作为其属性进行实例化，形成一个嵌套的配置结构。
    - 直接挂载了大量与LLM（大语言模型）和RAG（检索增强生成）相关的配置项，方便直接引用。
- **`dynamic_settings_defaults()` 方法**：
    - **目的**：定义了一组可以被外部（如通过Redis）动态覆盖的默认配置项。
    - **机制**：返回一个字典，其中包含了所有RAG、BM25和查询重写等策略的默认开关和参数。这允许在不重启应用的情况下，实时调整这些功能的行为。

## `settings` 实例

在文件末尾，`settings = Settings()` 创建了 `Settings` 类的一个全局实例。在应用的其他任何地方，都可以通过 `from app.core.config import settings` 来导入并使用这个实例，从而访问所有配置项，例如 `settings.postgres.HOST` 或 `settings.security.SECRET_KEY`。
