# `cache_serializer.py` 文档

此文件定义了 `CacheSerializer`，一个静态类，其核心职责是在缓存数据（通常是Python对象）和可以存入Redis的字节流之间进行双向转换。它特别设计用于处理 Pydantic 模型和 SQLAlchemy 模型。

## 核心设计

1.  **类型感知 (Type-Aware)**: 序列化器不是简单地将对象转换为JSON。它在序列化后的数据中注入了元数据字段（`__type__` 和 `__model__`），用于记录原始对象的类型（如 `pydantic` 或 `sqlalchemy`）及其全限定类名（如 `app.modules.auth.schemas.UserRead`）。这使得反序列化时能够精确地重建出原始的对象实例。

2.  **注册表机制 (Registry)**: 
    - `PYDANTIC_MODEL_REGISTRY` 和 `SQLALCHEMY_MODEL_REGISTRY` 是两个全局字典。
    - 为了能够从一个字符串类名（如 `"app.schemas.User"`）重新构造出一个Python类，这个类必须首先被“注册”到相应的注册表中。
    - 提供了 `register_pydantic_model` 和 `register_sqlalchemy_model` 两个装饰器或函数，用于在应用启动时将需要缓存的模型类加入到注册表中。

3.  **支持多种数据类型**: 除了 Pydantic 和 SQLAlchemy 模型，序列化器还支持：
    - **基本类型**: `str`, `int`, `float`, `bool`, `None`。
    - **集合类型**: `list`, `tuple`, `dict`。
    - **嵌套类型**: 能够处理列表中包含Pydantic/SQLAlchemy对象的复杂情况。

## 主要组件

### 注册函数
- **`register_pydantic_model(model_class)`**: 用于注册Pydantic模型。
- **`register_sqlalchemy_model(model_class)`**: 用于注册SQLAlchemy模型。
- **`_fqn(cls)`**: 一个内部辅助函数，用于获取一个类的“全限定名”（Fully Qualified Name），例如 `app.models.User`，这是注册和查找模型的关键。

### `CacheSerializer` 静态类

#### `serialize(obj: Any) -> bytes`
- **功能**: 将一个Python对象序列化为 `bytes`。
- **流程**:
    1.  判断输入对象 `obj` 的类型。
    2.  **对于Pydantic模型**: 使用 `obj.model_dump(mode='json')` 将其转换为字典。
    3.  **对于SQLAlchemy模型**: 使用 `_sqlalchemy_to_dict` 辅助方法，该方法只提取模型的列数据，避免意外加载延迟加载的关联关系，从而提高效率和避免循环引用。
    4.  **对于列表/元组**: 遍历每个元素，并递归地对元素进行序列化，保留其类型信息。
    5.  将处理后的数据与元数据（`__type__`, `__model__`）一起打包成一个字典 `payload`。
    6.  使用 `json.dumps(payload, default=str)` 将 `payload` 字典转换为JSON字符串。`default=str` 是一个重要的降级策略，它可以自动将 `datetime`、`Decimal` 等非原生JSON类型转换为字符串。
    7.  最后，将JSON字符串编码为UTF-8字节流。

#### `deserialize(data: Union[str, bytes]) -> Any`
- **功能**: 将 `bytes` 或 `str` 反序列化为原始的Python对象。
- **流程**:
    1.  将输入的字节流解码并用 `json.loads()` 解析成 `payload` 字典。
    2.  从 `payload` 中提取元数据 `__type__` 和 `__model__`。
    3.  根据 `__type__` 的值，执行相应的反序列化逻辑：
        - **`pydantic`**: 从 `PYDANTIC_MODEL_REGISTRY` 中查找模型类，然后使用 `ModelClass.model_validate(data)` 来重建Pydantic实例。
        - **`sqlalchemy`**: 从 `SQLALCHEMY_MODEL_REGISTRY` 中查找模型类，然后使用 `ModelClass(**data)` 来创建一个新的SQLAlchemy实例。
        - **`list`/`tuple`**: 遍历数据列表，并递归地对每个元素进行反序列化。
        - **`dict`/`primitive`**: 直接返回数据。
    4.  如果找不到对应的注册模型或数据格式无效，则会抛出异常。

## 总结

`CacheSerializer` 是缓存系统的核心组件之一。通过其智能的类型感知和注册表机制，它解决了将复杂的Python业务对象（特别是ORM模型）存入缓存并能准确恢复的难题，极大地增强了缓存系统的通用性和可靠性。
