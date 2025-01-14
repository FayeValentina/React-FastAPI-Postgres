from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_async_session

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        yield session 