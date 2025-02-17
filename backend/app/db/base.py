from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker # type: ignore

from app.core.config import settings
from app.db.base_class import Base
# Import all models here for Alembic
from app.models.user import User
from app.models.post import Post

# 创建异步数据库引擎
engine = create_async_engine(
    settings.postgres.SQLALCHEMY_DATABASE_URL,
    echo=settings.DB_ECHO_LOG,
    future=True,
    pool_pre_ping=True,
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 异步依赖函数
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
__all__ = ["Base", "User", "Post"]
