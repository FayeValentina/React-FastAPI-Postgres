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
        logger.info(f"Bot {bot_config_id} 爬取任务完成，结果: {result}")
        return result
        
    except Exception as exc:
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
        logger.info(f"手动爬取任务完成，结果: {result}")
        return result
        
    except Exception as exc:
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
        
        logger.info(f"批量爬取任务完成，总数: {len(results)}, 成功: {successful}, 失败: {failed}")
        return summary
        
    except Exception as exc:
        logger.error(f"批量爬取任务失败: {exc}")
        return {
            "status": "failed",
            "reason": str(exc),
            "bot_config_ids": bot_config_ids
        }


@celery_app.task(bind=True, name='cleanup_old_sessions_task')
def cleanup_old_sessions_task(self, days_old: int = 30) -> Dict[str, Any]:
    """清理旧的爬取会话任务"""
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
        return result
        
    except Exception as exc:
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


@celery_app.task(bind=True, name='auto_scraping_all_configs_task')
def auto_scraping_all_configs_task(self) -> Dict[str, Any]:
    """执行所有启用自动爬取的配置任务"""
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
        logger.info(f"自动爬取任务完成，处理了 {result.get('total_configs', 0)} 个配置")
        return result
        
    except Exception as exc:
        logger.error(f"自动爬取任务失败: {exc}")
        return {
            "status": "failed",
            "reason": str(exc)
        }


# 任务状态检查辅助函数
def get_task_info(task_id: str) -> Dict[str, Any]:
    """获取任务信息"""
    try:
        result = celery_app.AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result,
            "traceback": result.traceback,
            "date_done": result.date_done.isoformat() if result.date_done else None,
        }
    except Exception as e:
        return {
            "task_id": task_id,
            "status": "UNKNOWN",
            "error": str(e)
        }