# 高优先级优化具体实施方案

## 1. 统一状态定义

### 问题分析
目前存在多个重复/混淆的状态定义：
- `app/core/task_registry.py` 中的 `TaskStatus`（配置状态）
- `app/schemas/job_schemas.py` 中的 `TaskStatus`（运行状态）
- `app/models/task_execution.py` 中的 `ExecutionStatus`（执行状态）

### 实施方案

#### 1.1 保留和修改的文件

**修改 `app/core/task_registry.py`：**
```python
# 重命名 TaskStatus 为 ConfigStatus，明确这是配置状态
class ConfigStatus(str, PyEnum):
    """任务配置状态"""
    ACTIVE = "active"      # 配置激活，可以被调度
    INACTIVE = "inactive"  # 配置未激活，不会被调度
    PAUSED = "paused"      # 配置暂停，临时停止调度
    ERROR = "error"        # 配置错误，需要修复

# 添加运行时状态定义（从job_schemas.py迁移）
class RuntimeStatus(str, PyEnum):
    """任务运行时状态"""
    IDLE = "idle"           # 空闲
    SCHEDULED = "scheduled" # 已调度等待执行
    RUNNING = "running"     # 正在执行
    COMPLETED = "completed" # 执行完成
    FAILED = "failed"       # 执行失败
    TIMEOUT = "timeout"     # 执行超时
    MISFIRED = "misfired"   # 错过执行时间

# 保持 ExecutionStatus 引用，但使用 models 中的定义
from app.models.task_execution import ExecutionStatus

# 导出所有状态
__all__ = [
    "TaskType",
    "ConfigStatus",  # 原 TaskStatus
    "RuntimeStatus", # 新增
    "ExecutionStatus", # 从 models 导入
    "SchedulerType",
    "ScheduleAction"
]
```

**修改 `app/models/task_config.py`：**
```python
# 导入修改
from app.core.task_registry import TaskType, ConfigStatus, SchedulerType  # TaskStatus改为ConfigStatus

class TaskConfig(Base):
    # ... 其他代码 ...
    
    # 修改状态字段
    status: Mapped[ConfigStatus] = mapped_column(
        Enum(ConfigStatus),  # 原 TaskStatus
        nullable=False, 
        default=ConfigStatus.ACTIVE,  # 原 TaskStatus.ACTIVE
        index=True
    )
    
    @property
    def is_active(self) -> bool:
        """判断任务是否为活跃状态"""
        return self.status == ConfigStatus.ACTIVE  # 原 TaskStatus.ACTIVE
```

**删除 `app/schemas/job_schemas.py` 中的 TaskStatus：**
```python
# 删除这个枚举定义
# class TaskStatus(str, Enum):  # 删除整个类
#     RUNNING = "running"
#     SCHEDULED = "scheduled"
#     ...

# 改为从 task_registry 导入
from app.core.task_registry import RuntimeStatus

# 修改所有引用 TaskStatus 的地方为 RuntimeStatus
```

#### 1.2 需要更新引用的文件

**所有文件中的引用更新：**
```python
# 查找替换规则：
# TaskStatus.ACTIVE -> ConfigStatus.ACTIVE
# TaskStatus.INACTIVE -> ConfigStatus.INACTIVE
# TaskStatus.PAUSED -> ConfigStatus.PAUSED
# TaskStatus.ERROR -> ConfigStatus.ERROR

# 涉及文件：
# - app/crud/task_config.py
# - app/services/tasks_manager.py
# - app/schemas/task_config_schemas.py
# - app/api/v1/routes/task_routes.py
```

## 2. 修复异步方法不一致

### 问题分析
`app/services/tasks_manager.py` 中的私有方法异步性不一致。

### 实施方案

**修改 `app/services/tasks_manager.py`：**

```python
class TaskManager:
    # 这些方法内部没有异步操作，应该改为同步方法
    
    # 原来是 async，改为同步
    def _start_scheduler_task(self, config_id: int) -> bool:
        """启动调度器中的任务（不处理状态同步）"""
        try:
            # reload_task_from_database 是异步的，需要特殊处理
            # 改为同步调用或重新设计
            # 方案1：让 scheduler 提供同步版本的方法
            # 方案2：保持这个方法为 async
            return self.scheduler.start_task_sync(config_id, execute_scheduled_task)
        except Exception as e:
            logger.error(f"启动调度器任务失败 {config_id}: {e}")
            return False
    
    # 这些已经是同步的，保持不变
    def _stop_scheduler_task(self, config_id: int) -> bool:
        """停止调度器中的任务（不处理状态同步）"""
        # 保持不变
        pass
    
    def _pause_scheduler_task(self, config_id: int) -> bool:
        """暂停调度器中的任务（不处理状态同步）"""
        # 保持不变
        pass
    
    def _resume_scheduler_task(self, config_id: int) -> bool:
        """恢复调度器中的任务（不处理状态同步）"""
        # 保持不变
        pass
    
    # 需要保持 async，因为调用了异步的 reload_task_from_database
    async def _reload_scheduler_task(self, config_id: int) -> bool:
        """重新加载调度器中的任务（不处理状态同步）"""
        # 保持不变
        pass
```

**更好的方案：统一为异步方法**
```python
class TaskManager:
    # 统一改为异步方法，即使内部操作是同步的
    # 这样可以保持接口一致性，便于未来扩展
    
    async def _start_scheduler_task(self, config_id: int) -> bool:
        """启动调度器中的任务（不处理状态同步）"""
        try:
            return await self.scheduler.reload_task_from_database(config_id, execute_scheduled_task)
        except Exception as e:
            logger.error(f"启动调度器任务失败 {config_id}: {e}")
            return False
    
    async def _stop_scheduler_task(self, config_id: int) -> bool:
        """停止调度器中的任务（不处理状态同步）"""
        try:
            return self.scheduler.remove_task_by_config_id(config_id)
        except Exception as e:
            logger.error(f"停止调度器任务失败 {config_id}: {e}")
            return False
    
    async def _pause_scheduler_task(self, config_id: int) -> bool:
        """暂停调度器中的任务（不处理状态同步）"""
        try:
            jobs = self.scheduler.get_all_jobs()
            for job in jobs:
                extracted_config_id = TaskRegistry.extract_config_id_from_job_id(job.id)
                if extracted_config_id == config_id:
                    return self.scheduler.pause_job(job.id)
            logger.warning(f"未找到任务配置 {config_id} 的调度任务")
            return False
        except Exception as e:
            logger.error(f"暂停调度器任务失败 {config_id}: {e}")
            return False
    
    async def _resume_scheduler_task(self, config_id: int) -> bool:
        """恢复调度器中的任务（不处理状态同步）"""
        try:
            jobs = self.scheduler.get_all_jobs()
            for job in jobs:
                extracted_config_id = TaskRegistry.extract_config_id_from_job_id(job.id)
                if extracted_config_id == config_id:
                    return self.scheduler.resume_job(job.id)
            logger.warning(f"未找到任务配置 {config_id} 的调度任务")
            return False
        except Exception as e:
            logger.error(f"恢复调度器任务失败 {config_id}: {e}")
            return False
    
    # manage_scheduled_task 方法也需要相应更新
    async def manage_scheduled_task(self, config_id: int, action: ScheduleAction) -> Dict[str, Any]:
        """统一的调度任务管理方法"""
        try:
            # ... 其他代码 ...
            
            # 所有调用都改为 await
            if action == ScheduleAction.START:
                success = await self._start_scheduler_task(config_id)  # 添加 await
                target_status = ConfigStatus.ACTIVE  # TaskStatus 改为 ConfigStatus
                
            elif action == ScheduleAction.STOP:
                success = await self._stop_scheduler_task(config_id)  # 添加 await
                target_status = ConfigStatus.INACTIVE
                
            elif action == ScheduleAction.PAUSE:
                success = await self._pause_scheduler_task(config_id)  # 添加 await
                target_status = ConfigStatus.PAUSED
                
            elif action == ScheduleAction.RESUME:
                success = await self._resume_scheduler_task(config_id)  # 添加 await
                target_status = ConfigStatus.ACTIVE
                
            # ... 其他代码 ...
```

## 3. 统一命名规范

### 问题分析
主要是 `config_id` vs `config_id` 的不一致。

### 实施方案

**统一使用 `config_id`（更简洁）：**

#### 3.1 需要修改的文件

**修改 `app/services/tasks_manager.py`：**
```python
# 全局函数修改
async def execute_scheduled_task(config_id: int):  # config_id -> config_id
    """执行调度任务的通用包装函数"""
    dispatcher = TaskDispatcher()
    try:
        return await dispatcher.dispatch_by_config_id(config_id)
    except Exception as e:
        logger.error(f"执行调度任务失败 {config_id}: {e}")
        raise

# _record_event_async 方法参数保持 job_id，但内部变量统一
async def _record_event_async(
    self,
    job_id: str,
    event_type: ScheduleEventType,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    error_traceback: Optional[str] = None
):
    """异步记录调度事件"""
    try:
        # 从job_id中提取config_id（原 config_id）
        config_id = TaskRegistry.extract_config_id_from_job_id(job_id)
        
        if config_id is None:
            logger.warning(f"无法从job_id中提取config_id: {job_id}")
            return
        
        async with AsyncSessionLocal() as db:
            await crud_schedule_event.create(
                db,
                config_id=config_id,  # 数据库字段名保持不变
                job_id=job_id,
                job_name=f"Task-{job_id}",
                event_type=event_type,
                result=result,
                error_message=error_message,
                error_traceback=error_traceback
            )
    except Exception as e:
        logger.error(f"记录调度事件失败: {e}")
```

**修改 `app/core/task_dispatcher.py`：**
```python
async def dispatch_by_config_id(
    self,
    config_id: int,  # config_id -> config_id
    **options
) -> str:
    """
    根据任务配置ID分发任务
    
    Args:
        config_id: 任务配置ID  # 参数名和文档都改
        **options: 分发选项(countdown, eta等)
    """
    async with AsyncSessionLocal() as db:
        from app.crud.task_config import crud_task_config
        
        # 获取任务配置
        config = await crud_task_config.get(db, config_id)  # 内部使用也统一
        if not config:
            raise ValueError(f"任务配置不存在: {config_id}")
        
        # 准备参数
        args = [config_id]  # 这里传递的参数名不变，因为是位置参数
        kwargs = config.parameters or {}
        
        return self.dispatch_task(
            task_name=celery_task,
            args=args,
            kwargs=kwargs,
            queue=queue,
            **options
        )
```

**修改 `app/tasks/cleanup_jobs.py`：**
```python
async def _cleanup_expired_tokens_async(config_id: int, *, days_old: int = 7) -> Dict[str, Any]:
    """
    异步清理过期的刷新令牌和密码重置令牌的内部实现。
    """
    logger.info(f"开始异步清理 {days_old} 天前的过期令牌... (Config ID: {config_id})")
    # ... 其他代码保持不变 ...

@celery_app.task(bind=True, name='cleanup_expired_tokens_task')
@task_executor("清理过期令牌任务")
def cleanup_expired_tokens_task(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """清理过期的刷新令牌和密码重置令牌。"""
    # 从参数中提取 config_id（原 config_id）
    config_id = kwargs.get("config_id") or (args[0] if args else None)  # 保持兼容性
    
    # 提取特定于任务的参数
    days_old = kwargs.get("days_old", 7)
    
    return asyncio.run(_cleanup_expired_tokens_async(config_id, days_old=days_old))

# 对其他任务函数做同样修改
```

**修改 `app/middleware/decorators.py`：**
```python
async def _record_execution(
    config_id: int,  # config_id -> config_id
    job_id: str,
    job_name: str,
    status: ExecutionStatus,
    started_at: float,
    completed_at: float,
    result: Any = None,
    error_message: str | None = None,
    error_traceback: str | None = None,
):
    """异步地将任务执行记录保存到数据库。"""
    if config_id == -1:
        logger.info(f"任务 '{job_name}' (ID: {job_id}) 是直接调用任务，跳过数据库记录。")
        return
    
    # ... 其他代码，但数据库字段名保持 config_id ...
    await crud_task_execution.create(
        db=db,
        config_id=config_id,  # 数据库字段名不变
        # ... 其他参数 ...
    )

def task_executor(task_name: str):
    """一个装饰器，用于包装 Celery 任务，自动记录其执行状态。"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            task_instance: Task = args[0]
            job_id = task_instance.request.id
            
            # 变量名统一为 config_id
            config_id = kwargs.get("config_id") or (args[1] if len(args) > 1 else None)
            if not config_id:
                logger.warning(f"任务 '{task_name}' (ID: {job_id}) 没有 config_id，可能是直接调用的任务。")
                config_id = -1
            
            # ... 使用 config_id ...
```
其它相关Model和crud文件。
backend\app\models\schedule_event.py
backend\app\models\task_execution.py
backend\app\crud\schedule_event.py
backend\app\crud\task_execution.py
## 4. 实施步骤总结

### 第一步：状态定义统一（最重要）
1. 修改 `task_registry.py`，重命名 `TaskStatus` 为 `ConfigStatus`
2. 在 `task_registry.py` 添加 `RuntimeStatus`
3. 删除 `job_schemas.py` 中的 `TaskStatus`
4. 全局替换所有 `TaskStatus` 引用

### 第二步：异步方法统一
1. 将 `tasks_manager.py` 中所有 `_xxx_scheduler_task` 方法统一为 `async`
2. 在 `manage_scheduled_task` 中对应添加 `await`

### 第三步：命名规范统一
1. 全局将 `config_id` 参数名替换为 `config_id`
2. 更新相关文档字符串

### 测试验证
每一步修改后都需要运行测试：
```bash
# 运行测试确保没有破坏现有功能
pytest tests/
python app/tests/test_status_sync_simple.py
python app/tests/test_unified_schedule_endpoint.py
```

这些修改不会影响功能，只是提高代码的一致性和可维护性。建议按步骤逐个实施，每步完成后进行测试验证。