# `email_service.py` 文档

此文件定义了 `EmailService` 类，一个专门用于发送电子邮件的服务。它封装了与SMTP服务器交互的细节，并提供了发送特定类型邮件（如密码重置邮件）的便捷方法。

## `EmailService` 类

### `__init__(self)`
- **功能**: 构造函数，在实例化服务时，从 `app.core.config.settings` 中读取所有与SMTP相关的配置，并将其存储为实例属性。
- **配置项**: 
    - `SMTP_SERVER`: SMTP服务器地址。
    - `SMTP_PORT`: SMTP服务器端口。
    - `USERNAME`: 登录用户名。
    - `PASSWORD`: 登录密码。
    - `FROM_EMAIL`: 发件人邮箱地址。
    - `USE_TLS`: 是否使用TLS加密连接。

### `send_password_reset_email(self, to_email, reset_token, user_name)`
- **功能**: 一个高级方法，专门用于发送密码重置邮件。
- **流程**:
    1.  根据传入的 `reset_token` 和配置文件中的 `FRONTEND_URL`，构造一个完整的前端密码重置页面链接。
    2.  调用 `_generate_reset_email_html` 方法生成美观的HTML邮件内容。
    3.  调用底层的 `_send_email` 方法将邮件发送出去。
- **异常处理**: 捕获所有异常，并在失败时记录错误日志，返回 `False`。

### `_send_email(self, to_email, subject, html_content, ...)`
- **功能**: 一个通用的、底层的邮件发送方法。
- **异步实现**: 使用 `aiosmtplib` 库来异步发送邮件，这可以防止在等待SMTP服务器响应时阻塞FastAPI的事件循环，从而提高应用的并发性能。
- **邮件构造**: 
    - 使用标准库 `email.mime` 来创建一个 `MIMEMultipart('alternative')` 类型的邮件对象。这允许邮件同时包含HTML版本和纯文本版本（如果提供的话），邮件客户端会根据自身能力选择合适的版本显示。
    - 设置邮件的 `Subject` (主题), `From` (发件人), `To` (收件人)。
- **发送**: 调用 `aiosmtplib.send()` 来执行实际的发送操作。

### `_generate_reset_email_html(self, user_name, reset_url)`
- **功能**: 一个私有辅助方法，用于生成密码重置邮件的HTML模板字符串。
- **内容**: 包含一个欢迎信息、一个可点击的“重置密码”按钮、备用的可复制链接以及重要的安全提示。

## 全局实例

- `email_service = EmailService()`: 创建了一个全局唯一的服务实例，供应用的其他部分（如用户认证模块）调用。
