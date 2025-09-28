# `repository.py` (tasks) 文档

此文件实现了 `CRUDTaskConfig` 和 `CRUDTaskExecution` 两个仓库类，它们封装了与任务配置（`TaskConfig`）和任务执行历史（`TaskExecution`）模型相关的所有数据库交互逻辑。

## `CRUDTaskConfig` 类

这个类负责管理任务配置模板的增删改查和统计。

### 主要方法
- **`get(db, config_id)`**: 根据ID获取单个任务配置。
- **`get_by_query(db, query)`**: 一个强大的动态查询方法。它接收一个 `TaskConfigQuery` Pydantic模型作为参数，并根据其中的字段（如 `name_search`, `task_type`, `order_by`, `page` 等）动态地构建SQLAlchemy查询。这使得API可以支持复杂的前端筛选、排序和分页功能。
- **`create(db, obj_in)`**: 根据传入的 `TaskConfigCreate` Pydantic模型，创建一个新的 `TaskConfig` 记录。
- **`update(db, db_obj, obj_in)`**: 根据传入的 `TaskConfigUpdate` Pydantic模型，更新一个已存在的任务配置。它使用了 `model_dump(exclude_unset=True)` 来确保只更新被实际提供的字段。
- **`delete(db, config_id)`**: 删除一个任务配置。由于在模型中设置了级联删除，所有与该配置关联的执行历史记录也会被自动删除。

### 统计方法
- **`get_stats(db)`**: 获取关于任务配置的全局统计信息，包括总配置数和按任务类型分类的计数值。
- **`get_execution_stats(db, config_id)`**: **此方法已被移动/重构**（根据代码内容，它似乎更适合在 `CRUDTaskExecution` 中，或者其逻辑已被 `get_stats_by_config` 替代）。它的原始意图是获取单个任务配置的执行统计数据。

## `CRUDTaskExecution` 类

这个类负责管理每一次任务执行的具体历史记录的增删改查和统计。

### 主要方法
- **`create(db, ...)`**: 创建一条新的任务执行记录。这个方法通常由 `@execution_handler` 装饰器在任务执行完毕后自动调用。
- **`get_by_task_id(db, task_id)`**: 根据 `TaskIQ` 生成的唯一 `task_id` 获取执行记录。
- **`get_executions_by_config(db, config_id, limit)`**: 获取某个特定任务配置下的最近N条执行历史。
- **`get_recent_executions(db, hours, limit)`**: 获取最近N小时内的所有任务执行记录。
- **`get_failed_executions(db, days, limit)`**: 获取最近N天内所有失败的任务执行记录。
- **`cleanup_old_executions(db, days_to_keep)`**: 一个数据库维护方法，用于定期删除超过指定天数（如90天）的旧执行记录，防止 `task_executions` 表无限增长。

### 统计方法
- **`get_global_stats(db, days)`**: 获取一个时间段内（如最近30天）的**全局**任务执行统计报告。
    - **统计内容**: 总执行次数、成功/失败次数、成功率/失败率、按任务类型分类的执行次数、所有成功任务的平均执行时长。
    - **实现**: 通过多个独立的、使用 `func` 模块（如 `func.count`, `func.avg`）的SQLAlchemy聚合查询来完成。
- **`get_stats_by_config(db, config_id, days)`**: 获取一个时间段内**单个任务配置**的执行统计报告，内容与全局统计类似，但范围限定在指定的 `config_id`。

## 全局实例
- `crud_task_config = CRUDTaskConfig()`
- `crud_task_execution = CRUDTaskExecution()`

文件末尾创建了这两个仓库类的全局单例实例，供上层服务调用。
