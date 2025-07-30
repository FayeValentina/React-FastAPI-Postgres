from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.scrape_session import (
    ScrapeSessionResponse, ScrapeSessionStats,
    BatchScrapeRequest, BatchScrapeResponse, BatchScrapeResult
)
from app.crud.bot_config import CRUDBotConfig
from app.crud.scrape_session import CRUDScrapeSession
from app.services.scraping_orchestrator import ScrapingOrchestrator
from app.db.base import get_async_session
from app.models.user import User
from app.api.v1.dependencies.current_user import get_current_active_user
from app.core.exceptions import InsufficientPermissionsError
from app.utils.common import handle_error
from app.utils.permissions import check_bot_config_permission

router = APIRouter(prefix="/scraping", tags=["scraping"])


@router.post("/bot-configs/batch-scrape", response_model=BatchScrapeResponse)
async def batch_trigger_scraping(
    request_data: BatchScrapeRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> BatchScrapeResponse:
    """
    批量触发多个Bot配置的爬取会话
    
    并行执行多个配置的爬取，只能触发自己的配置，除非是超级用户
    """
    try:
        config_ids = request_data.config_ids
        session_type = request_data.session_type
        
        # 验证所有配置的权限和状态
        valid_config_ids = []
        results = []
        
        for config_id in config_ids:
            try:
                bot_config = await check_bot_config_permission(db, config_id, current_user)
                if not bot_config.is_active:
                    results.append(BatchScrapeResult(
                        config_id=config_id,
                        status="error",
                        message="Bot配置未激活"
                    ))
                else:
                    valid_config_ids.append(config_id)
            except Exception as e:
                results.append(BatchScrapeResult(
                    config_id=config_id,
                    status="error",
                    message=f"权限验证失败: {str(e)}"
                ))
        
        # 批量执行有效的配置
        if valid_config_ids:
            orchestrator = ScrapingOrchestrator()
            batch_results = await orchestrator.execute_multiple_configs(
                db, valid_config_ids, session_type
            )
            
            # 转换结果格式
            for result in batch_results:
                if result.get('status') == 'completed':
                    results.append(BatchScrapeResult(
                        config_id=result.get('config_id'),
                        session_id=result.get('session_id'),
                        status="completed",
                        message="爬取完成",
                        total_posts=result.get('total_posts'),
                        total_comments=result.get('total_comments')
                    ))
                else:
                    results.append(BatchScrapeResult(
                        config_id=result.get('config_id'),
                        session_id=result.get('session_id'),
                        status="failed",
                        message="爬取失败",
                        error=result.get('error')
                    ))
        
        successful_count = len([r for r in results if r.status == "completed"])
        
        return BatchScrapeResponse(
            total_configs=len(config_ids),
            successful_configs=successful_count,
            results=results,
            message=f"批量爬取完成: {successful_count}/{len(config_ids)} 个配置成功执行"
        )
        
    except Exception as e:
        raise handle_error(e)


@router.get("/scrape-sessions", response_model=List[ScrapeSessionResponse])
async def get_scrape_sessions(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    status: str = None,
    session_type: str = None,
    limit: int = 50
) -> List[ScrapeSessionResponse]:
    """
    获取当前用户的爬取会话列表
    
    - status: 可选，按状态过滤
    - session_type: 可选，按会话类型过滤
    - limit: 结果数量限制
    """
    try:
        # 直接获取用户的所有会话
        sessions = await CRUDScrapeSession.get_sessions(
            db, user_id=current_user.id, limit=limit, status=status, session_type=session_type
        )
        
        return sessions
        
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
        
        # 通过关联的bot配置检查权限
        await check_bot_config_permission(db, session.bot_config_id, current_user)
        
        return session
        
    except Exception as e:
        raise handle_error(e)