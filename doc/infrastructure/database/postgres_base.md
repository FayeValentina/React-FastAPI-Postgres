# `postgres_base.py` 文档

此文件是与PostgreSQL数据库交互的基础。它负责初始化SQLAlchemy的核心组件，包括引擎（Engine）、会话工厂（Session Factory）以及一个用于FastAPI依赖注入的会话生成器。

## `Base` 类
- **定义**: `class Base(DeclarativeBase):`
- **功能**: 这是一个所有SQLAlchemy ORM模型（即数据库表对应的Python类）都必须继承的声明性基类。
- **自动表名**: 通过 `@declared_attr` 装饰器，它实现了一个 `__tablename__` 的自动生成逻辑，即任何继承自 `Base` 的类，其对应的数据库表名都会自动设置为类名的小写版本（例如，`UserModel` 类会对应 `usermodel` 表）。

## `engine`
- **定义**: `create_async_engine(...)`
- **功能**: 这是SQLAlchemy的异步引擎实例，是应用程序与数据库进行所有通信的核心接口。
- **配置**: 
    - `settings.postgres.SQLALCHEMY_DATABASE_URL`: 从配置文件中读取异步的数据库连接URL。
    - `echo=settings.DB_ECHO_LOG`: 根据配置决定是否在控制台打印所有执行的SQL语句，非常便于调试。
    - `pool_pre_ping=True`: 开启连接池的“预检测”功能，确保每次从连接池中获取的连接都是有效的，避免因数据库重启等原因导致的连接失效问题。

## `_configure_pgvector` 事件监听器
- **定义**: `@event.listens_for(engine.sync_engine, "connect", ...)`
- **功能**: 这是一个SQLAlchemy事件监听器，它会在**每次**与数据库建立新连接时触发。
- **目的**: 专门为 `pgvector` 扩展设置运行时参数。它会从动态配置服务中获取最新的 `ivfflat.probes` 值，并通过 `SET ivfflat.probes = ...` SQL命令将其应用到当前数据库连接上。这允许在不重启应用的情况下，动态调整向量索引的搜索性能。
- **异常安全**: 监听器中的逻辑被包裹在 `try...except` 中，并且有意地“吞掉”了异常。这是为了防止在设置失败（例如，数据库用户权限不足或`pgvector`版本不支持）时导致整个应用启动失败。

## `AsyncSessionLocal`
- **定义**: `async_sessionmaker(...)`
- **功能**: 这是一个异步会话工厂。当需要与数据库进行交互时，就从这个工厂中获取一个 `AsyncSession` 实例。
- **配置**: 
    - `expire_on_commit=False`: 一个非常重要的设置。它防止了在会话提交（`commit`）后，所有从该会话中加载的ORM对象实例都变为“过期”状态。这使得我们可以在API响应中安全地返回这些对象，而无需重新查询。

## `get_async_session()`
- **功能**: 这是一个FastAPI的依赖项（Dependency），它遵循“一个请求一个会话”的最佳实践。
- **流程**: 
    1.  从 `AsyncSessionLocal` 工厂创建一个新的 `AsyncSession`。
    2.  使用 `yield` 将这个会话提供给API路径操作函数。
    3.  在路径操作函数执行完毕后，代码会继续执行：
        - 如果没有发生异常，则调用 `await session.commit()` 提交所有数据库更改。
        - 如果发生了任何异常，则调用 `await session.rollback()` 回滚所有更改，确保数据的一致性。
        - 无论成功与否，最后都会调用 `await session.close()` 将会话关闭并释放数据库连接。

这个函数是确保数据库操作既安全又高效的关键所在。
