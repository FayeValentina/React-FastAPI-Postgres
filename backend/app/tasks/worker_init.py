"""
Celery Worker 初始化钩子
为每个 Worker 进程配置独立的数据库连接
"""
import logging
import os
from celery.signals import worker_process_init, worker_process_shutdown

from app.db.engine_manager import engine_manager

logger = logging.getLogger(__name__)


@worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Worker 进程初始化钩子
    
    在每个 Worker 进程启动时调用，确保：
    1. 每个进程有独立的数据库引擎
    2. 避免继承父进程的连接池
    """
    pid = os.getpid()
    logger.info(f"初始化 Worker 进程 {pid}")
    
    try:
        # 强制创建新的引擎（engine_manager 会自动检测进程变化）
        engine = engine_manager.get_engine()
        logger.info(f"Worker 进程 {pid} 的数据库引擎初始化成功")
    except Exception as e:
        logger.error(f"Worker 进程 {pid} 初始化失败: {e}")
        raise


@worker_process_shutdown.connect
def shutdown_worker_process(**kwargs):
    """
    Worker 进程关闭钩子
    
    在 Worker 进程关闭时清理资源
    """
    pid = os.getpid()
    logger.info(f"关闭 Worker 进程 {pid}")
    
    # 注意：这是同步上下文，不能使用 await
    # 引擎会在进程结束时自动清理