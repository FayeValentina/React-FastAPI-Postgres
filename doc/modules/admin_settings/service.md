# `service.py` (admin_settings) 文档

此文件定义了 `AdminSettingsService`，它封装了管理动态管理员设置的业务逻辑。这个服务作为API路由（Controller层）和底层 `DynamicSettingsService`（基础设施层）之间的桥梁。

## `AdminSettingsService` 类

### `read_settings(self, dynamic_settings_service)`
- **功能**: 读取所有与动态设置相关的信息，并将其组装成 `AdminSettingsResponse` 模型以供API返回。
- **流程**:
    1.  从 `dynamic_settings_service` 中获取 `defaults`（默认值）和 `effective`（最终生效的值）。
    2.  尝试从Redis中获取 `overrides`（被覆盖的值）。如果失败（例如Redis连接不上），则将 `redis_status` 标记为 `unavailable`。
    3.  获取设置的元数据，特别是 `updated_at`（最后更新时间）。
    4.  调用 `_normalize_overrides` 对覆盖值进行“规范化”处理。这个步骤会移除那些与默认值相同的覆盖项，使得前端只看到真正被修改过的设置，界面更清晰。
    5.  将所有收集到的信息填充到 `AdminSettingsResponse` 模型中并返回。

### `update_settings(self, payload, dynamic_settings_service)`
- **功能**: 处理更新动态设置的请求。
- **流程**:
    1.  接收一个 `AdminSettingsUpdate` 类型的 `payload`（已由Pydantic验证过）。
    2.  调用 `payload.model_dump(exclude_none=True)` 来创建一个只包含被实际提供的、非`null`值的字典。这确保了只有用户想要修改的设置才会被更新。
    3.  如果 `updates` 字典为空，则抛出一个 `400 Bad Request` 错误。
    4.  将 `updates` 字典传递给 `dynamic_settings_service.update()`，由底层服务负责将其持久化到Redis并更新内存缓存。
    5.  最后，再次调用 `self.read_settings()` 来获取并返回更新后的最新设置状态。

### `reset_settings(self, dynamic_settings_service, keys)`
- **功能**: 处理重置动态设置的请求。
- **流程**:
    1.  接收一个可选的 `keys` 列表。
    2.  **如果 `keys` 列表存在**: 调用 `dynamic_settings_service.reset(keys)`，只重置指定的设置项。
    3.  **如果 `keys` 列表不存在**: 调用 `dynamic_settings_service.reset()`，重置所有设置项。
    4.  如果在重置过程中 `dynamic_settings_service` 抛出了 `ValueError`（例如，因为提供了无效的键名），则捕获该异常并将其转换为一个 `400 Bad Request` 的 `HTTPException`。
    5.  最后，同样调用 `self.read_settings()` 来获取并返回重置后的最新状态。

### 内部辅助方法
- **`_normalize_overrides(overrides, defaults)`**: 比较覆盖值和默认值，只返回那些与默认值不同的覆盖项。
- **`_parse_updated_at(raw)`**: 一个健壮的解析函数，能将不同格式（`datetime` 对象或ISO格式字符串）的输入统一转换为 `datetime` 对象。

## 全局实例
- `admin_settings_service = AdminSettingsService()`: 创建了一个全局唯一的服务实例，供API路由层调用。
