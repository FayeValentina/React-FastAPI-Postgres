from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.bot_config import BotConfig
from app.models.scrape_session import ScrapeSession
from app.crud.bot_config import CRUDBotConfig
from app.crud.scrape_session import CRUDScrapeSession


def _check_resource_ownership(owner_user_id: int, current_user: User) -> None:
    """内部方法：检查用户是否拥有资源的访问权限"""
    if owner_user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")


async def get_accessible_bot_config(
    db: AsyncSession,
    config_id: int,
    user: User
) -> BotConfig:
    """获取用户可访问的Bot配置
    
    - 超级用户可以访问所有配置
    - 普通用户只能访问自己的配置
    """
    bot_config = await CRUDBotConfig.get_bot_configs(db, config_id=config_id)
    if not bot_config:
        raise HTTPException(status_code=404, detail="Bot配置不存在")
    
    _check_resource_ownership(bot_config.user_id, user)
    return bot_config


async def get_accessible_session(
    db: AsyncSession,
    session_id: int,
    user: User
) -> ScrapeSession:
    """获取用户可访问的爬取会话
    
    - 超级用户可以访问所有会话
    - 普通用户只能访问自己Bot配置关联的会话
    """
    session = await CRUDScrapeSession.get_sessions(db, session_id=session_id)
    if not session:
        raise HTTPException(status_code=404, detail="爬取会话不存在")
    
    # 通过关联的Bot配置检查权限
    bot_config = await CRUDBotConfig.get_bot_configs(db, config_id=session.bot_config_id)
    if not bot_config:
        raise HTTPException(status_code=404, detail="关联的Bot配置不存在")
    
    _check_resource_ownership(bot_config.user_id, user)
    return session