# `common.py` 文档

此文件包含一系列通用的、与具体业务无关的辅助函数和工具，旨在提高代码的复用性和一致性。

## `get_current_time() -> datetime`
- **功能**: 获取当前的UTC时间。
- **实现**: 调用 `datetime.utcnow()`。
- **目的**: 在整个应用程序中提供一个统一的、标准的时间源。使用UTC时间是最佳实践，可以避免因服务器时区不同而导致的数据不一致问题。返回的 `datetime` 对象是“朴素的”（naive），不含时区信息，这通常是数据库（如PostgreSQL的 `TIMESTAMP WITHOUT TIME ZONE` 类型）所期望的格式。

## `handle_error(error: Exception, ...)`
- **功能**: 一个统一的错误处理辅助函数，用于将不同类型的原始异常转换为FastAPI能够理解的 `HTTPException`。
- **目的**: 这个函数**已不推荐使用**，因为它通过再次 `raise` 来中断控制流，这在某些复杂的业务逻辑中可能不是期望的行为。更现代的方式是使用全局异常处理器。
- **逻辑**:
    1.  如果传入的 `error` 已经是 `ApiError` 的子类（即我们自定义的业务异常），则直接将其转换为 `HTTPException` 并抛出。
    2.  如果 `error` 是 `ValueError`，则将其包装成一个 `ValidationError`（`ApiError`的子类）再抛出。
    3.  对于所有其他未知的异常，统一作为 `500 Internal Server Error` 抛出。

## `create_exception_handlers() -> Dict`
- **功能**: 创建并返回一个异常处理器字典，该字典可以被FastAPI应用实例用于注册全局异常处理器。
- **目的**: 这是在FastAPI中处理自定义异常的最佳实践。它将特定类型的异常与一个处理函数（Handler）关联起来，当应用中任何地方抛出该类型的异常时，FastAPI会自动调用对应的处理函数来生成一个标准的HTTP响应。
- **处理器**: 
    - **`api_error_handler`**: 
        - **捕获**: `ApiError` 及其所有子类。
        - **行为**: 从异常对象中提取 `status_code` 和 `detail`，并返回一个标准的 `JSONResponse`。
    - **`auth_error_handler`**: 
        - **捕获**: `AuthenticationError` 及其子类。
        - **行为**: 与 `api_error_handler` 类似，但它还会从异常对象中提取 `headers`（通常是 `{"WWW-Authenticate": "Bearer"}`），并将其添加到响应头中，这是符合HTTP认证规范的做法。
- **用法**: 在 `main.py` 中，这个函数返回的字典会被传递给 `FastAPI` 的 `exception_handlers` 参数，例如 `app = FastAPI(exception_handlers=create_exception_handlers())`。
