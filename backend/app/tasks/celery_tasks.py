"""
Celery任务定义
"""
from typing import Dict, Any, List
import asyncio
import logging
from celery import current_task
from celery.exceptions import Retry

from app.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.services.scraping_orchestrator import ScrapingOrchestrator
from app.models.scrape_session import SessionType
from app.crud.bot_config import CRUDBotConfig
from app.crud.scrape_session import CRUDScrapeSession
from app.models.task_execution import TaskExecution, ExecutionStatus
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def run_async_task(coro):
    """在Celery任务中运行异步函数的辅助函数"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, name='execute_bot_scraping_task')
def execute_bot_scraping_task(self, bot_config_id: int) -> Dict[str, Any]:
    """执行Bot配置的爬取任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
    async def _record_execution(status, result=None, error=None):
        async with AsyncSessionLocal() as db:
            execution = TaskExecution(
                job_id=task_id,
                job_name=f"Bot爬取任务-{bot_config_id}",
                status=status,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                result=result,
                error_message=str(error) if error else None
            )
            db.add(execution)
            await db.commit()
    try:
        logger.info(f"开始执行Bot {bot_config_id} 的爬取任务")
        
        async def _execute():
            async with AsyncSessionLocal() as db:
                orchestrator = ScrapingOrchestrator()
                result = await orchestrator.execute_scraping_session(
                    db, bot_config_id, session_type=SessionType.AUTO
                )
                return result or {"status": "failed", "reason": "no result"}
        
        result = run_async_task(_execute())
        
        # 记录成功执行
        run_async_task(_record_execution(ExecutionStatus.SUCCESS, result))
        
        logger.info(f"Bot {bot_config_id} 爬取任务完成，结果: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(_record_execution(ExecutionStatus.FAILED, error=exc))
        
        logger.error(f"Bot {bot_config_id} 爬取任务失败: {exc}")
        
        # 重试逻辑
        if self.request.retries < self.max_retries:
            logger.info(f"第 {self.request.retries + 1} 次重试Bot {bot_config_id}的任务")
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)
        
        return {
            "status": "failed",
            "reason": str(exc),
            "bot_config_id": bot_config_id,
            "retries": self.request.retries
        }


@celery_app.task(bind=True, name='manual_scraping_task')
def manual_scraping_task(
    self, 
    bot_config_id: int, 
    session_type: str = "manual"
) -> Dict[str, Any]:
    """手动触发的爬取任务"""

    start_time = datetime.utcnow()
    task_id = self.request.id
    
    async def _record_execution(status, result=None, error=None):
        async with AsyncSessionLocal() as db:
            execution = TaskExecution(
                job_id=task_id,
                job_name=f"Bot手动爬取任务-{bot_config_id}",
                status=status,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                result=result,
                error_message=str(error) if error else None
            )
            db.add(execution)
            await db.commit()
    try:
        logger.info(f"开始执行手动爬取任务，Bot ID: {bot_config_id}")
        
        async def _execute():
            async with AsyncSessionLocal() as db:
                orchestrator = ScrapingOrchestrator()
                session_type_enum = SessionType.MANUAL if session_type == "manual" else SessionType.AUTO
                result = await orchestrator.execute_scraping_session(
                    db, bot_config_id, session_type=session_type_enum
                )
                return result or {"status": "failed", "reason": "no result"}
        
        result = run_async_task(_execute())

        # 记录成功执行
        run_async_task(_record_execution(ExecutionStatus.SUCCESS, result))
    
        logger.info(f"手动爬取任务完成，结果: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(_record_execution(ExecutionStatus.FAILED, error=exc))
        
        logger.error(f"手动爬取任务失败: {exc}")
        
        # 手动任务通常不重试，但可以根据需要调整
        return {
            "status": "failed",
            "reason": str(exc),
            "bot_config_id": bot_config_id,
            "session_type": session_type
        }


@celery_app.task(bind=True, name='batch_scraping_task')
def batch_scraping_task(
    self, 
    bot_config_ids: List[int], 
    session_type: str = "manual"
) -> Dict[str, Any]:
    """批量爬取任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
    async def _record_execution(status, result=None, error=None):
        async with AsyncSessionLocal() as db:
            execution = TaskExecution(
                job_id=task_id,
                job_name=f"批量爬取任务-{len(bot_config_ids)}个Bot",
                status=status,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                result=result,
                error_message=str(error) if error else None
            )
            db.add(execution)
            await db.commit()
    
    try:
        logger.info(f"开始执行批量爬取任务，Bot IDs: {bot_config_ids}")
        
        async def _execute():
            results = []
            async with AsyncSessionLocal() as db:
                orchestrator = ScrapingOrchestrator()
                session_type_enum = SessionType.MANUAL if session_type == "manual" else SessionType.AUTO
                
                for bot_config_id in bot_config_ids:
                    try:
                        result = await orchestrator.execute_scraping_session(
                            db, bot_config_id, session_type=session_type_enum
                        )
                        results.append({
                            "bot_config_id": bot_config_id,
                            "result": result or {"status": "failed", "reason": "no result"}
                        })
                    except Exception as e:
                        logger.error(f"批量爬取中Bot {bot_config_id} 失败: {e}")
                        results.append({
                            "bot_config_id": bot_config_id,
                            "result": {"status": "failed", "reason": str(e)}
                        })
            
            return results
        
        results = run_async_task(_execute())
        
        # 统计结果
        successful = len([r for r in results if r["result"].get("status") == "completed"])
        failed = len(results) - successful
        
        summary = {
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "results": results
        }
        
        # 记录成功执行
        run_async_task(_record_execution(ExecutionStatus.SUCCESS, summary))
        
        logger.info(f"批量爬取任务完成，总数: {len(results)}, 成功: {successful}, 失败: {failed}")
        return summary
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(_record_execution(ExecutionStatus.FAILED, error=exc))
        
        logger.error(f"批量爬取任务失败: {exc}")
        return {
            "status": "failed",
            "reason": str(exc),
            "bot_config_ids": bot_config_ids
        }


@celery_app.task(bind=True, name='cleanup_old_sessions_task')
def cleanup_old_sessions_task(self, days_old: int = 30) -> Dict[str, Any]:
    """清理旧的爬取会话任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
    async def _record_execution(status, result=None, error=None):
        async with AsyncSessionLocal() as db:
            execution = TaskExecution(
                job_id=task_id,
                job_name=f"清理旧会话任务-{days_old}天前",
                status=status,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                result=result,
                error_message=str(error) if error else None
            )
            db.add(execution)
            await db.commit()
    
    try:
        logger.info(f"开始执行清理任务，删除{days_old}天前的会话")
        
        async def _execute():
            async with AsyncSessionLocal() as db:
                cutoff_date = datetime.utcnow() - timedelta(days=days_old)
                
                # 获取要删除的会话数量
                old_sessions = await CRUDScrapeSession.get_sessions_before_date(
                    db, cutoff_date
                )
                session_count = len(old_sessions)
                
                if session_count > 0:
                    # 删除旧会话
                    deleted_count = await CRUDScrapeSession.delete_sessions_before_date(
                        db, cutoff_date
                    )
                    logger.info(f"成功删除 {deleted_count} 个旧会话")
                    return {
                        "status": "completed",
                        "deleted_sessions": deleted_count,
                        "cutoff_date": cutoff_date.isoformat()
                    }
                else:
                    logger.info("没有找到需要清理的旧会话")
                    return {
                        "status": "completed",
                        "deleted_sessions": 0,
                        "message": "没有需要清理的会话"
                    }
        
        result = run_async_task(_execute())
        
        # 记录成功执行
        run_async_task(_record_execution(ExecutionStatus.SUCCESS, result))
        
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(_record_execution(ExecutionStatus.FAILED, error=exc))
        
        logger.error(f"清理任务失败: {exc}")
        
        # 清理任务失败时重试
        if self.request.retries < self.max_retries:
            logger.info(f"第 {self.request.retries + 1} 次重试清理任务")
            raise self.retry(countdown=300, exc=exc)  # 5分钟后重试
        
        return {
            "status": "failed",
            "reason": str(exc),
            "retries": self.request.retries
        }


@celery_app.task(bind=True, name='cleanup_expired_tokens_task')
def cleanup_expired_tokens_task(self) -> Dict[str, Any]:
    """清理过期令牌任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
    async def _record_execution(status, result=None, error=None):
        async with AsyncSessionLocal() as db:
            execution = TaskExecution(
                job_id=task_id,
                job_name="清理过期令牌任务",
                status=status,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                result=result,
                error_message=str(error) if error else None
            )
            db.add(execution)
            await db.commit()
    
    try:
        async def _execute():
            async with AsyncSessionLocal() as db:
                from app.crud.token import refresh_token
                from app.crud.password_reset import password_reset
                
                expired_refresh = await refresh_token.cleanup_expired(db)
                expired_reset = await password_reset.cleanup_expired(db)
                
                return {
                    "expired_refresh_tokens": expired_refresh,
                    "expired_reset_tokens": expired_reset,
                    "total_cleaned": expired_refresh + expired_reset
                }
        
        result = run_async_task(_execute())
        
        # 记录成功执行
        run_async_task(_record_execution(ExecutionStatus.SUCCESS, result))
        
        logger.info(f"清理过期令牌完成: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(_record_execution(ExecutionStatus.FAILED, error=exc))
        
        logger.error(f"清理过期令牌失败: {exc}")
        return {"status": "failed", "reason": str(exc)}


@celery_app.task(bind=True, name='cleanup_old_content_task')
def cleanup_old_content_task(self, days_old: int = 90) -> Dict[str, Any]:
    """清理旧Reddit内容任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
    async def _record_execution(status, result=None, error=None):
        async with AsyncSessionLocal() as db:
            execution = TaskExecution(
                job_id=task_id,
                job_name=f"清理旧内容任务-{days_old}天前",
                status=status,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                result=result,
                error_message=str(error) if error else None
            )
            db.add(execution)
            await db.commit()
    
    try:
        async def _execute():
            async with AsyncSessionLocal() as db:
                from app.crud.reddit_content import CRUDRedditContent
                deleted_posts, deleted_comments = await CRUDRedditContent.delete_old_content(
                    db, days_to_keep=days_old
                )
                return {
                    "deleted_posts": deleted_posts,
                    "deleted_comments": deleted_comments,
                    "total_deleted": deleted_posts + deleted_comments
                }
        
        result = run_async_task(_execute())
        
        # 记录成功执行
        run_async_task(_record_execution(ExecutionStatus.SUCCESS, result))
        
        logger.info(f"清理旧内容完成: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(_record_execution(ExecutionStatus.FAILED, error=exc))
        
        logger.error(f"清理旧内容失败: {exc}")
        return {"status": "failed", "reason": str(exc)}


@celery_app.task(bind=True, name='auto_scraping_all_configs_task')
def auto_scraping_all_configs_task(self) -> Dict[str, Any]:
    """执行所有启用自动爬取的配置任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
    async def _record_execution(status, result=None, error=None):
        async with AsyncSessionLocal() as db:
            execution = TaskExecution(
                job_id=task_id,
                job_name="自动爬取所有配置任务",
                status=status,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                result=result,
                error_message=str(error) if error else None
            )
            db.add(execution)
            await db.commit()
    
    try:
        logger.info("开始执行所有自动爬取配置的任务")
        
        async def _execute():
            async with AsyncSessionLocal() as db:
                # 获取所有启用自动爬取的配置
                active_configs = await CRUDBotConfig.get_active_configs_for_auto_scraping(db)
                
                if not active_configs:
                    return {
                        "status": "completed",
                        "message": "没有启用自动爬取的配置",
                        "total_configs": 0
                    }
                
                results = []
                orchestrator = ScrapingOrchestrator()
                
                for config in active_configs:
                    try:
                        result = await orchestrator.execute_scraping_session(
                            db, config.id, session_type=SessionType.AUTO
                        )
                        results.append({
                            "config_id": config.id,
                            "config_name": config.name,
                            "result": result or {"status": "failed", "reason": "no result"}
                        })
                    except Exception as e:
                        logger.error(f"自动爬取配置 {config.id} 失败: {e}")
                        results.append({
                            "config_id": config.id,
                            "config_name": config.name,
                            "result": {"status": "failed", "reason": str(e)}
                        })
                
                # 统计结果
                successful = len([r for r in results if r["result"].get("status") == "completed"])
                failed = len(results) - successful
                
                return {
                    "status": "completed",
                    "total_configs": len(results),
                    "successful": successful,
                    "failed": failed,
                    "results": results
                }
        
        result = run_async_task(_execute())
        
        # 记录成功执行
        run_async_task(_record_execution(ExecutionStatus.SUCCESS, result))
        
        logger.info(f"自动爬取任务完成，处理了 {result.get('total_configs', 0)} 个配置")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(_record_execution(ExecutionStatus.FAILED, error=exc))
        
        logger.error(f"自动爬取任务失败: {exc}")
        return {
            "status": "failed",
            "reason": str(exc)
        }


@celery_app.task(bind=True, name='cleanup_schedule_events_task')
def cleanup_schedule_events_task(self, days_old: int = 30) -> Dict[str, Any]:
    """清理旧的调度事件任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
    async def _record_execution(status, result=None, error=None):
        async with AsyncSessionLocal() as db:
            execution = TaskExecution(
                job_id=task_id,
                job_name=f"清理调度事件任务-{days_old}天前",
                status=status,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                result=result,
                error_message=str(error) if error else None
            )
            db.add(execution)
            await db.commit()
    
    try:
        async def _execute():
            async with AsyncSessionLocal() as db:
                from app.crud.schedule_event import CRUDScheduleEvent
                deleted_count = await CRUDScheduleEvent.cleanup_old_events(db, days_old)
                return {
                    "deleted_events": deleted_count,
                    "days_old": days_old
                }
        
        result = run_async_task(_execute())
        
        # 记录成功执行
        run_async_task(_record_execution(ExecutionStatus.SUCCESS, result))
        
        logger.info(f"清理调度事件完成: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(_record_execution(ExecutionStatus.FAILED, error=exc))
        
        logger.error(f"清理调度事件失败: {exc}")
        return {"status": "failed", "reason": str(exc)}
