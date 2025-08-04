from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.scrape_session import (
    ScrapeSessionResponse, ScrapeSessionStats,
    BatchScrapeRequest, BatchScrapeResponse, BatchScrapeResult
)
from app.crud.scrape_session import CRUDScrapeSession
from app.services.scraping_orchestrator import ScrapingOrchestrator
from app.services.schedule_manager import ScheduleManager
from app.db.base import get_async_session
from app.models.user import User
from app.dependencies.current_user import get_current_active_user
from app.utils.common import handle_error
from app.utils.permissions import get_accessible_bot_config, get_accessible_session
from app.models.scrape_session import SessionStatus, SessionType

router = APIRouter(prefix="/scraping", tags=["scraping"])


@router.post("/start/{config_id}")
async def start_scraping(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    手动触发单个Bot配置的爬取任务
    """
    try:
        # 验证权限
        bot_config = await get_accessible_bot_config(db, config_id, current_user)
        
        if not bot_config.is_active:
            raise HTTPException(status_code=400, detail="Bot配置未激活")
        
        # 发送手动爬取任务到队列
        task_id = ScheduleManager.trigger_manual_scraping(config_id, "manual")
        
        return {
            "message": "爬取任务已启动",
            "config_id": config_id,
            "task_id": task_id,
            "status": "queued"
        }
        
    except Exception as e:
        raise handle_error(e)


@router.get("/task-status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    获取Celery任务状态
    """
    try:
        status = ScheduleManager.get_task_status(task_id)
        return status
    except Exception as e:
        raise handle_error(e)


@router.post("/cancel-task/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    terminate: bool = False
):
    """
    取消Celery任务
    """
    try:
        result = ScheduleManager.cancel_task(task_id, terminate)
        return result
    except Exception as e:
        raise handle_error(e)


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
                bot_config = await get_accessible_bot_config(db, config_id, current_user)
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
        
        # 批量执行有效的配置 - 使用Celery队列
        if valid_config_ids:
            # 发送批量爬取任务到队列
            task_id = ScheduleManager.trigger_batch_scraping(
                valid_config_ids, session_type
            )
            
            # 返回任务ID，前端可以通过任务状态API查询进度
            for config_id in valid_config_ids:
                results.append(BatchScrapeResult(
                    config_id=config_id,
                    status="queued",
                    message=f"任务已加入队列，任务ID: {task_id}",
                    task_id=task_id
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
    status: SessionStatus = None,
    session_type: SessionType = None,
    limit: int = 50
) -> List[ScrapeSessionResponse]:
    """
    获取爬取会话列表
    
    - 超级用户: 返回所有用户的爬取会话
    - 普通用户: 返回当前用户配置关联的爬取会话
    - status: 可选，按状态过滤
    - session_type: 可选，按会话类型过滤
    - limit: 结果数量限制
    """
    try:
        # 超级用户可以查看所有会话，普通用户只能查看自己配置的会话
        user_id = None if current_user.is_superuser else current_user.id
        sessions = await CRUDScrapeSession.get_sessions(
            db, user_id=user_id, limit=limit, status=status, session_type=session_type
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
        session = await get_accessible_session(db, session_id, current_user)
        
        return session
        
    except Exception as e:
        raise handle_error(e)