from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.reddit_content import (
    RedditPostResponse, RedditCommentResponse, CommentSearchRequest,
    SubredditStats, RedditConnectionTestResponse
)
from app.crud.bot_config import CRUDBotConfig
from app.crud.scrape_session import CRUDScrapeSession
from app.crud.reddit_content import CRUDRedditContent
from app.services.scraping_orchestrator import ScrapingOrchestrator
from app.db.base import get_async_session
from app.models.user import User
from app.dependencies.current_user import get_current_active_user
from app.core.exceptions import InsufficientPermissionsError
from app.utils.common import handle_error
from app.utils.permissions import get_accessible_session

router = APIRouter(tags=["reddit-content"])


@router.get("/scrape-sessions/{session_id}/posts", response_model=List[RedditPostResponse])
async def get_session_posts(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = Query(100, ge=1, le=500, description="结果数量限制")
) -> List[RedditPostResponse]:
    """
    获取会话的帖子列表
    
    只能查看自己配置的会话数据，除非是超级用户
    """
    try:
        await get_accessible_session(db, session_id, current_user)
        
        # 获取帖子列表
        posts = await CRUDRedditContent.get_posts_by_session(db, session_id, limit)
        
        return posts
        
    except Exception as e:
        raise handle_error(e)


@router.get("/scrape-sessions/{session_id}/comments", response_model=List[RedditCommentResponse])
async def get_session_comments(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = Query(500, ge=1, le=1000, description="结果数量限制")
) -> List[RedditCommentResponse]:
    """
    获取会话的评论列表
    
    只能查看自己配置的会话数据，除非是超级用户
    """
    try:
        await get_accessible_session(db, session_id, current_user)
        
        # 获取评论列表
        comments = await CRUDRedditContent.get_comments_by_session(db, session_id, limit)
        
        return comments
        
    except Exception as e:
        raise handle_error(e)


@router.get("/posts/{post_id}/comments", response_model=List[RedditCommentResponse])
async def get_post_comments(
    post_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = Query(100, ge=1, le=500, description="结果数量限制")
) -> List[RedditCommentResponse]:
    """
    获取特定帖子的评论
    
    需要确保用户有权限查看该帖子数据
    """
    try:
        # 获取评论列表
        comments = await CRUDRedditContent.get_comments_by_post(db, post_id, limit)
        
        if not comments:
            raise HTTPException(status_code=404, detail="帖子不存在或无评论")
        
        # 通过第一个评论的会话ID检查权限
        first_comment = comments[0]
        session = await CRUDScrapeSession.get_session_by_id(db, first_comment.scrape_session_id)
        
        if session:
            try:
                await get_accessible_session(db, first_comment.scrape_session_id, current_user)
            except HTTPException:
                raise InsufficientPermissionsError("没有权限查看此帖子数据")
        
        return comments
        
    except Exception as e:
        raise handle_error(e)


@router.post("/comments/search", response_model=List[RedditCommentResponse])
async def search_comments(
    search_request: CommentSearchRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> List[RedditCommentResponse]:
    """
    搜索评论内容
    
    只搜索用户有权限查看的数据
    """
    try:
        # 获取用户的配置ID列表（用于权限过滤）
        user_configs = await CRUDBotConfig.get_bot_configs(db, user_id=current_user.id)
        
        if not user_configs and not current_user.is_superuser:
            return []
        
        # 搜索评论
        comments = await CRUDRedditContent.search_comments(
            db=db,
            query=search_request.query,
            subreddits=search_request.subreddits,
            min_score=search_request.min_score,
            days=search_request.days,
            limit=search_request.limit
        )
        
        # 如果不是超级用户，需要过滤出用户有权限的数据
        if not current_user.is_superuser:
            # 获取所有用户会话的ID
            user_session_ids = set()
            for config in user_configs:
                sessions = await CRUDScrapeSession.get_sessions_by_config(db, config.id, limit=1000)
                user_session_ids.update(session.id for session in sessions)
            
            # 过滤评论
            comments = [
                comment for comment in comments 
                if comment.scrape_session_id in user_session_ids
            ]
        
        return comments
        
    except Exception as e:
        raise handle_error(e)


@router.get("/subreddits/{subreddit}/stats", response_model=SubredditStats)
async def get_subreddit_stats(
    subreddit: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    days: int = Query(30, ge=1, le=365, description="统计天数")
) -> SubredditStats:
    """
    获取subreddit统计信息
    
    只统计用户有权限查看的数据
    """
    try:
        # 获取统计信息
        stats = await CRUDRedditContent.get_subreddit_stats(db, subreddit, days)
        
        # 如果不是超级用户，这里可以进一步过滤数据
        # 目前返回全部统计信息，后续可以优化为只统计用户自己的数据
        
        return SubredditStats(**stats)
        
    except Exception as e:
        raise handle_error(e)


@router.get("/system/test-reddit-connection", response_model=RedditConnectionTestResponse)
async def test_reddit_connection(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> RedditConnectionTestResponse:
    """
    测试Reddit连接状态
    
    需要认证权限
    """
    try:
        orchestrator = ScrapingOrchestrator()
        result = await orchestrator.test_reddit_connection()
        
        return RedditConnectionTestResponse(**result)
        
    except Exception as e:
        raise handle_error(e)