# 任务管理系统架构重构方案

## 一、核心重构理念

### 职责分离原则
1. **PostgreSQL (task_configs)**: 仅存储静态任务配置
2. **Redis**: 作为唯一的调度状态管理器
3. **PostgreSQL (task_executions)**: 仅存储执行历史记录（成功/失败）

## 二、需要删除的文件/代码

### 完全删除的文件夹
```
app/implementation/tasks/  # 整个文件夹都可以删除
├── __init__.py
├── config.py       # 过度封装，直接用CRUD
├── execution.py    # 过度封装，合并到其他地方
├── monitor.py      # 监控功能移到API层
└── scheduler.py    # 功能移到redis/scheduler.py
```

### 完全删除的文件
```
app/core/task_manager.py  # 删除这个中间层，直接调用具体服务
app/core/tasks/base.py    # TaskServiceBase没有必要
app/core/tasks/executor.py # 功能太简单，合并到decorators.py
```

## 三、数据库架构变更

### 1. task_configs 表改动
backend/app/models/task_config.py - 移除状态
我们将移除 status 字段，并简化模型，让它只关注配置本身。
```python
# backend/app/models/task_config.py

from datetime import datetime
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from sqlalchemy import String, DateTime, func, Integer, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base_class import Base
from app.core.tasks.registry import SchedulerType # 移除 ConfigStatus

if TYPE_CHECKING:
    from .task_execution import TaskExecution


class TaskConfig(Base):
    """任务配置表 - 存储所有类型任务的静态配置信息"""
    __tablename__ = "task_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # 基本信息
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # 任务类型
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scheduler_type: Mapped[SchedulerType] = mapped_column(Enum(SchedulerType), nullable=False)
    
    # 配置参数
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default={})
    schedule_config: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default={})
    
    # 执行控制
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)  # 1-10
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())
    
    # 关联关系
    task_executions: Mapped[List["TaskExecution"]] = relationship(
        "TaskExecution", 
        back_populates="task_config",
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    def __repr__(self) -> str:
        return f"<TaskConfig(id={self.id}, name='{self.name}', type={self.task_type})>"
    
    @property
    def is_scheduled(self) -> bool:
        """判断任务是否为调度任务"""
        return self.scheduler_type != SchedulerType.MANUAL
    
    def get_parameter(self, key: str, default=None):
        """获取参数值"""
        return self.parameters.get(key, default)
    
    def get_schedule_config(self, key: str, default=None):
        """获取调度配置值"""
        return self.schedule_config.get(key, default)
    
    def update_parameters(self, **kwargs):
        """更新参数"""
        if self.parameters is None:
            self.parameters = {}
        self.parameters.update(kwargs)
    
    def update_schedule_config(self, **kwargs):
        """更新调度配置"""
        if self.schedule_config is None:
            self.schedule_config = {}
        self.schedule_config.update(kwargs)
);
```

### 2. task_executions 表改动
我们将 status 简化，考虑使用布尔值，不再需要ExecutionStatus 枚举
```python
# backend/app/models/task_execution.py

from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, DateTime, func, Integer, Text, Enum, Numeric, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base_class import Base
if TYPE_CHECKING:
    from .task_config import TaskConfig


class TaskExecution(Base):
    """任务执行历史表 - 记录最终执行结果"""
    __tablename__ = "task_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    config_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("task_configs.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    
    # 最终执行状态
    is_success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    
    # 执行结果
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    task_config: Mapped["TaskConfig"] = relationship("TaskConfig", back_populates="task_executions")
    
    def __repr__(self) -> str:
        return f"<TaskExecution(id={self.id}, config_id={self.config_id}, status={self.status})>"
```

## 四、简化后的架构

### 文件结构
```
app/
├── api/v1/routes/
│   └── task_routes.py      # 直接调用CRUD和Redis服务
├── broker.py               # 保留
├── core/
│   ├── redis/              # 保留Redis基础设施
│   │   ├── base.py
│   │   ├── config.py
│   │   └── pool.py
│   ├── redis_manager.py    # 保留，但简化
│   └── tasks/
│       ├── __init__.py
│       ├── decorators.py   # 合并executor功能
│       └── registry.py     # 简化，只保留任务注册
├── services/               # 改名，更清晰
│   └── redis/
│       ├── scheduler.py    # 增强，包含所有调度逻辑
│       ├── cache.py        # 保留
│       ├── auth.py         # 保留
│       └── history.py      # 简化
├── crud/
│   ├── task_config.py      # 简化，删除status相关
│   └── task_execution.py   # 简化，使用is_success
├── models/
│   ├── task_config.py      # 删除status字段
│   └── task_execution.py   # 改为is_success
└── tasks/                  # 实际的任务定义
    ├── cleanup_tasks.py
    ├── data_tasks.py
    └── notification_tasks.py
```

## 五、核心文件重构

### 1. 删除 `app/core/task_manager.py`
直接在API层调用具体服务

### 2. 简化 `app/api/v1/routes/task_routes.py`
```python
from app.crud.task_config import crud_task_config
from app.crud.task_execution import crud_task_execution
from app.services.redis.scheduler import scheduler_service

@router.post("/configs")
async def create_task_config(config: TaskConfigCreate, db: AsyncSession = Depends(get_db)):
    """直接调用CRUD创建配置"""
    task_config = await crud_task_config.create(db, config)
    
    # 如果需要调度，直接注册到Redis
    if config.scheduler_type != "manual":
        await scheduler_service.register_task(task_config)
    
    return task_config

@router.post("/configs/{config_id}/schedule")
async def manage_schedule(config_id: int, action: str):
    """直接调用Redis scheduler服务"""
    if action == "start":
        await scheduler_service.start_task(config_id)
    elif action == "stop":
        await scheduler_service.stop_task(config_id)
    # ...

@router.get("/configs/{config_id}")
async def get_task_config(config_id: int, db: AsyncSession = Depends(get_db)):
    """组合数据库配置和Redis状态"""
    config = await crud_task_config.get(db, config_id)
    status = await scheduler_service.get_task_status(config_id)
    
    return {
        **config.dict(),
        "schedule_status": status
    }
```

### 3. 增强 `app/services/redis/scheduler.py`
调度器不再依赖数据库中的 status 字段。它的行为（注册、更新、删除）直接由 API 调用驱动。
```python
class SchedulerService:
    """统一的调度服务，管理所有调度相关操作"""
    
    def __init__(self):
        self.redis_source = RedisScheduleSource(url=settings.redis.CONNECTION_URL)
        self.status_prefix = "schedule:status:"
    
    # 任务注册/注销
    async def register_task(self, config: TaskConfig) -> bool:
        """注册任务到调度器"""
        task_func = get_task_function(config.task_type)
        scheduled_task = self._build_scheduled_task(config, task_func)
        await self.redis_source.add_schedule(scheduled_task)
        await self.set_status(config.id, "active")
        return True
    
    async def unregister_task(self, config_id: int) -> bool:
        """从调度器注销任务"""
        await self.redis_source.delete_schedule(f"task_{config_id}")
        await self.set_status(config_id, "inactive")
        return True
    
    # 状态管理
    async def set_status(self, config_id: int, status: str):
        """设置任务调度状态"""
        key = f"{self.status_prefix}{config_id}"
        await self.redis.set(key, status)
    
    async def get_status(self, config_id: int) -> str:
        """获取任务调度状态"""
        key = f"{self.status_prefix}{config_id}"
        return await self.redis.get(key) or "inactive"
    
    async def get_all_statuses(self) -> Dict[int, str]:
        """获取所有任务状态"""
        keys = await self.redis.keys(f"{self.status_prefix}*")
        statuses = {}
        for key in keys:
            config_id = int(key.replace(self.status_prefix, ""))
            statuses[config_id] = await self.redis.get(key)
        return statuses
    
    # 调度操作
    async def start_task(self, config_id: int):
        """启动任务调度"""
        config = await self._get_config(config_id)
        await self.register_task(config)
    
    async def stop_task(self, config_id: int):
        """停止任务调度"""
        await self.unregister_task(config_id)
    
    async def pause_task(self, config_id: int):
        """暂停任务（通过注销实现）"""
        await self.unregister_task(config_id)
        await self.set_status(config_id, "paused")
    
    async def resume_task(self, config_id: int):
        """恢复任务"""
        config = await self._get_config(config_id)
        await self.register_task(config)

scheduler_service = SchedulerService()
```

### 4. 合并功能到 `app/core/tasks/decorators.py`
现在不再有TIMEOUT，RUNNING等状态，只有成功，失败两种状态
```python
"""合并executor.py的功能"""
import uuid
from datetime import datetime

async def create_execution_record(config_id: int, task_id: str, is_success: bool = None):
    """创建执行记录（原executor功能）"""
    from app.db.base import AsyncSessionLocal
    from app.crud.task_execution import crud_task_execution
    
    async with AsyncSessionLocal() as db:
        await crud_task_execution.create(
            db=db,
            config_id=config_id,
            task_id=task_id,
            is_success=is_success,
            started_at=datetime.utcnow()
        )

def with_execution_tracking(func):
    """装饰器：跟踪任务执行"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        config_id = kwargs.get('config_id')
        task_id = str(uuid.uuid4())
        
        # 创建开始记录
        await create_execution_record(config_id, task_id)
        
        try:
            result = await func(*args, **kwargs)
            # 更新为成功
            await update_execution_record(task_id, is_success=True)
            return result
        except Exception as e:
            # 更新为失败
            await update_execution_record(task_id, is_success=False, error=str(e))
            raise
    
    return wrapper
```

### 5. `backend/app/crud/task_config.py` - 简化为纯粹的配置管理
CRUD 类现在只负责配置的增、删、改、查，不再关心任何“状态”管理。

```python
# backend/app/crud/task_config.py

# ... (imports) ...

class CRUDTaskConfig:
    """任务配置CRUD操作 - 只管理静态配置"""
    
    # ... (get, get_with_relations, get_by_name, get_by_query, get_by_type 保持不变) ...

    # 移除 get_active_configs 和 get_scheduled_configs
    # 获取“活跃”任务现在是调度器的职责 (get_all_schedules)
    
    async def create(self, db: AsyncSession, obj_in: TaskConfigCreate) -> TaskConfig:
        """创建任务配置"""
        try:
            # 移除 status 字段的映射
            db_obj = TaskConfig(
                name=obj_in.name,
                description=obj_in.description,
                task_type=obj_in.task_type,
                scheduler_type=obj_in.scheduler_type,
                # status=obj_in.status, # 移除
                parameters=obj_in.parameters,
                schedule_config=obj_in.schedule_config,
                max_retries=obj_in.max_retries,
                timeout_seconds=obj_in.timeout_seconds,
                priority=obj_in.priority
            )
            # ... (commit, refresh) ...
        except Exception as e:
            # ... (rollback, raise) ...

    async def update(
        self,
        db: AsyncSession,
        db_obj: TaskConfig,
        obj_in: TaskConfigUpdate
    ) -> TaskConfig:
        """更新任务配置"""
        # ... (逻辑基本不变，但 obj_in 中不会再有 status) ...

    async def delete(self, db: AsyncSession, config_id: int) -> bool:
        """删除任务配置"""
        # ... (逻辑不变) ...

    # ------------------------------------------------------------------
    # 以下所有与 status 相关的方法都应该被移除
    # ------------------------------------------------------------------
    # async def batch_update_status(...) -> REMOVE
    # async def update_status(...) -> REMOVE
    # async def get_active_count(...) -> REMOVE
    # ------------------------------------------------------------------

    # ... (其他统计方法如 get_execution_stats, count_by_type 等可以保留或根据新逻辑调整) ...
```

### 6. `backend/app/crud/task_execution.py` - 调整为仅记录最终结果
```python
# backend/app/crud/task_execution.py

# ... (imports) ...

class CRUDTaskExecution:
    """任务执行CRUD操作 - 记录最终结果"""
    
    async def create_execution_log(
        self,
        db: AsyncSession,
        config_id: int,
        task_id: str,
        status: bool,
        started_at: datetime,
        completed_at: datetime,
        duration_seconds: float,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None
    ) -> TaskExecution:
        """创建一条最终的任务执行日志"""
        try:
            db_obj = TaskExecution(
                config_id=config_id,
                task_id=task_id,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
                result=result,
                error_message=error_message,
                error_traceback=error_traceback
            )
            # ... (commit, refresh) ...
        except Exception as e:
            # ... (rollback, raise) ...
    
    # ------------------------------------------------------------------
    # 在新的模型下，执行记录应该在任务完成后一次性写入，而不是中途更新状态。
    # TaskIQ worker 在任务执行完毕后，收集所有信息（开始时间、结束时间、结果/错误），
    # 因此，可以移除 update_status 方法。
    # ------------------------------------------------------------------

    # ... (get_running_executions 失去了意义，应被移除) ...

    # async def get_running_executions(...) -> REMOVE
```

### 7. 简化 `app/core/redis_manager.py`
```python
class RedisServiceManager:
    """简化版Redis服务管理器"""
    
    def __init__(self):
        self.cache = CacheRedisService()
        self.scheduler = SchedulerService()  # 直接使用增强版
        self.history = HistoryService()
        self.auth = AuthRedisService()
    
    async def initialize(self):
        """初始化服务"""
        await self.scheduler.initialize()
        # 其他必要的初始化

redis_services = RedisServiceManager()
```

### 6. 简化 `app/core/tasks/registry.py`
```python
"""极简任务注册系统"""
from typing import Dict, Callable

# 全局任务注册表
TASKS: Dict[str, Callable] = {}

def task(name: str, queue: str = "default"):
    """任务注册装饰器"""
    def decorator(func: Callable) -> Callable:
        TASKS[name] = {
            'func': func,
            'queue': queue
        }
        return func
    return decorator

def get_task_function(task_type: str) -> Callable:
    """获取任务函数"""
    task_info = TASKS.get(task_type)
    return task_info['func'] if task_info else None

# 删除其他复杂的枚举和辅助函数
```

## 六、新架构的数据流

### 1. 创建任务配置
```
API -> CRUD -> PostgreSQL (task_configs)
    -> Redis (如果需要自动调度)
```

### 2. 管理调度状态
```
API -> Redis Scheduler Service -> Redis
```

### 3. 执行任务
```
TaskIQ Worker -> Task Code 
              -> CRUD -> PostgreSQL (task_executions，记录is_success)
```

### 4. 查询任务状态
```
API -> PostgreSQL (获取静态配置)
    -> Redis (获取调度状态)
    -> 合并返回
```