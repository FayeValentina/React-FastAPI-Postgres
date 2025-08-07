"""
爬取相关的Celery任务
"""
from typing import Dict, Any, List
import logging
from datetime import datetime
from celery import current_task
from celery.exceptions import Retry

from app.celery_app import celery_app
from app.db.base import AsyncSessionLocal
from app.services.scraping_orchestrator import ScrapingOrchestrator
from app.models.scrape_session import SessionType
from app.crud.bot_config import CRUDBotConfig
from app.models.task_execution import ExecutionStatus
from .common_utils import run_async_task, record_task_execution

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='execute_bot_scraping_task')
def execute_bot_scraping_task(self, bot_config_id: int) -> Dict[str, Any]:
    """执行Bot配置的爬取任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
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
        run_async_task(record_task_execution(
            task_id, f"Bot爬取任务-{bot_config_id}", start_time, ExecutionStatus.SUCCESS, result
        ))
        
        logger.info(f"Bot {bot_config_id} 爬取任务完成，结果: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(record_task_execution(
            task_id, f"Bot爬取任务-{bot_config_id}", start_time, ExecutionStatus.FAILED, error=exc
        ))
        
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
        run_async_task(record_task_execution(
            task_id, f"Bot手动爬取任务-{bot_config_id}", start_time, ExecutionStatus.SUCCESS, result
        ))
    
        logger.info(f"手动爬取任务完成，结果: {result}")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(record_task_execution(
            task_id, f"Bot手动爬取任务-{bot_config_id}", start_time, ExecutionStatus.FAILED, error=exc
        ))
        
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
        run_async_task(record_task_execution(
            task_id, f"批量爬取任务-{len(bot_config_ids)}个Bot", start_time, ExecutionStatus.SUCCESS, summary
        ))
        
        logger.info(f"批量爬取任务完成，总数: {len(results)}, 成功: {successful}, 失败: {failed}")
        return summary
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(record_task_execution(
            task_id, f"批量爬取任务-{len(bot_config_ids)}个Bot", start_time, ExecutionStatus.FAILED, error=exc
        ))
        
        logger.error(f"批量爬取任务失败: {exc}")
        return {
            "status": "failed",
            "reason": str(exc),
            "bot_config_ids": bot_config_ids
        }


@celery_app.task(bind=True, name='auto_scraping_all_configs_task')
def auto_scraping_all_configs_task(self) -> Dict[str, Any]:
    """执行所有启用自动爬取的配置任务"""
    start_time = datetime.utcnow()
    task_id = self.request.id
    
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
        run_async_task(record_task_execution(
            task_id, "自动爬取所有配置任务", start_time, ExecutionStatus.SUCCESS, result
        ))
        
        logger.info(f"自动爬取任务完成，处理了 {result.get('total_configs', 0)} 个配置")
        return result
        
    except Exception as exc:
        # 记录失败执行
        run_async_task(record_task_execution(
            task_id, "自动爬取所有配置任务", start_time, ExecutionStatus.FAILED, error=exc
        ))
        
        logger.error(f"自动爬取任务失败: {exc}")
        return {
            "status": "failed",
            "reason": str(exc)
        }