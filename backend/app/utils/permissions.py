from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.bot_config import BotConfig
from app.crud.bot_config import CRUDBotConfig
from app.core.exceptions import InsufficientPermissionsError


async def check_bot_config_permission(
    db: AsyncSession, 
    config_id: int, 
    user: User
) -> BotConfig:
    """检查用户对Bot配置的权限，返回配置对象
    
    Args:
        db: 数据库会话
        config_id: Bot配置ID
        user: 当前用户
        
    Returns:
        BotConfig: 验证通过的配置对象
        
    Raises:
        HTTPException: 配置不存在时抛出404
        InsufficientPermissionsError: 无权限时抛出403
    """
    bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)
    
    if not bot_config:
        raise HTTPException(status_code=404, detail="Bot配置不存在")
    
    # 超级用户可以访问所有配置，普通用户只能访问自己的配置
    if bot_config.user_id != user.id and not user.is_superuser:
        raise InsufficientPermissionsError("没有权限操作此配置")
    
    return bot_config


async def check_session_permission(
    db: AsyncSession,
    session_id: int,
    user: User
) -> bool:
    """检查用户对爬取会话的权限
    
    Args:
        db: 数据库会话
        session_id: 会话ID
        user: 当前用户
        
    Returns:
        bool: 是否有权限
    """
    from app.crud.scrape_session import CRUDScrapeSession
    
    session = await CRUDScrapeSession.get_session_by_id(db, session_id)
    if not session:
        return False
    
    # 通过关联的bot配置检查权限
    bot_config = await CRUDBotConfig.get_bot_config_by_id(db, session.bot_config_id)
    if not bot_config:
        return False
    
    return bot_config.user_id == user.id or user.is_superuser