# `logging.py` 文档

此文件定义了 `RequestResponseLoggingMiddleware`，一个用于详细记录HTTP请求和响应信息的FastAPI中间件。

## `RequestResponseLoggingMiddleware` 类

这是一个功能强大的中间件，用于监控API的流量，记录每个请求的详细信息、对应的响应以及处理过程中发生的任何错误。它使用 `loguru` 库进行结构化日志记录。

### `__init__(self, app, ...)`

构造函数，用于配置日志中间件的行为。

- **参数**：
    - `log_request_body`: 是否记录请求体，默认为 `True`。
    - `log_response_body`: 是否记录响应体，默认为 `True`。
    - `max_body_length`: 记录的请求/响应体的最大长度，默认为 `1024` 字符。
    - `exclude_paths`: 不需要记录日志的路径列表（如 `/docs`, `/openapi.json`）。
    - `exclude_extensions`: 不需要记录日志的文件扩展名（如 `.css`, `.js`）。

### `async dispatch(self, request, call_next)`

中间件的核心逻辑，处理每个进入的请求。

- **功能**：
    1.  为每个请求生成一个唯一的 `request_id`，并将其存储在 `request.state` 中，以便在整个请求生命周期中跟踪。
    2.  调用 `_should_skip_logging` 检查是否应跳过当前请求的日志记录。
    3.  记录请求开始时间，并调用 `_collect_request_info` 收集请求的详细信息。
    4.  执行 `await call_next(request)` 来处理请求并获取响应。
    5.  计算总处理时间，并调用 `_collect_response_info` 收集响应的详细信息。
    6.  调用 `_log_request_response` 将收集到的所有信息格式化并输出到日志。
    7.  在响应头中添加 `X-Process-Time` 和 `X-Request-ID` 以方便调试。
- **错误处理**：如果请求处理过程中发生异常，它会捕获异常，记录包括错误信息在内的日志，然后重新抛出异常。

### `_should_skip_logging(self, request)`

判断是否应跳过当前请求的日志记录。

- **逻辑**：检查请求的路径是否匹配 `exclude_paths` 列表中的路径或 `exclude_extensions` 列表中的文件扩展名。

### `_collect_request_info(self, request)`

异步方法，用于从请求对象中收集详细信息。

- **收集内容**：方法、URL、路径、路径参数、查询参数、请求头和客户端IP/端口。
- **安全过滤**：会自动过滤掉请求头中的 `Authorization` 和 `Cookie` 等敏感信息。
- **请求体**：如果配置了 `log_request_body`，它会异步读取请求体，并调用 `_get_request_body` 进行处理。

### `_get_request_body(self, request)`

安全地读取和解析请求体。

- **功能**：
    - 它能处理不同 `Content-Type` 的请求，如 `application/json`, `application/x-www-form-urlencoded`, `multipart/form-data`。
    - 对于JSON格式的请求体，它会调用 `_filter_sensitive_data` 过滤掉密码、令牌等敏感字段。
    - 对于非文本或二进制数据，它会记录为摘要信息（如 `[Binary data, length: ...]`）。

### `_collect_response_info(self, response, duration)`

从响应对象中收集详细信息。

- **收集内容**：状态码、处理时长、响应头。
- **响应体**：如果配置了 `log_response_body` 且响应不是流式传输（streaming），它会读取响应体内容。对于JSON响应，同样会进行敏感数据过滤。

### `_truncate_body(self, body)`

如果请求或响应体超过了 `max_body_length`，则进行截断，并在末尾添加 `... [truncated]` 标记。

### `_filter_sensitive_data(self, data)`

递归地遍历字典或列表，查找并过滤掉包含敏感关键词（如 `password`, `token`, `secret` 等）的字段值，将其替换为 `[FILTERED]`。

### `_log_request_response(self, ...)`

将所有收集到的信息格式化成一个美观、易于阅读的多行日志消息，并根据响应的状态码（如 2xx, 4xx, 5xx）选择合适的日志级别（`INFO`, `WARNING`, `ERROR`）进行记录。
