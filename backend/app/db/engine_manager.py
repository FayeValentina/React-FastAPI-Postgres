"""
数据库引擎管理器 - 为每个 Worker 进程提供独立的数据库引擎
"""
import os
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


class EngineManager:
    """
    数据库引擎管理器
    
    为每个 Worker 进程维护独立的数据库引擎实例，
    避免跨进程共享连接导致的事件循环冲突
    """
    
    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
        self._process_id: Optional[int] = None
    
    def _create_engine(self) -> AsyncEngine:
        """创建新的数据库引擎"""
        engine = create_async_engine(
            settings.postgres.SQLALCHEMY_DATABASE_URL,
            echo=settings.DB_ECHO_LOG,
            future=True,
            pool_pre_ping=True,
            # Worker 进程专用的连接池配置
            pool_size=5,  # 减小连接池大小
            max_overflow=10,
            pool_recycle=3600,  # 1小时回收连接
            pool_timeout=30,
        )
        logger.info(f"为进程 {os.getpid()} 创建了新的数据库引擎")
        return engine
    
    def get_engine(self) -> AsyncEngine:
        """
        获取当前进程的数据库引擎
        
        如果检测到进程变化（fork后），会创建新的引擎
        """
        current_pid = os.getpid()
        
        # 检查是否需要创建新引擎
        if self._engine is None or self._process_id != current_pid:
            # 如果旧引擎存在，先关闭它
            if self._engine is not None:
                logger.warning(f"检测到进程变化 {self._process_id} -> {current_pid}，重新创建引擎")
                # 注意：这里不能使用 await，因为可能在同步上下文中
                # 旧引擎会被垃圾回收器清理
            
            # 创建新引擎
            self._engine = self._create_engine()
            self._process_id = current_pid
            
            # 创建新的会话工厂
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        
        return self._engine
    
    def get_session_factory(self) -> async_sessionmaker:
        """获取当前进程的会话工厂"""
        # 确保引擎已创建
        self.get_engine()
        return self._session_factory
    
    async def close(self):
        """关闭当前进程的数据库引擎"""
        if self._engine is not None:
            await self._engine.dispose()
            logger.info(f"进程 {os.getpid()} 的数据库引擎已关闭")
            self._engine = None
            self._session_factory = None


# 全局引擎管理器实例
engine_manager = EngineManager()