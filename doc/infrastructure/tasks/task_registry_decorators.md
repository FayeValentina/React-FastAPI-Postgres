# `task_registry_decorators.py` 文档

此文件实现了一个强大的、自描述的任务注册系统。它不仅能注册后台任务，还能通过Python的类型注解（Type Annotations）和 `inspect` 模块，自动提取任务函数的参数信息、文档字符串以及UI提示，为动态生成前端表单和API文档提供了数据基础。

## 核心组件

### `TASKS` 全局注册表
- **定义**: `TASKS: Dict[str, Dict] = {}`
- **功能**: 这是一个全局字典，是所有任务信息的“单一事实来源”。
- **结构**: 
    - **键 (Key)**: 任务的唯一名称（例如 `"reddit_scraper"`），由 `@task` 装饰器提供。
    - **值 (Value)**: 一个字典，包含了关于该任务的所有元数据，如工作函数名、队列名、参数详情、文档字符串等。

### `@task(name: str, queue: str)` 装饰器
- **功能**: 这是任务注册的入口点。任何希望被系统管理的后台任务函数都必须使用此装饰器。
- **流程**:
    1.  当装饰器被应用到一个函数上时，它首先调用 `_extract_parameter_info` 来解析该函数的签名。
    2.  然后，它将任务的唯一名称 (`name`)、队列名 (`queue`)、函数本身 (`func`)、解析出的参数信息 (`parameters`) 以及函数的文档字符串 (`doc`) 打包成一个字典。
    3.  最后，它将这个字典存入全局的 `TASKS` 注册表中，以 `name` 为键。

### `_extract_parameter_info(func: Callable)` 内部函数
- **功能**: 这是该模块最核心、最复杂的部分，负责“读取”一个函数的签名并提取其参数的详细信息。
- **实现**: 
    1.  使用 `inspect.signature(func)` 获取函数的参数列表。
    2.  遍历每个参数，提取其名称、类型注解、默认值和是否必需等基本信息。
    3.  **`Annotated` 类型支持**: 它能够特别处理 `typing.Annotated`。例如，对于 `param: Annotated[str, {"label": "帖子ID", "placeholder": "请输入帖子的URL"}]`，它能：
        - 调用 `_unwrap_annotated` 分离出基础类型 (`str`) 和元数据 (`{"label": ...}`）。
        - 调用 `_merge_ui_meta` 将元数据合并成一个用于UI展示的字典。
    4.  **UI提示推断**: 调用 `_infer_ui_from_type`，根据参数的类型和名称进行启发式推断。例如：
        - `Literal["A", "B"]` 或 `Enum` 类型会被自动推断为UI中的下拉选择框 (`select`)。
        - 参数名以 `email` 结尾的会被推断为 `email` 输入框。
        - `context`、`config_id` 或 FastAPI 的 `Depends` 等参数会被自动标记为 `exclude_from_ui`，不在前端表单中显示。
    5.  **合并UI信息**: 它会将 `Annotated` 中显式提供的UI元信息覆盖在启发式推断的结果之上，实现了灵活的配置。
    6.  **类型解析**: 调用 `_parse_type_annotation_to_dict` 将复杂的类型注解（如 `Optional[List[str]]`）解析成一个结构化的字典（如 `{"type": "optional", "args": [{"type": "list", "args": [{"type": "str"}]}]}`），方便前端进行处理。

### `auto_discover_tasks(package_path: str)`
- **功能**: 这是一个自动发现机制，用于在应用启动时自动导入指定包路径下的所有模块。
- **目的**: 开发者在 `app.modules.tasks.workers` 目录下创建新的任务文件后，无需手动在任何地方导入它。只要文件中的任务函数被 `@task` 装饰器标记，`auto_discover_tasks` 在启动时就会自动扫描并执行这些模块文件，从而触发装饰器逻辑，完成任务的自动注册。

### 访问函数
文件还提供了一系列便捷的访问函数，用于从 `TASKS` 注册表中查询信息，例如：
- `get_function(task_type)`: 获取任务的可执行函数。
- `get_parameters(task_type)`: 获取任务的参数信息列表。
- `list_all_tasks()`: 列出所有已注册任务的完整信息。

## 总结

这个任务注册系统是一个非常优雅的元编程（Metaprogramming）实践。它通过装饰器和类型注解，将任务的定义、实现和其元数据（如何配置、如何展示）紧密地耦合在一起，同时又将任务的注册过程与应用的主逻辑解耦。这不仅使得任务管理变得高度自动化，还为构建动态、数据驱动的用户界面提供了强大的支持。
