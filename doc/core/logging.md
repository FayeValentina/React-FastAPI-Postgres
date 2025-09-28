# `logging.py` 文档

此文件负责配置整个应用程序的日志系统。它使用 `loguru` 库来提供功能强大且易于配置的结构化日志记录，并能拦截和统一处理来自标准 `logging` 模块的日志。

## 核心组件

### `InterceptHandler(logging.Handler)`
- **功能**：这是一个自定义的日志处理器，继承自标准库的 `logging.Handler`。
- **目的**：它的核心作用是**拦截**所有发送到标准 `logging` 模块的日志记录（例如来自 `uvicorn`, `fastapi`, `sqlalchemy` 等库的日志），并将它们重定向到 `loguru` 的处理器中。
- **实现**：在 `emit` 方法中，它获取原始日志记录，并使用 `logger.opt()` 将其重新记录到 `loguru` 系统中，同时保留原始的日志级别、异常信息和调用栈深度。

### `setup_logging(...)`
- **功能**：这是配置日志系统的入口函数，通常在应用启动时调用。
- **参数**：
    - `log_level`: 日志级别 (e.g., "INFO", "DEBUG")。
    - `json_logs`: 是否以JSON格式输出日志。
    - `log_file`: 日志文件的路径。
    - 这些参数可以被直接传入，但如果未提供，它们会从 `app.core.config.settings` 中读取默认值。

- **配置步骤**：
    1.  **清空并设置根Logger**：移除所有 `logging` 模块的默认处理器，并将根 logger 的处理器设置为我们自定义的 `InterceptHandler`。
    2.  **拦截目标模块**：明确指定要拦截日志的模块列表（如 `uvicorn`, `fastapi`），并将它们的处理器也设置为 `InterceptHandler`，同时设置 `propagate = False` 防止日志被重复记录。
    3.  **配置 `loguru` handlers**：这是最核心的部分，它定义了日志的最终去向和格式。
        - **多个 Sink**：配置了多个 `sink`（目的地），都指向 `sys.stdout`（控制台），但使用不同的 `filter` 和 `format`。
        - **动态格式**：
            - 如果日志记录中包含 `request_id`（由日志中间件添加），则使用包含该ID的详细格式。
            - 如果没有 `request_id`，则使用一个较简单的格式。
            - 对于来自 `RequestResponseLoggingMiddleware` 的日志，使用一个极简的格式，因为它本身已经包含了完整的格式化信息。
        - **JSON支持**：根据 `json_logs` 参数，可以自动将所有日志输出为JSON格式。
        - **文件日志**：如果提供了 `log_file` 路径，会自动添加一个文件 `sink`，并配置了日志轮换（每天）、保留期限（30天）和压缩（zip）。
    4.  **应用配置**：最后调用 `logger.configure(handlers=handlers)` 使所有配置生效。

## 总结

这个模块通过 `InterceptHandler` 巧妙地将标准日志系统与 `loguru` 结合起来，实现了对整个应用（包括所有第三方库）日志的集中控制。开发者可以方便地通过环境变量来切换日志级别、格式（文本或JSON）以及是否将日志写入文件，而无需修改代码。
