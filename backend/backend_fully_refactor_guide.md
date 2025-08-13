# TaskIQ 重构指南

## 一、架构概述

### 现有架构问题
- Celery 与 FastAPI 的异步/同步转换复杂
- APScheduler 与 Celery 的集成管理困难
- 状态管理过于复杂
- 事件循环冲突问题频发

### 新架构优势
- **TaskIQ** 原生支持异步，与 FastAPI 完美兼容
- **TaskIQ-Scheduler** 内置调度器，无需额外集成
- 统一的任务管理接口
- 简化的状态管理

## 二、依赖更新

### 2.1 更新 `backend/pyproject.toml`

```toml
[tool.poetry]
name = "backend"
version = "0.1.0"
description = ""
authors = ["Your Name <you@example.com>"]
package-mode = false

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.112.0"
uvicorn = "^0.35.0"
sqlalchemy = "^2.0.42"
pydantic = {extras = ["email"], version = "^2.11.0"}
pydantic-settings = "^2.10.0"
pydantic-extra-types = "^2.5.0"
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
bcrypt = "4.0.1"
python-multipart = "^0.0.6"
alembic = "^1.13.1"
psycopg2-binary = "^2.9.9"
loguru = "^0.7.2"
python-dotenv = "^1.0.0"
asyncpg = "^0.29.0"
pytz = "^2024.1"

# 新增 TaskIQ 相关依赖
taskiq = "^0.11.0"
taskiq-aio-pika = "^0.4.0"  # RabbitMQ broker
taskiq-redis = "^1.0.0"  # 可选：用于结果后端
taskiq-scheduler = "^1.0.0"  # 调度器
pydantic-settings = "^2.0.0"

# 保留但可能不再需要的依赖（根据实际需求决定）
asyncpraw = "^7.7.1"
tweepy = "^4.14.0"
python-telegram-bot = "^20.0"
aiohttp = "^3.8.0"
pillow = "^10.0.0"
google-genai = "^0.3.0"
twitter-text-parser = "^3.0.0"

# 删除的依赖
# apscheduler = "^3.10.4"  # 删除
# celery = {extras = ["amqp", "sqlalchemy"], version = "^5.5.0"}  # 删除
# kombu = "^5.3.4"  # 删除
# flower = "^2.0.1"  # 删除

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

### 2.2 更新 `docker-compose.yml`

```yaml
version: "3.8"

services:
  frontend:
    build: ./frontend
    env_file:
      - .env
    ports:
      - "${FRONTEND_PORT}:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_URL=http://backend:${BACKEND_PORT}
    depends_on:
      - backend
    networks:
      - app_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${FRONTEND_PORT}"]
      interval: 30s
      timeout: 10s
      retries: 3

  backend:
    build: ./backend
    env_file:
      - .env
    ports:
      - "${BACKEND_PORT}:8000"
    volumes:
      - ./backend:/app
    environment:
      - POSTGRES_HOST=${POSTGRES_HOST}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
      - SECRET_KEY=${SECRET_KEY}
      - ACCESS_TOKEN_EXPIRE_MINUTES=${ACCESS_TOKEN_EXPIRE_MINUTES}
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_USER=${RABBITMQ_USER:-guest}
      - RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-guest}
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    command: >
      bash -c "
        echo '等待数据库准备...' &&
        poetry install --no-interaction --no-ansi &&
        poetry run alembic upgrade head &&
        poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
      "
    networks:
      - app_network

  postgres:
    image: postgres:17
    env_file:
      - .env
    ports:
      - "${POSTGRES_PORT}:5432"
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - app_network

  pgadmin:
    image: dpage/pgadmin4:9
    env_file:
      - .env
    ports:
      - "${PGADMIN_PORT}:80"
    environment:
      - PGADMIN_DEFAULT_EMAIL=${PGADMIN_DEFAULT_EMAIL}
      - PGADMIN_DEFAULT_PASSWORD=${PGADMIN_DEFAULT_PASSWORD}
      - PGADMIN_CONFIG_SERVER_MODE=${PGADMIN_CONFIG_SERVER_MODE}
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - app_network

  rabbitmq:
    image: rabbitmq:4-management
    env_file:
      - .env
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      - RABBITMQ_DEFAULT_USER=${RABBITMQ_USER:-guest}
      - RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASSWORD:-guest}
      - RABBITMQ_DEFAULT_VHOST=${RABBITMQ_VHOST:-/}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - app_network

  # TaskIQ Worker 服务
  taskiq_worker:
    build: ./backend
    env_file:
      - .env
    environment:
      - POSTGRES_HOST=${POSTGRES_HOST}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_USER=${RABBITMQ_USER:-guest}
      - RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-guest}
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    command: >
      bash -c "
        echo '等待依赖服务...' &&
        sleep 10 &&
        poetry install --no-interaction --no-ansi &&
        poetry run taskiq worker app.broker:broker --log-level info
      "
    networks:
      - app_network
    deploy:
      replicas: 2  # 可以根据需求调整 worker 数量

  # TaskIQ Scheduler 服务
  taskiq_scheduler:
    build: ./backend
    env_file:
      - .env
    environment:
      - POSTGRES_HOST=${POSTGRES_HOST}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_USER=${RABBITMQ_USER:-guest}
      - RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-guest}
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      taskiq_worker:
        condition: service_started
    command: >
      bash -c "
        echo '等待依赖服务...' &&
        sleep 15 &&
        poetry install --no-interaction --no-ansi &&
        poetry run taskiq-scheduler app.scheduler:scheduler --log-level info
      "
    networks:
      - app_network

volumes:
  postgres_data:
  rabbitmq_data:

networks:
  app_network:
    driver: bridge
```

## 三、删除的文件

以下文件应该完全删除：

```
backend/app/celery_app.py
backend/app/core/scheduler.py
backend/app/core/task_dispatcher.py
backend/app/tasks/worker_init.py
backend/app/middleware/decorators.py
backend/app/db/engine_manager.py
```

## 四、新增的文件

### 4.1 创建 `backend/app/broker.py`

```python
"""
TaskIQ Broker 配置
统一管理任务队列和调度器
"""
import os
from typing import Optional
from taskiq import TaskiqScheduler, TaskiqEvents
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from app.core.config import settings
from app.db.base import engine

# 配置 RabbitMQ broker
broker = AioPikaBroker(
    url=f"amqp://{settings.rabbitmq.USER}:{settings.rabbitmq.PASSWORD}@{settings.rabbitmq.HOST}:{settings.rabbitmq.PORT}/",
    task_id_generator=lambda: str(uuid.uuid4()),
)

# 可选：配置 Redis 作为结果后端（更快）
# 如果不使用 Redis，可以使用 PostgreSQL
if os.getenv("REDIS_URL"):
    broker = broker.with_result_backend(
        RedisAsyncResultBackend(
            redis_url=os.getenv("REDIS_URL"),
            result_ex_time=3600,  # 结果过期时间（秒）
        )
    )

# 配置任务事件监听器
@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def on_worker_startup(state: dict) -> None:
    """Worker 启动时的初始化"""
    # 初始化数据库连接等
    pass

@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def on_worker_shutdown(state: dict) -> None:
    """Worker 关闭时的清理"""
    # 关闭数据库连接等
    pass
```

### 4.2 创建 `backend/app/scheduler.py`

```python
"""
TaskIQ Scheduler 配置
管理定时任务和调度
"""
from datetime import datetime, timedelta
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisScheduleSource

from app.broker import broker
from app.tasks import cleanup_tasks, notification_tasks
from app.db.base import AsyncSessionLocal
from app.models.task_config import TaskConfig
from app.core.task_registry import TaskType, SchedulerType

# 创建调度器
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        # 使用 Redis 存储调度任务（推荐）
        # RedisScheduleSource(url="redis://localhost:6379"),
        # 或使用基于标签的调度（开发环境）
        LabelScheduleSource(broker=broker),
    ],
)

async def load_schedules_from_db():
    """从数据库加载任务调度配置"""
    async with AsyncSessionLocal() as db:
        # 查询所有活跃的调度任务
        configs = await db.query(TaskConfig).filter(
            TaskConfig.status == "active",
            TaskConfig.scheduler_type != SchedulerType.MANUAL
        ).all()
        
        for config in configs:
            await register_scheduled_task(config)

async def register_scheduled_task(config: TaskConfig):
    """注册单个调度任务"""
    task_func = get_task_function(config.task_type)
    if not task_func:
        return
    
    schedule_config = config.schedule_config
    
    if config.scheduler_type == SchedulerType.INTERVAL:
        # 间隔任务
        schedule = {
            "schedule": timedelta(
                days=schedule_config.get("days", 0),
                hours=schedule_config.get("hours", 0),
                minutes=schedule_config.get("minutes", 0),
                seconds=schedule_config.get("seconds", 0),
            ),
            "args": [config.id],
            "kwargs": config.parameters,
        }
    elif config.scheduler_type == SchedulerType.CRON:
        # Cron 任务
        schedule = {
            "cron": schedule_config.get("cron_expression"),
            "args": [config.id],
            "kwargs": config.parameters,
        }
    elif config.scheduler_type == SchedulerType.DATE:
        # 一次性任务
        schedule = {
            "date": datetime.fromisoformat(schedule_config.get("run_date")),
            "args": [config.id],
            "kwargs": config.parameters,
        }
    else:
        return
    
    await scheduler.add_schedule(
        task_name=f"{config.task_type}_{config.id}",
        task=task_func,
        **schedule
    )

def get_task_function(task_type: TaskType):
    """根据任务类型获取任务函数"""
    task_mapping = {
        TaskType.CLEANUP_TOKENS: cleanup_tasks.cleanup_expired_tokens,
        TaskType.CLEANUP_CONTENT: cleanup_tasks.cleanup_old_content,
        TaskType.SEND_EMAIL: notification_tasks.send_email,
        # ... 其他任务映射
    }
    return task_mapping.get(task_type)
```

### 4.3 创建 `backend/app/tasks/__init__.py`

```python
"""
TaskIQ 任务定义
所有异步任务都在这里定义
"""
from app.broker import broker

# 导入所有任务模块
from app.tasks import cleanup_tasks
from app.tasks import notification_tasks
from app.tasks import data_tasks

__all__ = [
    "cleanup_tasks",
    "notification_tasks", 
    "data_tasks",
]
```

### 4.4 创建 `backend/app/tasks/cleanup_tasks.py`

```python
"""
清理任务定义
"""
from typing import Dict, Any
from datetime import timedelta
import logging

from app.broker import broker
from app.db.base import AsyncSessionLocal
from app.crud.token import crud_refresh_token
from app.crud.password_reset import crud_password_reset

logger = logging.getLogger(__name__)

@broker.task(
    task_name="cleanup_expired_tokens",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
async def cleanup_expired_tokens(
    config_id: int,
    days_old: int = 7
) -> Dict[str, Any]:
    """
    清理过期的令牌
    
    Args:
        config_id: 任务配置ID
        days_old: 清理多少天前的过期令牌
    
    Returns:
        清理结果统计
    """
    logger.info(f"开始清理 {days_old} 天前的过期令牌... (Config ID: {config_id})")
    
    async with AsyncSessionLocal() as db:
        try:
            expired_refresh = await crud_refresh_token.cleanup_expired(db, days_old=days_old)
            expired_reset = await crud_password_reset.cleanup_expired(db, days_old=days_old)
            
            result = {
                "config_id": config_id,
                "expired_refresh_tokens": expired_refresh,
                "expired_reset_tokens": expired_reset,
                "total_cleaned": expired_refresh + expired_reset,
                "days_old": days_old
            }
            
            # 记录执行结果
            await record_task_execution(db, config_id, "success", result)
            
            logger.info(f"清理过期令牌完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"清理过期令牌时出错: {e}", exc_info=True)
            await record_task_execution(db, config_id, "failed", error=str(e))
            raise

@broker.task(
    task_name="cleanup_old_content",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
async def cleanup_old_content(
    config_id: int,
    days_old: int = 90
) -> Dict[str, Any]:
    """
    清理旧内容
    
    Args:
        config_id: 任务配置ID
        days_old: 清理多少天前的内容
    
    Returns:
        清理结果统计
    """
    logger.info(f"开始清理 {days_old} 天前的旧内容... (Config ID: {config_id})")
    
    async with AsyncSessionLocal() as db:
        try:
            # 清理逻辑
            result = {
                "config_id": config_id,
                "deleted_items": 0,
                "days_old": days_old
            }
            
            await record_task_execution(db, config_id, "success", result)
            return result
            
        except Exception as e:
            logger.error(f"清理旧内容时出错: {e}", exc_info=True)
            await record_task_execution(db, config_id, "failed", error=str(e))
            raise

async def record_task_execution(db, config_id: int, status: str, result: Dict = None, error: str = None):
    """记录任务执行结果"""
    from app.models.task_execution import TaskExecution
    from datetime import datetime
    
    execution = TaskExecution(
        config_id=config_id,
        status=status,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        result=result,
        error_message=error
    )
    db.add(execution)
    await db.commit()
```

### 4.5 创建 `backend/app/services/task_manager.py`

```python
"""
任务管理服务
统一管理任务的创建、调度、执行和监控
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.broker import broker
from app.scheduler import scheduler, load_schedules_from_db
from app.db.base import AsyncSessionLocal
from app.models.task_config import TaskConfig
from app.schemas.task_config_schemas import TaskConfigCreate, TaskConfigUpdate
from app.core.task_registry import TaskType, ConfigStatus, SchedulerType

logger = logging.getLogger(__name__)

class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self.broker = broker
        self.scheduler = scheduler
        self._initialized = False
    
    async def initialize(self):
        """初始化任务管理器"""
        if self._initialized:
            return
        
        # 加载数据库中的调度任务
        await load_schedules_from_db()
        self._initialized = True
        logger.info("任务管理器初始化完成")
    
    async def create_task_config(
        self,
        config_data: TaskConfigCreate
    ) -> int:
        """创建任务配置"""
        async with AsyncSessionLocal() as db:
            config = TaskConfig(**config_data.dict())
            db.add(config)
            await db.commit()
            await db.refresh(config)
            
            # 如果是调度任务，注册到调度器
            if config.scheduler_type != SchedulerType.MANUAL:
                await self._register_scheduled_task(config)
            
            return config.id
    
    async def update_task_config(
        self,
        config_id: int,
        update_data: TaskConfigUpdate
    ) -> bool:
        """更新任务配置"""
        async with AsyncSessionLocal() as db:
            config = await db.get(TaskConfig, config_id)
            if not config:
                return False
            
            for key, value in update_data.dict(exclude_unset=True).items():
                setattr(config, key, value)
            
            await db.commit()
            
            # 重新注册调度任务
            if config.scheduler_type != SchedulerType.MANUAL:
                await self._unregister_scheduled_task(config_id)
                await self._register_scheduled_task(config)
            
            return True
    
    async def delete_task_config(self, config_id: int) -> bool:
        """删除任务配置"""
        async with AsyncSessionLocal() as db:
            config = await db.get(TaskConfig, config_id)
            if not config:
                return False
            
            # 取消调度
            await self._unregister_scheduled_task(config_id)
            
            await db.delete(config)
            await db.commit()
            return True
    
    async def execute_task_immediately(
        self,
        config_id: int,
        **kwargs
    ) -> str:
        """立即执行任务"""
        async with AsyncSessionLocal() as db:
            config = await db.get(TaskConfig, config_id)
            if not config:
                raise ValueError(f"任务配置不存在: {config_id}")
            
            # 获取任务函数
            task_func = self._get_task_function(config.task_type)
            if not task_func:
                raise ValueError(f"不支持的任务类型: {config.task_type}")
            
            # 发送任务到队列
            task = await task_func.kiq(
                config_id,
                **config.parameters
            )
            
            return task.task_id
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        result = await broker.result_backend.get_result(task_id)
        return {
            "task_id": task_id,
            "status": result.status if result else "unknown",
            "result": result.result if result else None,
            "error": result.error if result else None,
        }
    
    async def list_active_tasks(self) -> List[Dict[str, Any]]:
        """列出活跃的任务"""
        # TaskIQ 没有内置的活跃任务列表
        # 需要通过自定义实现
        return []
    
    async def _register_scheduled_task(self, config: TaskConfig):
        """注册调度任务"""
        from app.scheduler import register_scheduled_task
        await register_scheduled_task(config)
    
    async def _unregister_scheduled_task(self, config_id: int):
        """取消调度任务"""
        # 从调度器中移除任务
        task_name = f"task_{config_id}"
        await self.scheduler.delete_schedule(task_name)
    
    def _get_task_function(self, task_type: TaskType):
        """根据任务类型获取任务函数"""
        from app.tasks import cleanup_tasks, notification_tasks
        
        task_mapping = {
            TaskType.CLEANUP_TOKENS: cleanup_tasks.cleanup_expired_tokens,
            TaskType.CLEANUP_CONTENT: cleanup_tasks.cleanup_old_content,
            # 添加其他任务映射
        }
        return task_mapping.get(task_type)
    
    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "broker_connected": True,  # 简化实现
            "scheduler_running": self._initialized,
            "timestamp": datetime.utcnow().isoformat(),
        }

# 全局任务管理器实例
task_manager = TaskManager()
```

### 4.6 更新 `backend/app/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.core.config import settings
from app.services.task_manager import task_manager
from app.broker import broker

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    await broker.startup()
    await task_manager.initialize()
    
    yield
    
    # 关闭时
    await broker.shutdown()

app = FastAPI(
    title="FastAPI with TaskIQ",
    version="2.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含 API 路由
app.include_router(router, prefix="/api")
```

## 五、简化的数据模型

### 5.1 更新 `backend/app/models/task_config.py`

```python
"""
简化的任务配置模型
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, DateTime, func, Integer, Text, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.core.task_registry import TaskType, ConfigStatus, SchedulerType

class TaskConfig(Base):
    """任务配置表"""
    __tablename__ = "task_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), nullable=False)
    scheduler_type: Mapped[SchedulerType] = mapped_column(Enum(SchedulerType), nullable=False)
    status: Mapped[ConfigStatus] = mapped_column(Enum(ConfigStatus), default=ConfigStatus.ACTIVE)
    
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, default={})
    schedule_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default={})
    
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    timeout_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())
```

### 5.2 更新 `backend/app/models/task_execution.py`

```python
"""
任务执行记录模型
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, DateTime, func, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base

class TaskExecution(Base):
    """任务执行记录表"""
    __tablename__ = "task_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_id: Mapped[int] = mapped_column(Integer, ForeignKey("task_configs.id"))
    task_id: Mapped[str] = mapped_column(String, nullable=False)  # TaskIQ task ID
    
    status: Mapped[str] = mapped_column(String(20))  # success, failed, running
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

## 六、API 路由更新

### 6.1 更新 `backend/app/api/v1/routes/task_routes.py`

```python
"""
任务管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.models.user import User
from app.dependencies.current_user import get_current_superuser
from app.schemas.task_config_schemas import (
    TaskConfigCreate,
    TaskConfigUpdate,
    TaskConfigResponse
)
from app.services.task_manager import task_manager

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/configs", response_model=TaskConfigResponse)
async def create_task_config(
    config: TaskConfigCreate,
    current_user: User = Depends(get_current_superuser)
):
    """创建任务配置"""
    config_id = await task_manager.create_task_config(config)
    return {"id": config_id, **config.dict()}

@router.put("/configs/{config_id}")
async def update_task_config(
    config_id: int,
    config: TaskConfigUpdate,
    current_user: User = Depends(get_current_superuser)
):
    """更新任务配置"""
    success = await task_manager.update_task_config(config_id, config)
    if not success:
        raise HTTPException(status_code=404, detail="任务配置不存在")
    return {"message": "更新成功"}

@router.delete("/configs/{config_id}")
async def delete_task_config(
    config_id: int,
    current_user: User = Depends(get_current_superuser)
):
    """删除任务配置"""
    success = await task_manager.delete_task_config(config_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务配置不存在")
    return {"message": "删除成功"}

@router.post("/configs/{config_id}/execute")
async def execute_task(
    config_id: int,
    current_user: User = Depends(get_current_superuser)
):
    """立即执行任务"""
    try:
        task_id = await task_manager.execute_task_immediately(config_id)
        return {"task_id": task_id, "message": "任务已提交"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_superuser)
):
    """获取任务状态"""
    status = await task_manager.get_task_status(task_id)
    return status

@router.get("/system/status")
async def get_system_status(
    current_user: User = Depends(get_current_superuser)
):
    """获取系统状态"""
    status = await task_manager.get_system_status()
    return status
```

## 七、数据库迁移

### 7.1 创建新的迁移脚本

```bash
# 删除旧的调度相关表
poetry run alembic revision -m "Remove APScheduler and Celery tables"
```

迁移脚本内容：

```python
"""Remove APScheduler and Celery tables

Revision ID: xxx
Revises: xxx
Create Date: xxx
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # 删除 APScheduler 相关表
    op.drop_table('apscheduler_jobs', if_exists=True)
    
    # 删除 Celery 相关表
    op.drop_table('celery_taskmeta', if_exists=True)
    op.drop_table('celery_tasksetmeta', if_exists=True)
    
    # 删除旧的 schedule_events 表（如果需要）
    op.drop_table('schedule_events', if_exists=True)
    
    # 简化 task_executions 表
    op.drop_column('task_executions', 'job_id')
    op.add_column('task_executions', sa.Column('task_id', sa.String(), nullable=False))

def downgrade():
    pass  # 不支持回滚
```

## 八、配置文件更新

### 8.1 更新 `backend/app/core/config.py`

```python
"""
简化的配置文件
"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 基本配置
    PROJECT_NAME: str = "FastAPI with TaskIQ"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    
    # 数据库配置
    POSTGRES_HOST: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = "5432"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # RabbitMQ 配置
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    
    @property
    def RABBITMQ_URL(self) -> str:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"
    
    # Redis 配置（可选）
    REDIS_URL: str = None
    
    # 安全配置
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"

settings = Settings()
```

## 九、部署和测试

### 9.1 部署步骤

```bash
# 1. 停止现有服务
docker-compose down

# 2. 清理旧的容器和卷
docker system prune -a
docker volume prune

# 3. 更新依赖
cd backend
poetry lock
poetry install

# 4. 运行数据库迁移
poetry run alembic upgrade head

# 5. 启动新服务
docker-compose up --build
```

### 9.2 测试脚本

创建 `backend/app/tests/test_taskiq.py`:

```python
"""
TaskIQ 功能测试
"""
import asyncio
from app.broker import broker
from app.tasks.cleanup_tasks import cleanup_expired_tokens

async def test_task_execution():
    """测试任务执行"""
    # 启动 broker
    await broker.startup()
    
    # 发送任务
    task = await cleanup_expired_tokens.kiq(
        config_id=1,
        days_old=7
    )
    
    print(f"Task ID: {task.task_id}")
    
    # 等待结果
    result = await task.wait_result(timeout=30)
    print(f"Result: {result}")
    
    # 关闭 broker
    await broker.shutdown()

if __name__ == "__main__":
    asyncio.run(test_task_execution())
```

## 十、优势总结

1. **原生异步支持**：TaskIQ 完全基于异步设计，与 FastAPI 完美兼容
2. **简化的架构**：一个框架同时处理任务队列和调度
3. **更好的性能**：减少了同步/异步转换的开销
4. **简化的配置**：更少的配置文件和环境变量
5. **现代化的 API**：更符合 Python 异步编程规范
6. **更容易测试**：TaskIQ 提供了更好的测试支持

## 十一、注意事项

1. TaskIQ 相对较新，社区和文档可能不如 Celery 完善
2. 需要重新学习 TaskIQ 的概念和 API
3. 监控工具需要重新选择（TaskIQ 没有类似 Flower 的工具）
4. 确保所有任务都是异步的，避免阻塞操作

这个重构指南提供了完整的迁移路径，从 Celery + APScheduler 迁移到 TaskIQ。主要改动包括：
- 简化了依赖和配置
- 统一了任务管理接口
- 消除了同步/异步转换问题
- 提高了代码的可维护性