# `cache_tags.py` 文档

此文件定义了一个枚举类 `CacheTags`，用于标准化和集中管理应用中使用的所有缓存标签（Cache Tags）。

## `CacheTags(str, Enum)` 枚举

使用缓存标签是一种良好的实践，它允许我们对相关的缓存进行分组。当某个数据发生变化时，我们可以通过标签来批量失效（invalidate）一组缓存，而不是手动跟踪和删除每一个缓存键。

### 功能

该枚举将字符串标签赋予有意义的名称，提高了代码的可读性和可维护性。如果未来需要修改某个标签的名称，只需在此文件中修改一处即可。

### 定义的标签

- **用户相关 (`USER_PROFILE`, `USER_LIST`, `USER_ME`)**
    - 用于缓存用户的个人资料、用户列表以及当前登录用户的信息。

- **任务系统 (`TASK_CONFIGS`, `TASK_CONFIG_DETAIL`, `SCHEDULE_LIST`, `EXECUTION_STATS`)**
    - 用于缓存任务配置列表、单个任务配置的详情、任务调度计划以及任务执行的统计数据。

- **系统状态 (`SYSTEM_STATUS`, `SYSTEM_DASHBOARD`, `SYSTEM_ENUMS`, `TASK_INFO`)**
    - 用于缓存系统健康状态、仪表盘数据、系统中使用的各种枚举值以及后台任务（如TaskIQ）的信息。
