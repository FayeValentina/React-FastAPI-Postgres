from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.infrastructure.cache.cache_serializer import register_pydantic_model


class RedditPostBase(BaseModel):
    title: str
    author: Optional[str] = None
    subreddit: str
    subreddit_subscribers: Optional[int] = None
    content: Optional[str] = None
    url: Optional[str] = None
    domain: Optional[str] = None
    score: int = 0
    upvote_ratio: Optional[float] = None
    num_comments: int = 0
    flair_text: Optional[str] = None
    is_self: bool = False
    is_nsfw: bool = False
    is_spoiler: bool = False
    reddit_created_at: datetime


@register_pydantic_model
class RedditPostResponse(RedditPostBase):
    id: str
    scraped_at: datetime
    model_config = ConfigDict(from_attributes=True)

class RedditCommentBase(BaseModel):
    author: Optional[str] = None
    body: str
    subreddit: str
    parent_id: Optional[str] = None
    depth: int = 0
    is_submitter: bool = False
    score: int = 0
    controversiality: int = 0
    reddit_created_at: datetime


@register_pydantic_model
class RedditCommentResponse(RedditCommentBase):
    id: str
    post_id: str
    scraped_at: datetime
    model_config = ConfigDict(from_attributes=True)

class RedditContentListResponse(BaseModel):
    posts: Optional[List[RedditPostResponse]] = None
    comments: Optional[List[RedditCommentResponse]] = None
    total_count: int
    page: int
    page_size: int


class CommentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="搜索关键词")
    subreddits: Optional[List[str]] = Field(None, description="限制搜索的subreddit")
    min_score: int = Field(0, description="最小分数")
    days: Optional[int] = Field(None, ge=1, description="限制天数")
    limit: int = Field(100, ge=1, le=500, description="结果数量限制")


class SubredditStats(BaseModel):
    subreddit: str
    period_days: int
    posts: Dict[str, Any]
    comments: Dict[str, Any]
    top_authors: List[Dict[str, Any]]


class RedditConnectionTestResponse(BaseModel):
    status: str
    message: str
    test_subreddit: Optional[str] = None