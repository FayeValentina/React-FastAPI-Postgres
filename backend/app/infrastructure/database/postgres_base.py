from typing import AsyncGenerator, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import event

from app.core.config import settings
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.declarative import declared_attr


class Base(DeclarativeBase):
    """SQLAlchemy 声明性基类"""
    
    @declared_attr
    def __tablename__(cls) -> str:
        """自动生成表名"""
        return cls.__name__.lower()
    
    # 通用的列可以在这里定义
    id: Any
    __name__: str 
    
# 主应用使用的引擎（用于 Web 服务器）
engine = create_async_engine(
    settings.postgres.SQLALCHEMY_DATABASE_URL,
    echo=settings.DB_ECHO_LOG,
    future=True,
    pool_pre_ping=True,
)

# Ensure pgvector uses ivfflat index probes tuned from settings for every connection
@event.listens_for(engine.sync_engine, "connect", once=False)
def _configure_pgvector(connection, _):
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SET ivfflat.probes = {settings.RAG_IVFFLAT_PROBES}")
    except Exception:
        # Intentionally swallow to avoid breaking app startup if the command fails
        return

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
__all__ = ["Base"]

