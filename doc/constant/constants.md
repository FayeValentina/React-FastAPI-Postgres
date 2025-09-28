# `constants.py` 文档

此文件用于定义整个应用程序中可以复用的常量，主要包括HTTP状态码和标准化的错误消息。

## `StatusCode` 类

这个类将常用的HTTP状态码封装成易于理解的常量。它直接引用了 `fastapi.status` 中定义的值。

- **目的**：
    - 提高代码的可读性，例如使用 `StatusCode.NOT_FOUND` 而不是硬编码的数字 `404`。
    - 确保整个应用中状态码的一致性。

- **示例**：
    - `OK = 200`
    - `CREATED = 201`
    - `UNAUTHORIZED = 401`
    - `INTERNAL_SERVER_ERROR = 500`

## `ErrorMessages` 类

这个类集中定义了应用中所有可能返回给用户的标准错误消息字符串。

- **目的**：
    - **国际化（i18n）准备**：将所有面向用户的字符串集中在一个地方，为未来的多语言支持打下基础。
    - **一致性**：确保相同的错误场景在应用的不同部分返回完全相同的错误信息。
    - **可维护性**：当需要修改某条错误消息时，只需在此处修改一次。

- **分类**：
    - **认证相关**：如 `AUTHENTICATION_FAILED`, `INVALID_CREDENTIALS`。
    - **用户相关**：如 `USER_NOT_FOUND`, `EMAIL_ALREADY_REGISTERED`。
    - **资源相关**：如 `RESOURCE_NOT_FOUND`。
    - **验证相关**：如 `VALIDATION_ERROR`, `PASSWORD_TOO_SHORT`。
    - **系统相关**：如 `DATABASE_ERROR`, `INTERNAL_ERROR`。
