# APScheduler 定时任务系统实装指南

## 一、概述

本指南描述如何在现有的 FastAPI 后端项目中实现一个基于 APScheduler 的定时任务系统。该系统充分利用 APScheduler 的内置功能，特别是 SQLAlchemyJobStore 来持久化任务配置。

### 核心特点
- 使用 SQLAlchemyJobStore 自动管理任务持久化
- 任务执行历史记录
- RESTful API 管理接口
- 支持多种触发器类型（interval、cron、date）
- 任务执行监控和统计

## 二、项目架构

### 1. 新增文件结构

```
backend/app/
├── models/
│   └── task_execution.py          # 新增：任务执行历史模型
├── schemas/
│   └── task.py                    # 新增：任务相关的Pydantic模型
├── tasks/
│   ├── __init__.py               # 修改：导出新的scheduler
│   ├── scheduler.py              # 修改：重构现有调度器
│   ├── manager.py                # 新增：任务管理器
│   └── jobs/                     # 新增：任务实现目录
│       ├── __init__.py
│       ├── cleanup.py            # 新增：清理任务
│       └── scraping.py           # 新增：爬虫任务
├── api/v1/routes/
│   └── task_routes.py            # 新增：任务管理API
└── main.py                       # 修改：集成新的调度器
```

## 三、具体实现

### 1. 新增数据模型

**文件：`backend/app/models/task_execution.py`**

```python
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, DateTime, func, Integer, Text, Enum, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum as PyEnum

from app.db.base_class import Base


class ExecutionStatus(str, PyEnum):
    """执行状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RUNNING = "running"


class TaskExecution(Base):
    """任务执行历史表"""
    __tablename__ = "task_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    job_name: Mapped[str] = mapped_column(String, nullable=False)
    
    # 执行信息
    status: Mapped[ExecutionStatus] = mapped_column(Enum(ExecutionStatus))
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    
    # 执行结果
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

### 2. 新增Schema定义

**文件：`backend/app/schemas/task.py`**

```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.task_execution import ExecutionStatus


class JobInfo(BaseModel):
    """任务信息"""
    id: str
    name: str
    trigger: str
    next_run_time: Optional[datetime] = None
    pending: bool = False
    
    # 详细信息（可选）
    func: Optional[str] = None
    args: Optional[List[Any]] = None
    kwargs: Optional[Dict[str, Any]] = None
    executor: Optional[str] = None
    max_instances: Optional[int] = None
    misfire_grace_time: Optional[int] = None
    coalesce: Optional[bool] = None


class TaskExecutionResponse(BaseModel):
    """任务执行历史响应"""
    id: int
    job_id: str
    job_name: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class JobStatsResponse(BaseModel):
    """任务统计响应"""
    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    avg_duration_seconds: float
```

### 3. 任务管理器

**文件：`backend/app/tasks/manager.py`**

```python
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from apscheduler.job import Job
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging

from app.models.task_execution import TaskExecution, ExecutionStatus

logger = logging.getLogger(__name__)


class TaskManager:
    """任务管理器 - 主要管理执行历史"""
    
    def __init__(self, scheduler):
        self.scheduler = scheduler
    
    async def record_execution(
        self,
        db: AsyncSession,
        job_id: str,
        job_name: str,
        status: ExecutionStatus,
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None
    ) -> TaskExecution:
        """记录任务执行"""
        duration = None
        if completed_at and started_at:
            duration = (completed_at - started_at).total_seconds()
        
        execution = TaskExecution(
            job_id=job_id,
            job_name=job_name,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            result=result,
            error_message=error_message,
            error_traceback=error_traceback
        )
        
        db.add(execution)
        await db.commit()
        await db.refresh(execution)
        
        return execution
    
    async def get_job_executions(
        self,
        db: AsyncSession,
        job_id: str,
        limit: int = 50
    ) -> List[TaskExecution]:
        """获取任务的执行历史"""
        result = await db.execute(
            select(TaskExecution)
            .where(TaskExecution.job_id == job_id)
            .order_by(TaskExecution.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_job_stats(
        self,
        db: AsyncSession,
        job_id: str
    ) -> Dict[str, Any]:
        """获取任务执行统计"""
        # 总执行次数
        total_result = await db.execute(
            select(func.count(TaskExecution.id))
            .where(TaskExecution.job_id == job_id)
        )
        total_runs = total_result.scalar() or 0
        
        # 成功次数
        success_result = await db.execute(
            select(func.count(TaskExecution.id))
            .where(
                TaskExecution.job_id == job_id,
                TaskExecution.status == ExecutionStatus.SUCCESS
            )
        )
        successful_runs = success_result.scalar() or 0
        
        # 平均执行时间
        avg_duration_result = await db.execute(
            select(func.avg(TaskExecution.duration_seconds))
            .where(
                TaskExecution.job_id == job_id,
                TaskExecution.status == ExecutionStatus.SUCCESS
            )
        )
        avg_duration = avg_duration_result.scalar()
        
        return {
            'total_runs': total_runs,
            'successful_runs': successful_runs,
            'failed_runs': total_runs - successful_runs,
            'success_rate': (successful_runs / total_runs * 100) if total_runs > 0 else 0,
            'avg_duration_seconds': float(avg_duration) if avg_duration else 0
        }
    
    def get_all_jobs(self) -> List[Job]:
        """获取所有任务"""
        return self.scheduler.get_jobs()
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """获取单个任务"""
        return self.scheduler.get_job(job_id)
    
    async def cleanup_old_executions(
        self,
        db: AsyncSession,
        days_to_keep: int = 30
    ) -> int:
        """清理旧的执行记录"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        result = await db.execute(
            select(TaskExecution)
            .where(TaskExecution.created_at < cutoff_date)
        )
        old_executions = result.scalars().all()
        
        for execution in old_executions:
            await db.delete(execution)
        
        await db.commit()
        return len(old_executions)
```

### 4. 重构调度器

**文件：`backend/app/tasks/scheduler.py`（替换现有文件）**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import (
    EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
)
import asyncio
import traceback
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from functools import wraps

from app.core.config import settings
from app.tasks.manager import TaskManager
from app.models.task_execution import ExecutionStatus
from app.db.base import AsyncSessionLocal

logger = logging.getLogger(__name__)


def with_task_logging(job_name: str):
    """装饰器：为任务添加执行日志记录"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            job_id = kwargs.get('_job_id', 'manual')
            
            async with AsyncSessionLocal() as db:
                manager = TaskManager(task_scheduler.scheduler)
                
                try:
                    # 执行任务
                    result = await func(*args, **kwargs)
                    
                    # 记录成功
                    await manager.record_execution(
                        db=db,
                        job_id=job_id,
                        job_name=job_name,
                        status=ExecutionStatus.SUCCESS,
                        started_at=start_time,
                        completed_at=datetime.utcnow(),
                        result=result if isinstance(result, dict) else {'result': result}
                    )
                    
                    return result
                    
                except Exception as e:
                    # 记录失败
                    await manager.record_execution(
                        db=db,
                        job_id=job_id,
                        job_name=job_name,
                        status=ExecutionStatus.FAILED,
                        started_at=start_time,
                        completed_at=datetime.utcnow(),
                        error_message=str(e),
                        error_traceback=traceback.format_exc()
                    )
                    raise
        
        return wrapper
    return decorator


class EnhancedScheduler:
    """增强的任务调度器"""
    
    def __init__(self):
        # 配置作业存储 - 使用 SQLAlchemyJobStore
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=settings.postgres.SQLALCHEMY_DATABASE_URL.replace(
                    '+asyncpg', ''  # SQLAlchemyJobStore需要同步驱动
                ),
                tablename='apscheduler_jobs'
            )
        }
        
        # 配置执行器
        executors = {
            'default': AsyncIOExecutor(),
        }
        
        # 配置作业默认设置
        job_defaults = {
            'coalesce': True,
            'max_instances': 3,
            'misfire_grace_time': 30
        }
        
        # 创建调度器
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
        self.manager = TaskManager(self.scheduler)
        self._setup_listeners()
        self._running = False
    
    def _setup_listeners(self):
        """设置事件监听器"""
        self.scheduler.add_listener(
            self._job_executed_listener,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._job_error_listener,
            EVENT_JOB_ERROR
        )
        self.scheduler.add_listener(
            self._job_missed_listener,
            EVENT_JOB_MISSED
        )
    
    def _job_executed_listener(self, event):
        """作业执行成功监听器"""
        logger.info(f"作业 {event.job_id} 执行成功")
    
    def _job_error_listener(self, event):
        """作业执行错误监听器"""
        logger.error(
            f"作业 {event.job_id} 执行失败: {event.exception}",
            exc_info=event.exception
        )
    
    def _job_missed_listener(self, event):
        """作业错过执行监听器"""
        logger.warning(f"作业 {event.job_id} 错过了执行时间")
    
    def add_job(
        self,
        func: Callable,
        trigger: str,
        id: str,
        name: str = None,
        **trigger_args
    ):
        """添加任务的便捷方法"""
        # 包装函数以传递job_id
        async def wrapped_func():
            return await func(_job_id=id)
        
        # 根据触发器类型创建触发器对象
        if trigger == 'interval':
            trigger_obj = IntervalTrigger(**trigger_args)
        elif trigger == 'cron':
            trigger_obj = CronTrigger(**trigger_args)
        elif trigger == 'date':
            trigger_obj = DateTrigger(**trigger_args)
        else:
            raise ValueError(f"不支持的触发器类型: {trigger}")
        
        self.scheduler.add_job(
            wrapped_func,
            trigger=trigger_obj,
            id=id,
            name=name or id,
            replace_existing=True
        )
    
    def remove_job(self, job_id: str):
        """移除任务"""
        self.scheduler.remove_job(job_id)
    
    def pause_job(self, job_id: str):
        """暂停任务"""
        self.scheduler.pause_job(job_id)
    
    def resume_job(self, job_id: str):
        """恢复任务"""
        self.scheduler.resume_job(job_id)
    
    def get_job(self, job_id: str):
        """获取任务信息"""
        return self.scheduler.get_job(job_id)
    
    def get_jobs(self):
        """获取所有任务"""
        return self.scheduler.get_jobs()
    
    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("调度器已经在运行")
            return
            
        self.scheduler.start()
        self._running = True
        
        # 注册所有任务
        await self._register_all_tasks()
        
        logger.info("任务调度器已启动")
        
        # 打印已加载的任务
        jobs = self.get_jobs()
        logger.info(f"已加载 {len(jobs)} 个任务")
        for job in jobs:
            logger.info(f"- {job.name} (ID: {job.id}, 下次运行: {job.next_run_time})")
    
    async def _register_all_tasks(self):
        """注册所有定时任务"""
        # 导入任务模块，这会自动注册任务
        from app.tasks.jobs import cleanup, scraping
        
        # 为所有启用自动爬取的Bot配置添加任务
        from app.crud.bot_config import CRUDBotConfig
        async with AsyncSessionLocal() as db:
            active_configs = await CRUDBotConfig.get_active_configs_for_auto_scraping(db)
            
            for config in active_configs:
                from app.tasks.jobs.scraping import create_bot_scraping_task
                await create_bot_scraping_task(config.id, config.scrape_interval_hours)
                logger.info(f"已为Bot配置 {config.id} 添加定时任务")
    
    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("任务调度器已关闭")


# 全局调度器实例
task_scheduler = EnhancedScheduler()
```

### 5. 清理任务实现

**文件：`backend/app/tasks/jobs/__init__.py`**

```python
# 确保导入所有任务模块
from . import cleanup
from . import scraping
```

**文件：`backend/app/tasks/jobs/cleanup.py`**

```python
from typing import Dict, Any
from app.tasks.scheduler import task_scheduler, with_task_logging
from app.db.base import AsyncSessionLocal
from app.crud.token import refresh_token
from app.crud.password_reset import password_reset
from app.crud.scrape_session import CRUDScrapeSession
from app.crud.reddit_content import CRUDRedditContent


@with_task_logging("清理过期令牌")
async def cleanup_expired_tokens(**kwargs) -> Dict[str, Any]:
    """清理过期令牌任务"""
    async with AsyncSessionLocal() as db:
        expired_refresh = await refresh_token.cleanup_expired(db)
        expired_reset = await password_reset.cleanup_expired(db)
        
        return {
            "expired_refresh_tokens": expired_refresh,
            "expired_reset_tokens": expired_reset,
            "total_cleaned": expired_refresh + expired_reset
        }


@with_task_logging("清理旧会话")
async def cleanup_old_sessions(**kwargs) -> Dict[str, Any]:
    """清理旧会话任务"""
    async with AsyncSessionLocal() as db:
        deleted_sessions = await CRUDScrapeSession.cleanup_old_sessions(db, days_to_keep=30)
        return {"deleted_sessions": deleted_sessions}


@with_task_logging("清理旧内容")
async def cleanup_old_content(**kwargs) -> Dict[str, Any]:
    """清理旧Reddit内容任务"""
    async with AsyncSessionLocal() as db:
        deleted_posts, deleted_comments = await CRUDRedditContent.delete_old_content(
            db, days_to_keep=90
        )
        return {
            "deleted_posts": deleted_posts,
            "deleted_comments": deleted_comments
        }


@with_task_logging("清理执行历史")
async def cleanup_execution_history(**kwargs) -> Dict[str, Any]:
    """清理旧的任务执行历史"""
    async with AsyncSessionLocal() as db:
        from app.tasks.manager import TaskManager
        manager = TaskManager(task_scheduler.scheduler)
        deleted_count = await manager.cleanup_old_executions(db, days_to_keep=30)
        return {"deleted_executions": deleted_count}


# 注册定时任务
task_scheduler.add_job(
    cleanup_expired_tokens,
    trigger='interval',
    id='cleanup_tokens',
    name='清理过期令牌',
    hours=1
)

task_scheduler.add_job(
    cleanup_old_sessions,
    trigger='cron',
    id='cleanup_sessions',
    name='清理旧会话',
    hour=2,
    minute=0
)

task_scheduler.add_job(
    cleanup_old_content,
    trigger='cron',
    id='cleanup_content',
    name='清理旧内容',
    day_of_week=6,  # 周日
    hour=2,
    minute=30
)

task_scheduler.add_job(
    cleanup_execution_history,
    trigger='cron',
    id='cleanup_executions',
    name='清理执行历史',
    hour=3,
    minute=0
)
```

### 6. 爬虫任务实现

**文件：`backend/app/tasks/jobs/scraping.py`**

```python
from typing import Dict, Any
from app.tasks.scheduler import task_scheduler, with_task_logging
from app.db.base import AsyncSessionLocal
from app.services.scraping_orchestrator import ScrapingOrchestrator
from app.models.scrape_session import SessionType
import logging

logger = logging.getLogger(__name__)


async def create_bot_scraping_task(bot_config_id: int, interval_hours: int):
    """为Bot配置创建爬取任务"""
    
    @with_task_logging(f"Bot-{bot_config_id} 自动爬取")
    async def bot_scraping_task(**kwargs) -> Dict[str, Any]:
        async with AsyncSessionLocal() as db:
            orchestrator = ScrapingOrchestrator()
            result = await orchestrator.execute_scraping_session(
                db, bot_config_id, session_type=SessionType.AUTO
            )
            return result or {"status": "failed", "reason": "no result"}
    
    # 添加到调度器
    task_scheduler.add_job(
        bot_scraping_task,
        trigger='interval',
        id=f'bot_scraping_{bot_config_id}',
        name=f'Bot-{bot_config_id} 自动爬取',
        hours=interval_hours
    )
    
    logger.info(f"已添加Bot {bot_config_id}的定时任务，执行间隔: {interval_hours}小时")
    return f'bot_scraping_{bot_config_id}'


def remove_bot_scraping_task(bot_config_id: int) -> bool:
    """移除Bot爬取任务"""
    job_id = f'bot_scraping_{bot_config_id}'
    try:
        task_scheduler.remove_job(job_id)
        logger.info(f"已移除Bot {bot_config_id}的定时任务")
        return True
    except Exception as e:
        logger.error(f"移除Bot {bot_config_id}的定时任务失败: {e}")
        return False


def update_bot_scraping_task(bot_config_id: int, interval_hours: int):
    """更新Bot爬取任务（先删除后添加）"""
    remove_bot_scraping_task(bot_config_id)
    return create_bot_scraping_task(bot_config_id, interval_hours)


@with_task_logging("批量自动爬取")
async def auto_scraping_task(**kwargs) -> Dict[str, Any]:
    """执行所有启用自动爬取的配置"""
    async with AsyncSessionLocal() as db:
        orchestrator = ScrapingOrchestrator()
        results = await orchestrator.execute_auto_scraping(db)
        
        successful = len([r for r in results if r.get('status') == 'completed'])
        failed = len([r for r in results if r.get('status') != 'completed'])
        
        return {
            "total_configs": len(results),
            "successful": successful,
            "failed": failed,
            "details": results
        }


# 注册批量自动爬取任务（可选）
# task_scheduler.add_job(
#     auto_scraping_task,
#     trigger='interval',
#     id='auto_scraping_batch',
#     name='批量自动爬取',
#     hours=6
# )
```

### 7. 任务管理API

**文件：`backend/app/api/v1/routes/task_routes.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated, List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.tasks.scheduler import task_scheduler
from app.tasks.manager import TaskManager
from app.schemas.task import JobInfo, TaskExecutionResponse, JobStatsResponse
from app.db.base import get_async_session
from app.models.user import User
from app.dependencies.current_user import get_current_superuser
from app.utils.common import handle_error

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=List[JobInfo])
async def list_jobs(
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> List[JobInfo]:
    """获取所有任务列表（需要超级管理员权限）"""
    jobs = task_scheduler.get_jobs()
    
    return [
        JobInfo(
            id=job.id,
            name=job.name,
            trigger=str(job.trigger),
            next_run_time=job.next_run_time,
            pending=job.pending
        )
        for job in jobs
    ]


@router.get("/{job_id}", response_model=JobInfo)
async def get_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> JobInfo:
    """获取任务详情（需要超级管理员权限）"""
    job = task_scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return JobInfo(
        id=job.id,
        name=job.name,
        trigger=str(job.trigger),
        next_run_time=job.next_run_time,
        pending=job.pending,
        func=job.func.__name__ if hasattr(job.func, '__name__') else str(job.func),
        args=job.args,
        kwargs=job.kwargs,
        executor=job.executor,
        max_instances=job.max_instances,
        misfire_grace_time=job.misfire_grace_time,
        coalesce=job.coalesce
    )


@router.post("/{job_id}/pause")
async def pause_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, str]:
    """暂停任务（需要超级管理员权限）"""
    try:
        task_scheduler.pause_job(job_id)
        return {"status": "paused", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{job_id}/resume")
async def resume_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, str]:
    """恢复任务（需要超级管理员权限）"""
    try:
        task_scheduler.resume_job(job_id)
        return {"status": "resumed", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{job_id}/run")
async def run_job_now(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, Any]:
    """立即运行任务（需要超级管理员权限）"""
    job = task_scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    try:
        # 立即执行任务
        # 注意：这里需要使用 asyncio.create_task 来异步执行
        asyncio.create_task(job.func())
        return {"status": "triggered", "job_id": job_id, "message": "任务已触发执行"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, str]:
    """删除任务（需要超级管理员权限）"""
    try:
        task_scheduler.remove_job(job_id)
        return {"status": "deleted", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}/executions", response_model=List[TaskExecutionResponse])
async def get_job_executions(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)],
    limit: int = Query(50, ge=1, le=200)
) -> List[TaskExecutionResponse]:
    """获取任务执行历史（需要超级管理员权限）"""
    try:
        manager = TaskManager(task_scheduler.scheduler)
        executions = await manager.get_job_executions(db, job_id, limit)
        return executions
    except Exception as e:
        raise handle_error(e)


@router.get("/{job_id}/stats", response_model=JobStatsResponse)
async def get_job_stats(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> JobStatsResponse:
    """获取任务执行统计（需要超级管理员权限）"""
    try:
        manager = TaskManager(task_scheduler.scheduler)
        stats = await manager.get_job_stats(db, job_id)
        return JobStatsResponse(**stats)
    except Exception as e:
        raise handle_error(e)


@router.get("/system/stats")
async def get_system_stats(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_superuser)]
) -> Dict[str, Any]:
    """获取系统任务统计概览（需要超级管理员权限）"""
    jobs = task_scheduler.get_jobs()
    
    # 统计各种任务类型
    task_types = {}
    for job in jobs:
        task_type = job.id.split('_')[0]  # 从job_id提取任务类型
        task_types[task_type] = task_types.get(task_type, 0) + 1
    
    return {
        "total_jobs": len(jobs),
        "active_jobs": len([j for j in jobs if not j.pending]),
        "paused_jobs": len([j for j in jobs if j.pending]),
        "task_types": task_types,
        "scheduler_running": task_scheduler._running
    }
```

### 8. 修改Bot配置相关文件

**修改文件：`backend/app/api/v1/routes/bot_config_routes.py`**

在文件末尾添加以下导入和修改相应的方法：

```python
from app.tasks.jobs.scraping import create_bot_scraping_task, remove_bot_scraping_task, update_bot_scraping_task

# 在 create_bot_config 方法的末尾添加：
@router.post("", response_model=BotConfigResponse, status_code=201)
async def create_bot_config(
    config_data: BotConfigCreate,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> BotConfigResponse:
    """创建Bot配置"""
    try:
        bot_config = await CRUDBotConfig.create_bot_config(
            # ... 现有代码 ...
        )
        
        # 如果启用了自动爬取，创建定时任务
        if bot_config.auto_scrape_enabled and bot_config.is_active:
            await create_bot_scraping_task(
                bot_config.id, 
                bot_config.scrape_interval_hours
            )
        
        return bot_config
    except Exception as e:
        raise handle_error(e)


# 在 update_bot_config 方法中添加任务更新逻辑：
@router.patch("/{config_id}", response_model=BotConfigResponse)
async def update_bot_config(
    config_id: int,
    config_update: BotConfigUpdate,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> BotConfigResponse:
    """更新Bot配置"""
    try:
        # ... 现有代码 ...
        
        # 只更新提供的字段
        update_data = config_update.model_dump(exclude_unset=True)
        updated_config = await CRUDBotConfig.update_bot_config(
            db, config_id, **update_data
        )
        
        if not updated_config:
            raise HTTPException(status_code=404, detail="更新失败")
        
        # 更新定时任务
        if updated_config.auto_scrape_enabled and updated_config.is_active:
            await update_bot_scraping_task(
                updated_config.id,
                updated_config.scrape_interval_hours
            )
        else:
            remove_bot_scraping_task(updated_config.id)
            
        return updated_config
    except Exception as e:
        raise handle_error(e)


# 在 delete_bot_config 方法中添加任务删除逻辑：
@router.delete("/{config_id}", status_code=204)
async def delete_bot_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> None:
    """删除Bot配置"""
    try:
        await get_accessible_bot_config(db, config_id, current_user)
        
        # 删除定时任务
        remove_bot_scraping_task(config_id)
        
        success = await CRUDBotConfig.delete_bot_config(db, config_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="删除失败")
    except Exception as e:
        raise handle_error(e)
```

### 9. 更新路由配置

**修改文件：`backend/app/api/v1/router.py`**

添加任务路由：

```python
from app.api.v1.routes import (
    user_routes,
    auth_routes,
    bot_config_routes,
    reddit_content_routes,
    scraping_routes,
    task_routes  # 新增
)

# 创建主路由
router = APIRouter()

# 包含核心路由
router.include_router(user_routes.router)
router.include_router(auth_routes.router)
router.include_router(bot_config_routes.router)
router.include_router(reddit_content_routes.router)
router.include_router(scraping_routes.router)
router.include_router(task_routes.router)  # 新增
```

### 10. 更新主应用文件

**修改文件：`backend/app/main.py`**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    from app.tasks.scheduler import task_scheduler
    await task_scheduler.start()
    
    yield
    
    # 关闭时
    task_scheduler.shutdown()
```

### 11. 更新tasks模块导出

**修改文件：`backend/app/tasks/__init__.py`**

```python
from .scheduler import task_scheduler
from .manager import TaskManager

__all__ = ["task_scheduler", "TaskManager"]
```

### 12. 更新数据库导入

**修改文件：`backend/app/db/base.py`**

在导入部分添加：

```python
# Import all models here for Alembic
from app.models.user import User
from app.models.token import RefreshToken
from app.models.password_reset import PasswordReset
from app.models.bot_config import BotConfig
from app.models.scrape_session import ScrapeSession
from app.models.reddit_content import RedditPost, RedditComment
from app.models.task_execution import TaskExecution  # 新增

# Re-export Base and all models for Alembic
__all__ = [
    "Base", 
    "User", 
    "RefreshToken", 
    "PasswordReset",
    "BotConfig",
    "ScrapeSession",
    "RedditPost",
    "RedditComment",
    "TaskExecution"  # 新增
]
```

### 13. 创建数据库迁移

在完成所有代码更改后，需要创建数据库迁移：

```bash
# 生成迁移文件
alembic revision --autogenerate -m "Add task execution history table"

# 执行迁移
alembic upgrade head
```

## 四、API使用示例

### 1. 查看所有任务
```http
GET /api/v1/tasks
Authorization: Bearer {token}
```

### 2. 查看任务详情
```http
GET /api/v1/tasks/{job_id}
Authorization: Bearer {token}
```

### 3. 暂停任务
```http
POST /api/v1/tasks/{job_id}/pause
Authorization: Bearer {token}
```

### 4. 恢复任务
```http
POST /api/v1/tasks/{job_id}/resume
Authorization: Bearer {token}
```

### 5. 立即执行任务
```http
POST /api/v1/tasks/{job_id}/run
Authorization: Bearer {token}
```

### 6. 查看任务执行历史
```http
GET /api/v1/tasks/{job_id}/executions?limit=50
Authorization: Bearer {token}
```

### 7. 查看任务统计
```http
GET /api/v1/tasks/{job_id}/stats
Authorization: Bearer {token}
```

## 五、注意事项

1. **数据库连接**：SQLAlchemyJobStore 需要同步数据库驱动，所以在配置中将 `+asyncpg` 替换为空字符串。

2. **任务持久化**：任务配置会自动保存在 `apscheduler_jobs` 表中，重启后会自动恢复。

3. **执行历史**：所有任务执行历史保存在 `task_executions` 表中，定期清理以避免数据过多。

4. **权限控制**：所有任务管理API需要超级管理员权限。

5. **Bot任务管理**：Bot配置的创建、更新、删除会自动管理相应的定时任务。

6. **异步执行**：所有任务都是异步执行的，不会阻塞主线程。