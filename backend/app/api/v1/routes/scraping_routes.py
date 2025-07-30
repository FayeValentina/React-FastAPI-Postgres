from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Annotated, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.scrape_session import (
    ScrapeSessionResponse, ScrapeSessionStats, ScrapeTriggerResponse
)
from app.crud.bot_config import CRUDBotConfig
from app.crud.scrape_session import CRUDScrapeSession
from app.services.scraping_orchestrator import ScrapingOrchestrator
from app.db.base import get_async_session
from app.models.user import User
from app.api.v1.dependencies.current_user import get_current_active_user
from app.core.exceptions import InsufficientPermissionsError
from app.utils.common import handle_error

router = APIRouter(tags=["scraping"])


@router.post("/bot-configs/{config_id}/scrape", response_model=ScrapeTriggerResponse)
async def trigger_scraping(
    config_id: int,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> ScrapeTriggerResponse:
    """
    手动触发Bot配置的爬取会话
    
    只能触发自己的配置，除非是超级用户
    """
    try:
        # 检查配置是否存在和权限
        bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)
        
        if not bot_config:
            raise HTTPException(status_code=404, detail="Bot配置不存在")
        
        # 权限检查
        if bot_config.user_id != current_user.id and not current_user.is_superuser:
            raise InsufficientPermissionsError("没有权限操作此配置")
        
        if not bot_config.is_active:
            raise HTTPException(status_code=400, detail="Bot配置未激活")
        
        # 检查是否有正在运行的会话
        running_sessions = await CRUDScrapeSession.get_sessions_by_config(
            db, config_id, status='running'
        )
        
        if running_sessions:
            raise HTTPException(
                status_code=409, 
                detail="该配置已有正在运行的爬取会话"
            )
        
        # 先创建初始会话记录（包含config_snapshot）
        # 获取bot配置来创建config_snapshot
        config_snapshot = {
            'target_subreddits': bot_config.target_subreddits,
            'posts_per_subreddit': bot_config.posts_per_subreddit,
            'comments_per_post': bot_config.comments_per_post,
            'sort_method': bot_config.sort_method,
            'time_filter': bot_config.time_filter,
            'enable_ai_filter': bot_config.enable_ai_filter,
            'ai_confidence_threshold': float(bot_config.ai_confidence_threshold),
            'min_comment_length': bot_config.min_comment_length,
            'max_comment_length': bot_config.max_comment_length
        }
        
        session = await CRUDScrapeSession.create_scrape_session(
            db, config_id, 'manual', config_snapshot
        )
        
        # 创建爬取编排器并在后台执行
        orchestrator = ScrapingOrchestrator()
        
        # 在后台任务中执行爬取
        async def execute_scraping_task():
            try:
                # 直接使用数据库会话创建器，而不是依赖注入的生成器
                from app.db.base import AsyncSessionLocal
                async with AsyncSessionLocal() as session_db:
                    try:
                        result = await orchestrator.execute_scraping_session_with_existing(
                            session_db, session.id
                        )
                        await session_db.commit()
                        return result
                    except Exception as e:
                        await session_db.rollback()
                        raise e
            except Exception as e:
                # 记录错误但不影响响应
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"后台爬取任务失败: {e}")
        
        background_tasks.add_task(execute_scraping_task)
        
        return ScrapeTriggerResponse(
            session_id=session.id,
            status="initiated",
            message="爬取任务已启动，正在后台执行"
        )
        
    except Exception as e:
        raise handle_error(e)


@router.get("/scrape-sessions", response_model=List[ScrapeSessionResponse])
async def get_scrape_sessions(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    status: str = None,
    limit: int = 50
) -> List[ScrapeSessionResponse]:
    """
    获取当前用户的爬取会话列表
    
    - status: 可选，按状态过滤
    - limit: 结果数量限制
    """
    try:
        # 获取用户的所有bot配置
        user_configs = await CRUDBotConfig.get_user_bot_configs(db, current_user.id)
        
        if not user_configs:
            return []
        
        # 获取所有配置的会话
        all_sessions = []
        for config in user_configs:
            sessions = await CRUDScrapeSession.get_sessions_by_config(
                db, config.id, limit=limit, status=status
            )
            all_sessions.extend(sessions)
        
        # 按创建时间降序排序
        all_sessions.sort(key=lambda x: x.created_at, reverse=True)
        
        return all_sessions[:limit]
        
    except Exception as e:
        raise handle_error(e)


@router.get("/scrape-sessions/{session_id}", response_model=ScrapeSessionResponse)
async def get_scrape_session(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> ScrapeSessionResponse:
    """
    获取特定会话详情
    
    只能查看自己配置的会话，除非是超级用户
    """
    try:
        session = await CRUDScrapeSession.get_session_by_id(db, session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="爬取会话不存在")
        
        # 获取关联的bot配置检查权限
        bot_config = await CRUDBotConfig.get_bot_config_by_id(db, session.bot_config_id)
        
        if not bot_config:
            raise HTTPException(status_code=404, detail="关联的Bot配置不存在")
        
        # 权限检查
        if bot_config.user_id != current_user.id and not current_user.is_superuser:
            raise InsufficientPermissionsError("没有权限查看此会话")
        
        return session
        
    except Exception as e:
        raise handle_error(e)



@router.get("/scrape-sessions/stats", response_model=ScrapeSessionStats)
async def get_session_stats(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    days: int = 7
) -> ScrapeSessionStats:
    """
    获取爬取会话统计信息
    
    - days: 统计最近N天的数据
    """
    try:
        # 这里需要扩展CRUD方法来支持按用户过滤的统计
        # 暂时返回全局统计（后续可以优化为用户特定统计）
        stats = await CRUDScrapeSession.get_recent_sessions_stats(db, days)
        
        return ScrapeSessionStats(**stats)
        
    except Exception as e:
        raise handle_error(e)


@router.get("/scrape-sessions/running", response_model=List[ScrapeSessionResponse])
async def get_running_sessions(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> List[ScrapeSessionResponse]:
    """
    获取正在运行的会话
    
    只显示当前用户的会话，除非是超级用户
    """
    try:
        running_sessions = await CRUDScrapeSession.get_running_sessions(db)
        
        # 如果不是超级用户，只返回自己的会话
        if not current_user.is_superuser:
            # 获取用户的配置ID列表
            user_configs = await CRUDBotConfig.get_user_bot_configs(db, current_user.id)
            user_config_ids = {config.id for config in user_configs}
            
            # 过滤出属于当前用户的会话
            running_sessions = [
                session for session in running_sessions 
                if session.bot_config_id in user_config_ids
            ]
        
        return running_sessions
        
    except Exception as e:
        raise handle_error(e)