"""
任务共享工具模块
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


def run_async_task(coro):
    """在Celery任务中运行异步函数的辅助函数"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)