from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.reddit_content import (
    RedditPostResponse, RedditCommentResponse, CommentSearchRequest,
    SubredditStats, RedditConnectionTestResponse
)
from app.crud.reddit_content import CRUDRedditContent
from app.db.base import get_async_session
from app.models.user import User
from app.dependencies.current_user import get_current_active_user
from app.core.exceptions import InsufficientPermissionsError
from app.utils.common import handle_error
from app.utils.cache_decorators import cache_list_data, cache_stats_data

router = APIRouter(tags=["reddit-content"])


@router.get("/posts", response_model=List[RedditPostResponse])
@cache_list_data("reddit_posts")
async def get_posts(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = Query(100, ge=1, le=500, description="结果数量限制")
) -> List[RedditPostResponse]:
    """
    获取Reddit帖子列表
    
    普通用户只能查看自己的数据，超级用户可以查看所有数据
    """
    try:
        # 获取帖子列表
        posts = await CRUDRedditContent.get_posts(db, limit=limit, user_id=None if current_user.is_superuser else current_user.id)
        
        return posts
        
    except Exception as e:
        raise handle_error(e)


@router.get("/comments", response_model=List[RedditCommentResponse])
@cache_list_data("reddit_comments")
async def get_comments(
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = Query(500, ge=1, le=1000, description="结果数量限制")
) -> List[RedditCommentResponse]:
    """
    获取Reddit评论列表
    
    普通用户只能查看自己的数据，超级用户可以查看所有数据
    """
    try:
        # 获取评论列表
        comments = await CRUDRedditContent.get_comments(db, limit=limit, user_id=None if current_user.is_superuser else current_user.id)
        
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
    """
    try:
        # 获取评论列表
        comments = await CRUDRedditContent.get_comments_by_post(db, post_id, limit)
        
        if not comments:
            raise HTTPException(status_code=404, detail="帖子不存在或无评论")
        
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
    """
    try:
        # 搜索评论
        comments = await CRUDRedditContent.search_comments(
            db=db,
            query=search_request.query,
            subreddits=search_request.subreddits,
            min_score=search_request.min_score,
            days=search_request.days,
            limit=search_request.limit
        )
        
        return comments
        
    except Exception as e:
        raise handle_error(e)


@router.get("/subreddits/{subreddit}/stats", response_model=SubredditStats)
@cache_stats_data("subreddit_stats")
async def get_subreddit_stats(
    subreddit: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    days: int = Query(30, ge=1, le=365, description="统计天数")
) -> SubredditStats:
    """
    获取subreddit统计信息
    """
    try:
        # 获取统计信息
        stats = await CRUDRedditContent.get_subreddit_stats(db, subreddit, days)
        
        return SubredditStats(**stats)
        
    except Exception as e:
        raise handle_error(e)