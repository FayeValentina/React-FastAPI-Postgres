from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.bot_config import (
    BotConfigCreate, BotConfigUpdate, BotConfigResponse, BotConfigToggleResponse
)
from app.crud.bot_config import CRUDBotConfig
from app.db.base import get_async_session
from app.models.user import User
from app.api.v1.dependencies.current_user import get_current_active_user
from app.core.exceptions import UserNotFoundError, InsufficientPermissionsError
from app.utils.common import handle_error

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
    获取当前用户的Bot配置列表
    
    - is_active: 可选，过滤激活状态
    """
    try:
        # 普通用户只能查看自己的配置，超级用户可以查看所有配置
        if current_user.is_superuser:
            # 对于超级用户，可以扩展为获取所有用户的配置
            # 这里暂时还是返回当前用户的配置，可以后续扩展
            configs = await CRUDBotConfig.get_user_bot_configs(
                db, current_user.id, is_active
            )
        else:
            configs = await CRUDBotConfig.get_user_bot_configs(
                db, current_user.id, is_active
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
        bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)
        
        if not bot_config:
            raise HTTPException(status_code=404, detail="Bot配置不存在")
        
        # 权限检查：只能查看自己的配置或超级用户可以查看所有配置
        if bot_config.user_id != current_user.id and not current_user.is_superuser:
            raise InsufficientPermissionsError("没有权限查看此配置")
            
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
        # 先获取配置检查权限
        bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)
        
        if not bot_config:
            raise HTTPException(status_code=404, detail="Bot配置不存在")
        
        # 权限检查
        if bot_config.user_id != current_user.id and not current_user.is_superuser:
            raise InsufficientPermissionsError("没有权限修改此配置")
        
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
        # 先获取配置检查权限
        bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)
        
        if not bot_config:
            raise HTTPException(status_code=404, detail="Bot配置不存在")
        
        # 权限检查
        if bot_config.user_id != current_user.id and not current_user.is_superuser:
            raise InsufficientPermissionsError("没有权限删除此配置")
        
        success = await CRUDBotConfig.delete_bot_config(db, config_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="删除失败")
    except Exception as e:
        raise handle_error(e)


@router.post("/{config_id}/toggle", response_model=BotConfigToggleResponse)
async def toggle_bot_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> BotConfigToggleResponse:
    """
    启用/禁用Bot配置
    
    只能切换自己的配置，除非是超级用户
    """
    try:
        # 先获取配置检查权限
        bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)
        
        if not bot_config:
            raise HTTPException(status_code=404, detail="Bot配置不存在")
        
        # 权限检查
        if bot_config.user_id != current_user.id and not current_user.is_superuser:
            raise InsufficientPermissionsError("没有权限修改此配置")
        
        updated_config = await CRUDBotConfig.toggle_bot_config_status(db, config_id)
        
        if not updated_config:
            raise HTTPException(status_code=404, detail="切换状态失败")
        
        status_text = "启用" if updated_config.is_active else "禁用"
        
        return BotConfigToggleResponse(
            id=updated_config.id,
            is_active=updated_config.is_active,
            message=f"Bot配置已{status_text}"
        )
    except Exception as e:
        raise handle_error(e)