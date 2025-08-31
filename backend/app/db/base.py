from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.db.base_class import Base

# Import all models here for Alembic
from app.models.user import User
from app.models.password_reset import PasswordReset
from app.models.task_execution import TaskExecution
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


# Re-export Base and all models for Alembic
__all__ = [
    "Base", 
    "User", 
    "PasswordReset",
    "TaskExecution",
    "TaskConfig"
]

