我刚刚创建了我后端项目中关于定时任务的一些文件，使用APscheduler+RabbitMQ+Celery。
目前有下面5个核心文件:
backend\app\core\scheduler.py :只负责使用APscheduler 进行调度
backend\app\core\event_recorder.py :只负责将调度事件和celery的执行事件记录到数据库。
backend\app\core\task_dispatcher.py :只负责注册任务并且将任务分发到celery
backend\app\core\job_config_manager.py :只负责管理任务的配置信息。
backend\app\services\tasks_manager.py :协调上面4个组件，作为用户输入的入口

可以看到，我的上面5个文件中，都写死了目前任务的类型，比如cleanup，或者scraping。（目前我的系统中只有这两种类型的任务）
可是，我的系统随着规模的增长，会增加越来越多的任务，比如send_email,notification 的新类型。
因此，目前的代码缺乏良好的扩展性。

我现在希望搭建一个框架，能够随时创建，修改不同类型的定时任务，同时监控任务状态，纪律任务执行履历。
为了完善这个框架，我觉得需要添加和修改如下的文件。
-------------------------------------
第一部分:
1.
在backend\app\core 文件夹下 创建task_type.py文件，创建一个枚举类，用来储存不同类型任务。
在backend\app\schemas 文件夹下创建task_type_schema.py文件，因为不同类型的task的配置参数不同，可能需要不同的schema对应。
2.
在backend\app\models 文件夹下增加一张task_config 表。
用来储存不同类型tasks的参数。
需要包含一个叫做task_type的列，类型为枚举，从上面创建的枚举类中取值。
因为不同类型tasks的参数可能完全不同，你可能需要一个json类型的列用来存储配置参数。

3.目前backend\app\models\schedule_event.py 表用来储存调度时间相关的信息。
backend\app\models\task_execution.py 表用来储存celery中执行的任务的相关信息。

我想将这两张表与上面的task_config 表关联。为此请你考虑一下这三个表之间的关系，给出一种合理的设计
-------------------------------------
第二部分:
基础的数据库已经创建完成，接下来你可能需要针对这三个表建成各自的crud文件。
在backend\app\crud 文件夹下。
schedule_event.py与task_execution.py 对应的crud文件已经存在了，但是由于刚才你可能更改了数据库结构，所以这两个文件也要做相应的修改
然后创建task_config 表 相关的crud文件。
-------------------------------------
第三部分:
task相关的表与crud操作已经完成，现在需要你修改与tasks相关的4个核心组件。
backend\app\core\scheduler.py :只负责使用APscheduler 进行调度
backend\app\core\event_recorder.py :只负责将调度事件和celery的执行事件记录到数据库。
backend\app\core\task_dispatcher.py :只负责注册任务并且将任务分发到celery
backend\app\core\job_config_manager.py :只负责管理任务的配置信息。

注意这4个单纯组件的职责分离，不要有相互耦合。去掉代码中原本与cleanup和scraping相关的死代码。现在所有任务的都应该从task_config 表中读取然后注册。
然后你可能需要修改一下job_config_manager.py 增加相关的数据库操作，因为task_config 表是刚刚添加的。
-------------------------------------
第四部分:
现在与tasks相关的基本框架已经完成，接下来需要制作用户接口暴露给用户。
修改backend\app\services\tasks_manager.py，用来协调上面的4个组件。
至少需要有以下功能:
a.根据现有的task类型，创建一个task schedule
b.更新目前task schedule的配置参数
c.删除一个task schedule
d.立即批量执行多个 task schedule
剩下的还有查看task状态，执行状态，健康度等等功能，你可以参考现有的代码自行发挥
-------------------------------------
补充:如果要添加新类型的任务，首先在backend\app\tasks 文件夹下创建新的任务处理逻辑
然后在刚才创建的task_type.py枚举文件中，创建新的类型。

=====================================
# 🎉 重构进展总结

## ✅ 已完成的工作

### 第一部分：基础数据库结构 - 已完成 ✅

1. **枚举定义** (`backend/app/core/task_type.py`) 
   - `TaskType` 枚举：支持爬取、清理、通知、数据处理、系统维护等多种任务类型
   - `TaskStatus` 枚举：任务状态管理（active, inactive, paused, error）
   - `SchedulerType` 枚举：调度器类型（interval, cron, date, manual）

2. **Schema模型** (`backend/app/schemas/task_config.py`)
   - 完整的Pydantic模型：创建、更新、响应、查询
   - 针对不同任务类型的特定配置Schema（Bot爬取、清理、邮件、通知等）
   - 完善的参数验证和调度配置验证
   - 支持批量操作和多维查询

3. **数据库模型** (`backend/app/models/task_config.py`)
   - `TaskConfig` 表：使用JSON列灵活存储任务参数和调度配置
   - 完整字段：名称、描述、类型、状态、参数、重试、超时、优先级等
   - 支持关联关系和级联删除

4. **表关联关系设计**
   ```
   task_config (1) -> (N) schedule_event  # 一个配置对应多个调度事件
   task_config (1) -> (N) task_execution  # 一个配置对应多个执行记录
   ```
   - 选择了方案A：两个执行表独立，通过task_config_id关联
   - `schedule_event` 表：添加了 `task_config_id` 外键
   - `task_execution` 表：添加了 `task_config_id` 外键
   - ID策略：APScheduler的job_id使用配置ID，Celery使用UUID

### 第二部分：CRUD操作层 - 已完成 ✅

1. **TaskConfig CRUD** (`backend/app/crud/task_config.py`)
   - 基础CRUD：创建、查询、更新、删除
   - 高级查询：按类型、状态、名称搜索，支持分页排序
   - 关联查询：可获取配置及其关联的调度事件和执行记录
   - 批量操作：批量更新状态、参数和调度配置
   - 统计功能：按类型/状态统计、执行统计信息
   - 业务方法：获取活跃配置、调度配置等

2. **ScheduleEvent CRUD 更新** (`backend/app/crud/schedule_event.py`)
   - 支持 `task_config_id` 外键关联
   - 新增创建方法，直接通过配置ID创建调度事件
   - 查询增强：按配置ID查询，支持关联预加载
   - 统计分析：事件统计、成功率分析
   - 优化的清理机制和错误处理

3. **TaskExecution CRUD 更新** (`backend/app/crud/task_execution.py`)
   - 完整生命周期：创建、状态更新、查询执行记录
   - 支持 `task_config_id` 外键关联
   - 多维查询：按配置ID、状态、时间范围查询
   - 状态管理：正在运行、失败执行记录的专门查询
   - 统计报告：详细的执行统计和成功率分析
   - 数据清理：自动清理旧执行记录

4. **CRUD模块导出** (`backend/app/crud/__init__.py`)
   - 统一导出所有CRUD类和全局实例
   - 提供 `crud_task_config`, `crud_schedule_event`, `crud_task_execution` 实例

## 🔄 待完成的工作

### 第三部分：核心组件重构 - 待开始 ⏳
- `scheduler.py`：移除硬编码，从task_config表读取调度任务
- `event_recorder.py`：适配新的数据库关联关系
- `task_dispatcher.py`：支持通用任务类型分发
- `job_config_manager.py`：改为数据库存储而非内存存储

### 第四部分：用户接口层重构 - 待开始 ⏳
- `tasks_manager.py`：重构为通用任务管理接口
- 功能：创建、更新、删除任务调度，批量执行，状态监控等

## 🏗️ 架构设计亮点

1. **灵活的参数存储**：使用JSON列支持不同任务类型的不同参数需求
2. **完整的关联关系**：三张表正确关联，支持级联操作
3. **丰富的查询功能**：支持复杂条件查询、统计分析、关联预加载
4. **统一的错误处理**：完善的异常处理和事务管理
5. **业务场景适配**：针对任务管理场景设计的专用方法和统计功能

## 📝 下次继续的重点

继续第三部分时，重点关注：
1. 保持4个核心组件的职责分离，避免相互耦合
2. 将hardcode的任务类型改为从数据库读取
3. 无需考虑兼容性，可以认为这是全新的框架
4. job_config_manager从内存存储迁移到数据库存储

=====================================