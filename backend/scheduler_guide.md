# FastAPI项目定时任务实装指南

## 概述

本文档详细说明如何在当前FastAPI项目中实装APScheduler定时任务系统，替换现有的BackgroundTasks机制，实现真正的自动化定时任务。

---

## 1. APScheduler安装配置

### 1.1 Poetry依赖管理

在 `backend/pyproject.toml` 文件的 `[tool.poetry.dependencies]` 部分添加：

```toml
# backend/pyproject.toml
[tool.poetry.dependencies]
# ... 现有依赖 ...
apscheduler = "^3.10.4"
```

然后执行安装：
```bash
cd backend
poetry install
```

### 1.2 验证安装
```bash
poetry show apscheduler
```

---

## 2. 项目中需要定时执行的方法

### 2.1 令牌清理类任务

| 方法 | 文件位置 | 执行频率 | 说明 |
|------|----------|----------|------|
| `refresh_token.cleanup_expired()` | `backend/app/crud/token.py` | 每小时 | 清理过期的刷新令牌 |
| `password_reset.cleanup_expired()` | `backend/app/crud/password_reset.py` | 每小时 | 清理过期的密码重置令牌 |

### 2.2 数据清理类任务

| 方法 | 文件位置 | 执行频率 | 说明 |
|------|----------|----------|------|
| `CRUDScrapeSession.cleanup_old_sessions()` | `backend/app/crud/scrape_session.py` | 每天02:00 | 清理30天前的爬取会话 |
| `CRUDRedditContent.delete_old_content()` | `backend/app/crud/reddit_content.py` | 每周日02:00 | 清理90天前的Reddit内容 |

### 2.3 业务逻辑类任务

| 方法 | 文件位置 | 执行频率 | 说明 |
|------|----------|----------|------|
| `ScrapingOrchestrator.get_active_configs_and_execute()` | `backend/app/services/scraping_orchestrator.py` | 每6小时 | 执行启用自动爬取的配置 |

---

## 3. 定时任务调度器实现

### 3.1 创建调度器文件

创建 `backend/app/tasks/scheduler.py`：

```python
# backend/app/tasks/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from typing import Optional

from app.db.base import AsyncSessionLocal
from app.crud.token import refresh_token
from app.crud.password_reset import password_reset
from app.crud.scrape_session import CRUDScrapeSession
from app.crud.reddit_content import CRUDRedditContent
from app.services.scraping_orchestrator import ScrapingOrchestrator

logger = logging.getLogger(__name__)

class TaskScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running = False
    
    async def cleanup_expired_tokens(self):
        """清理过期令牌任务 - 每小时执行"""
        try:
            async with AsyncSessionLocal() as db:
                # 清理过期的刷新令牌
                expired_refresh_tokens = await refresh_token.cleanup_expired(db)
                # 清理过期的密码重置令牌
                expired_reset_tokens = await password_reset.cleanup_expired(db)
                
                logger.info(f"令牌清理完成: {expired_refresh_tokens}个刷新令牌, {expired_reset_tokens}个重置令牌")
        except Exception as e:
            logger.error(f"令牌清理任务失败: {e}")
    
    async def cleanup_old_sessions(self):
        """清理旧爬取会话 - 每天执行"""
        try:
            async with AsyncSessionLocal() as db:
                deleted_sessions = await CRUDScrapeSession.cleanup_old_sessions(db, days_to_keep=30)
                logger.info(f"会话清理完成: 删除了{deleted_sessions}个旧会话")
        except Exception as e:
            logger.error(f"会话清理任务失败: {e}")
    
    async def cleanup_old_content(self):
        """清理旧Reddit内容 - 每周执行"""
        try:
            async with AsyncSessionLocal() as db:
                deleted_posts, deleted_comments = await CRUDRedditContent.delete_old_content(db, days_to_keep=90)
                logger.info(f"内容清理完成: 删除了{deleted_posts}个帖子, {deleted_comments}条评论")
        except Exception as e:
            logger.error(f"内容清理任务失败: {e}")
    
    async def auto_scraping_task(self):
        """自动爬取任务 - 每6小时执行"""
        try:
            async with AsyncSessionLocal() as db:
                orchestrator = ScrapingOrchestrator()
                results = await orchestrator.get_active_configs_and_execute(db)
                
                if results:
                    successful = len([r for r in results if r.get('status') != 'error'])
                    logger.info(f"自动爬取完成: {successful}/{len(results)}个配置成功执行")
                else:
                    logger.info("自动爬取检查完成: 没有启用自动爬取的配置")
        except Exception as e:
            logger.error(f"自动爬取任务失败: {e}")
    
    def start(self):
        """启动所有定时任务"""
        if self._running:
            logger.warning("调度器已经在运行")
            return
        
        # 1. 每小时清理过期令牌 (每小时的0分执行)
        self.scheduler.add_job(
            self.cleanup_expired_tokens,
            CronTrigger(minute=0),
            id='cleanup_tokens',
            name='清理过期令牌',
            replace_existing=True
        )
        
        # 2. 每天凌晨2点清理旧会话
        self.scheduler.add_job(
            self.cleanup_old_sessions,
            CronTrigger(hour=2, minute=0),
            id='cleanup_sessions',
            name='清理旧会话',
            replace_existing=True
        )
        
        # 3. 每周日凌晨2点30分清理旧内容
        self.scheduler.add_job(
            self.cleanup_old_content,
            CronTrigger(day_of_week=6, hour=2, minute=30),  # 周日=6
            id='cleanup_content',
            name='清理旧内容',
            replace_existing=True
        )
        
        # 4. 每6小时检查自动爬取 (00:00, 06:00, 12:00, 18:00)
        self.scheduler.add_job(
            self.auto_scraping_task,
            CronTrigger(hour='0,6,12,18', minute=0),
            id='auto_scraping',
            name='自动爬取检查',
            replace_existing=True
        )
        
        self.scheduler.start()
        self._running = True
        logger.info("定时任务调度器已启动")
        
        # 打印已注册的任务
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            logger.info(f"已注册任务: {job.name} (ID: {job.id})")
    
    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("定时任务调度器已关闭")

# 全局调度器实例
task_scheduler = TaskScheduler()
```

### 3.2 创建任务包初始化文件

创建 `backend/app/tasks/__init__.py`：

```python
# backend/app/tasks/__init__.py
from .scheduler import task_scheduler

__all__ = ["task_scheduler"]
```

### 3.3 在主应用中集成

修改 `backend/app/main.py`：

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
# ... 其他导入 ...

# 导入定时任务调度器
from app.tasks import task_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    task_scheduler.start()
    
    yield
    
    # 关闭时
    task_scheduler.shutdown()

# 更新FastAPI应用配置
app = FastAPI(
    title="FastAPI Demo",
    description="A demo FastAPI application with restructured routes",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    dependencies=[Depends(request_context_dependency)],
    exception_handlers=create_exception_handlers(),
    lifespan=lifespan  # 添加生命周期管理
)

# ... 其余代码保持不变 ...
```

---

## 4. 修改爬取路由 - 取消BackgroundTasks

### 4.1 当前问题分析

`backend/app/api/v1/routes/scraping_routes.py` 中的 `trigger_scraping` 端点目前使用 `BackgroundTasks` 进行单次后台执行，这不是真正的定时任务。

### 4.2 修改方案

**方案A: 完全移除手动触发**
```python
# 完全删除 trigger_scraping 端点，只依靠定时任务
```

**方案B: 保留手动触发但简化逻辑（推荐）**
```python
# backend/app/api/v1/routes/scraping_routes.py

# 删除或注释掉原来的 trigger_scraping 方法
# @router.post("/bot-configs/{config_id}/scrape", response_model=ScrapeTriggerResponse)
# async def trigger_scraping(...):
#     ... 原有代码 ...

# 替换为简化的手动触发版本
@router.post("/bot-configs/{config_id}/scrape-now", response_model=ScrapeTriggerResponse)
async def trigger_scraping_now(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> ScrapeTriggerResponse:
    """
    立即执行指定配置的爬取任务（同步执行）
    注意：这是同步执行，可能需要较长时间
    """
    try:
        # 检查配置权限
        bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)
        if not bot_config:
            raise HTTPException(status_code=404, detail="Bot配置不存在")
        
        if bot_config.user_id != current_user.id and not current_user.is_superuser:
            raise InsufficientPermissionsError("没有权限操作此配置")
        
        if not bot_config.is_active:
            raise HTTPException(status_code=400, detail="Bot配置未激活")
        
        # 直接执行爬取（同步）
        orchestrator = ScrapingOrchestrator()
        result = await orchestrator.execute_scraping_session(
            db, bot_config_id=config_id, session_type='manual'
        )
        
        if result and result.get('status') == 'completed':
            return ScrapeTriggerResponse(
                session_id=result.get('session_id', 0),
                status="completed",
                message=f"爬取完成: {result.get('total_posts', 0)}个帖子, {result.get('total_comments', 0)}条评论"
            )
        else:
            return ScrapeTriggerResponse(
                session_id=0,
                status="failed",
                message="爬取执行失败"
            )
            
    except Exception as e:
        raise handle_error(e)
```

### 4.3 移除BackgroundTasks相关导入

在 `scraping_routes.py` 文件顶部：

```python
# 删除这行导入
# from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

# 改为
from fastapi import APIRouter, Depends, HTTPException
```

---

## 5. 验证定时任务是否正常工作

### 5.1 查看日志

启动应用后，查看日志中是否有以下信息：
```
INFO: 定时任务调度器已启动
INFO: 已注册任务: 清理过期令牌 (ID: cleanup_tokens)
INFO: 已注册任务: 清理旧会话 (ID: cleanup_sessions)
INFO: 已注册任务: 清理旧内容 (ID: cleanup_content)
INFO: 已注册任务: 自动爬取检查 (ID: auto_scraping)
```

### 5.2 测试端点

创建临时测试端点来验证任务执行：

```python
# 可以临时添加到任意路由文件中用于测试
@router.get("/test/trigger-cleanup-tokens")
async def test_cleanup_tokens():
    """测试令牌清理任务"""
    from app.tasks import task_scheduler
    await task_scheduler.cleanup_expired_tokens()
    return {"message": "令牌清理任务执行完成"}

@router.get("/test/trigger-auto-scraping")
async def test_auto_scraping():
    """测试自动爬取任务"""
    from app.tasks import task_scheduler
    await task_scheduler.auto_scraping_task()
    return {"message": "自动爬取任务执行完成"}
```

---

## 6. 部署注意事项

### 6.1 时区设置

确保服务器时区正确，或在调度器中指定时区：

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

self.scheduler = AsyncIOScheduler(timezone='Asia/Shanghai')  # 设置时区
```

### 6.2 多实例部署

如果使用多个实例部署，需要确保定时任务只在一个实例中运行，避免重复执行：

```python
# 可以通过环境变量控制
import os

class TaskScheduler:
    def start(self):
        # 只在主实例中启动定时任务
        if os.getenv('ENABLE_SCHEDULER', 'false').lower() == 'true':
            # ... 启动调度器
        else:
            logger.info("定时任务调度器已禁用（非主实例）")
```

---

## 7. 总结

完成上述步骤后，你的FastAPI项目将具备：

1. ✅ **自动令牌清理** - 每小时清理过期令牌
2. ✅ **自动数据清理** - 定期清理旧的会话和内容数据
3. ✅ **自动爬取执行** - 每6小时检查并执行启用自动爬取的配置
4. ✅ **优雅的启动/关闭** - 随应用启动和关闭
5. ✅ **完整的日志记录** - 便于监控和调试

原有的手动触发功能可以保留但简化，真正的定时自动化通过APScheduler实现。