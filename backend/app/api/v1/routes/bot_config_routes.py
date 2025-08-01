from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.bot_config import (
    BotConfigCreate, BotConfigUpdate, BotConfigResponse
)
from app.crud.bot_config import CRUDBotConfig
from app.db.base import get_async_session
from app.models.user import User
from app.dependencies.current_user import get_current_active_user
from app.utils.common import handle_error
from app.utils.permissions import get_accessible_bot_config

router = APIRouter(prefix="/bot-configs", tags=["bot-configs"])


@router.post("", response_model=BotConfigResponse, status_code=201)
async def create_bot_config(
    config_data: BotConfigCreate,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> BotConfigResponse:
    """
    创建Bot配置
    
    只能为当前用户创建配置
    """
    try:
        bot_config = await CRUDBotConfig.create_bot_config(
            db=db,
            user_id=current_user.id,
            name=config_data.name,
            description=config_data.description,
            target_subreddits=config_data.target_subreddits,
            posts_per_subreddit=config_data.posts_per_subreddit,
            comments_per_post=config_data.comments_per_post,
            sort_method=config_data.sort_method,
            time_filter=config_data.time_filter,
            enable_ai_filter=config_data.enable_ai_filter,
            ai_confidence_threshold=config_data.ai_confidence_threshold,
            min_comment_length=config_data.min_comment_length,
            max_comment_length=config_data.max_comment_length,
            auto_scrape_enabled=config_data.auto_scrape_enabled,
            scrape_interval_hours=config_data.scrape_interval_hours,
            max_daily_posts=config_data.max_daily_posts
        )
        return bot_config
    except Exception as e:
        raise handle_error(e)


@router.get("", response_model=List[BotConfigResponse])
async def get_bot_configs(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    is_active: bool = None
) -> List[BotConfigResponse]:
    """
    获取Bot配置列表
    
    - 超级用户: 返回所有用户的Bot配置
    - 普通用户: 返回当前用户的Bot配置
    - is_active: 可选，过滤激活状态
    """
    try:
        # 超级用户可以查看所有配置，普通用户只能查看自己的配置
        user_id = None if current_user.is_superuser else current_user.id
        configs = await CRUDBotConfig.get_bot_configs(
            db, user_id=user_id, is_active=is_active
        )
        return configs
    except Exception as e:
        raise handle_error(e)


@router.get("/{config_id}", response_model=BotConfigResponse)
async def get_bot_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> BotConfigResponse:
    """
    获取特定Bot配置详情
    
    只能获取自己的配置，除非是超级用户
    """
    try:
        bot_config = await get_accessible_bot_config(db, config_id, current_user)
            
        return bot_config
    except Exception as e:
        raise handle_error(e)


@router.patch("/{config_id}", response_model=BotConfigResponse)
async def update_bot_config(
    config_id: int,
    config_update: BotConfigUpdate,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> BotConfigResponse:
    """
    更新Bot配置
    
    只能更新自己的配置，除非是超级用户
    """
    try:
        await get_accessible_bot_config(db, config_id, current_user)
        
        # 只更新提供的字段
        update_data = config_update.model_dump(exclude_unset=True)
        updated_config = await CRUDBotConfig.update_bot_config(
            db, config_id, **update_data
        )
        
        if not updated_config:
            raise HTTPException(status_code=404, detail="更新失败")
            
        return updated_config
    except Exception as e:
        raise handle_error(e)


@router.delete("/{config_id}", status_code=204)
async def delete_bot_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> None:
    """
    删除Bot配置
    
    只能删除自己的配置，除非是超级用户
    """
    try:
        await get_accessible_bot_config(db, config_id, current_user)
        
        success = await CRUDBotConfig.delete_bot_config(db, config_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="删除失败")
    except Exception as e:
        raise handle_error(e)


