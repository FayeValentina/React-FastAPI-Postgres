from typing import Dict, Any
from app.tasks.scheduler import task_scheduler
from app.tasks.decorators import with_task_logging
from app.db.base import AsyncSessionLocal
from app.services.scraping_orchestrator import ScrapingOrchestrator
from app.models.scrape_session import SessionType
import logging

logger = logging.getLogger(__name__)


@with_task_logging("Bot自动爬取")
async def execute_bot_scraping(bot_config_id: int, **kwargs) -> Dict[str, Any]:
    """执行Bot配置的爬取任务"""
    async with AsyncSessionLocal() as db:
        orchestrator = ScrapingOrchestrator()
        result = await orchestrator.execute_scraping_session(
            db, bot_config_id, session_type=SessionType.AUTO
        )
        return result or {"status": "failed", "reason": "no result"}


async def create_bot_scraping_task(bot_config_id: int, bot_config_name: str, interval_hours: int):
    """为Bot配置创建爬取任务"""
    
    # 添加到调度器，使用文本引用避免序列化问题
    task_scheduler.add_job(
        'app.tasks.jobs.scraping:execute_bot_scraping',
        trigger='interval',
        id=f'bot_scraping_{bot_config_id}',
        name=f'Bot-{bot_config_name} 自动爬取',
        args=[bot_config_id],
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


async def update_bot_scraping_task(bot_config_id: int, bot_config_name: str, interval_hours: int):
    """更新Bot爬取任务（先删除后添加）"""
    remove_bot_scraping_task(bot_config_id)
    return await create_bot_scraping_task(bot_config_id, bot_config_name, interval_hours)


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
#     'app.tasks.jobs.scraping:auto_scraping_task',
#     trigger='interval',
#     id='auto_scraping_batch',
#     name='批量自动爬取',
#     hours=6
# )