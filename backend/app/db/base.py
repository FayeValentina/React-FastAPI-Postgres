from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.db.base_class import Base
from app.db.engine_manager import engine_manager

# Import all models here for Alembic
from app.models.user import User
from app.models.token import RefreshToken
from app.models.password_reset import PasswordReset
from app.models.task_execution import TaskExecution
from app.models.schedule_event import ScheduleEvent
from app.models.task_config import TaskConfig

# 主应用使用的引擎（用于 Web 服务器）
engine = create_async_engine(
    settings.postgres.SQLALCHEMY_DATABASE_URL,
    echo=settings.DB_ECHO_LOG,
    future=True,
    pool_pre_ping=True,
)

# 主应用的会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Worker 进程专用的会话工厂（通过引擎管理器获取）
def get_worker_session_factory() -> async_sessionmaker:
    """获取 Worker 进程专用的会话工厂"""
    return engine_manager.get_session_factory()


# 异步依赖函数（用于 FastAPI）
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Worker 进程专用的会话获取函数
async def get_worker_session() -> AsyncGenerator[AsyncSession, None]:
    """获取 Worker 进程专用的数据库会话"""
    session_factory = get_worker_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Re-export Base and all models for Alembic
__all__ = [
    "Base", 
    "User", 
    "RefreshToken", 
    "PasswordReset",
    "TaskExecution",
    "ScheduleEvent",
    "TaskConfig",
    "get_worker_session",
    "engine_manager"
]

