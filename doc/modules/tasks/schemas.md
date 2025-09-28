# `schemas.py` (tasks) 文档

此文件是任务和系统监控模块的Pydantic模型中心，定义了大量用于API请求/响应验证和序列化的数据结构。这些模型覆盖了从任务配置、执行历史、调度管理到系统健康状态和仪表盘的方方面面。

## 任务配置 (Config) 相关模型

- **`TaskConfigBase`**: 定义了任务配置的核心字段，如 `name`, `task_type`, `parameters` 等。
- **`TaskConfigCreate`**: 用于创建新任务配置的请求体模型。它包含了自定义的 `@field_validator`，用于根据 `task_type` 和 `scheduler_type` 验证 `parameters` 和 `schedule_config` 字段的内部结构是否正确。
- **`TaskConfigUpdate`**: 用于部分更新任务配置的请求体模型，所有字段都是可选的。
- **`TaskConfigQuery`**: 定义了查询任务配置列表时的所有可用参数，如名称搜索、分页、排序等。
- **`TaskConfigResponse`**: 任务配置的基础响应模型，包含了数据库中的所有字段。
- **`TaskConfigDetailResponse`**: 继承自 `TaskConfigResponse`，并额外包含了 `recent_history` 和 `stats`，用于获取单个配置的详细信息。
- **`TaskConfigListResponse`**: 用于返回任务配置分页列表的响应模型。

## 任务执行 (Execution) 相关模型

- **`TaskExecutionInfo`**: 任务执行历史记录的基础模型。
- **`TaskExecutionDetailInfo`**: 继承自 `TaskExecutionInfo`，并增加了 `config_name`, `task_type`, `error_traceback` 等更详细的信息。
- **`ConfigExecutionsResponse`**: 用于返回某个特定配置下的执行历史列表。
- **`RecentExecutionsResponse` / `FailedExecutionsResponse`**: 分别用于返回最近的或失败的执行历史列表。
- **`ExecutionCleanupResponse`**: 清理旧执行记录API的响应模型。

## 调度管理 (Schedule) 相关模型

- **`ScheduleOperationResponse`**: 对单个调度实例（`schedule_id`）执行操作（如暂停、恢复）后的响应模型。
- **`ScheduledJobInfo`**: 表示从 `TaskIQ` 中查询到的单个调度任务的信息。
- **`ScheduleHistoryEvent`**: 表示在Redis中记录的单个历史事件（如 `task_registered`）。
- **`ScheduleListResponse`**: 返回 `TaskIQ` 中所有调度任务列表的响应模型。
- **`ScheduleHistoryResponse`**: 返回某个调度实例的历史事件列表。
- **`ScheduleSummaryResponse`**: 返回调度器状态的全局摘要信息（如活跃、暂停的实例数量）。
- **`ScheduleInstanceInfo` / `ScheduleInstanceResponse`**: 用于表示从Redis中合成的单个调度实例的完整信息（状态、元数据、历史）。

## 系统监控与信息 (System) 相关模型

- **`TaskInfo` & `TaskParameterInfo`**: **核心模型**。这两个模型用于结构化地表示一个已注册任务的完整元信息。`TaskParameterInfo` 详细描述了任务的每个参数，包括其名称、类型、是否必需，以及最重要的 `ui` 字段。`ui` 字段（`UIMetaInfo` 模型）包含了由后端自动推断或通过 `Annotated` 注解指定的、用于前端动态生成表单的所有UI提示（如控件类型、标签、占位符、选项等）。
- **`TaskInfoResponse`**: 返回所有已注册任务及其参数详细信息的API的响应模型。
- **`SystemStatusResponse`**: 返回系统各个方面（调度器、数据库、Redis、任务统计）当前状态的快照。
- **`SystemHealthResponse`**: 返回系统各组件健康检查结果的响应模型。
- **`SystemEnumsResponse`**: 向前端提供系统中使用的各种枚举值（如调度类型、任务类型），方便前端构建下拉菜单等UI元素。
- **`SystemDashboardResponse`**: 为前端仪表盘提供聚合后的统计数据，如最近7天/30天的执行统计等。

## 系统清理 (Cleanup) 相关模型

- **`OrphanListResponse`**: 返回“孤儿”调度实例列表的响应模型。
- **`OrphanCleanupResponse`**: 清理孤儿实例API的响应模型。
- **`CleanupLegacyResponse`**: 清理旧版遗留数据API的响应模型。

## 总结

这个 `schemas.py` 文件是整个后端应用，特别是其动态和可配置特性的基石。通过Pydantic的严格验证和精心设计的模型结构，它确保了API接口的健壮性和可靠性。特别是 `TaskInfo` 和 `TaskParameterInfo` 模型，它们体现了“后端驱动UI”的设计思想，使得前端能够根据API返回的元数据动态渲染出复杂的配置表单，极大地提高了开发效率和灵活性。
