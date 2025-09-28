# `schemas.py` (admin_settings) 文档

此文件定义了与“管理员设置”功能相关的Pydantic模型。这些模型主要用于API的数据验证和序列化，确保前端和后端之间交换的数据格式正确、类型安全。

## `AdminSettingsResponse(BaseModel)`
- **用途**: 作为 `/api/v1/admin/settings` GET 请求的响应体模型。
- **字段**:
    - `defaults: Dict[str, Any]`: 一个字典，包含了从 `config.py` 中读取的、所有动态设置的**默认值**。
    - `overrides: Dict[str, Any]`: 一个字典，包含了当前存储在Redis中的、所有被管理员**覆盖**的设置项。
    - `effective: Dict[str, Any]`: 一个字典，包含了最终在应用中**生效**的设置项（即 `defaults` 和 `overrides` 合并后的结果）。
    - `updated_at: datetime | None`: 上次设置被修改的时间戳。
    - `redis_status: Literal["ok", "unavailable"]`: 一个表示Redis连接状态的标志，方便前端了解配置是否从缓存中成功加载。

## `AdminSettingsUpdate(BaseModel)`
- **用途**: 作为 `/api/v1/admin/settings` PATCH 请求的请求体模型，用于更新一个或多个动态设置项。
- **设计**:
    - **部分更新**: 所有字段都被定义为可选的 (`| None = None`)，这意味着前端可以只发送需要修改的字段，而无需发送完整的配置对象。
    - **严格验证**: 
        - `model_config = ConfigDict(extra="forbid")`: Pydantic配置，禁止在请求体中包含此模型未定义的任何额外字段，防止意外的或恶意的参数注入。
        - **范围约束**: 大部分字段都使用了 `Field` 函数来定义严格的验证规则。例如，`RAG_TOP_K: int | None = Field(None, ge=1, le=100)` 确保了 `RAG_TOP_K` 的值如果被提供，必须是一个介于1和100之间的整数。这在API层面就保证了数据的有效性，防止无效的配置值进入系统。

## `AdminSettingsResetRequest(BaseModel)`
- **用途**: 作为 `/api/v1/admin/settings/reset` POST 请求的请求体模型，用于将一个或多个设置项重置为其默认值。
- **字段**:
    - `keys: list[str] | None`: 一个可选的字符串列表。
        - **如果提供了列表**: 服务将只重置列表中指定的那些键。
        - **如果该字段被省略或为 `null`**: 服务将清除所有在Redis中的覆盖值，使所有动态设置都恢复到其默认状态。
