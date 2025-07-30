from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class BotConfigBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Bot配置名称")
    description: Optional[str] = Field(None, description="Bot配置描述")
    target_subreddits: List[str] = Field(..., description="目标subreddit列表")
    posts_per_subreddit: int = Field(50, ge=1, le=500, description="每个subreddit爬取的帖子数量")
    comments_per_post: int = Field(20, ge=1, le=100, description="每个帖子爬取的评论数量")
    sort_method: str = Field("hot", description="排序方式")
    time_filter: str = Field("day", description="时间筛选")
    enable_ai_filter: bool = Field(True, description="是否启用AI过滤")
    ai_confidence_threshold: float = Field(0.8, ge=0.0, le=1.0, description="AI置信度阈值")
    min_comment_length: int = Field(10, ge=1, description="最小评论长度")
    max_comment_length: int = Field(280, ge=1, description="最大评论长度")
    auto_scrape_enabled: bool = Field(False, description="是否启用自动发布")
    scrape_interval_hours: int = Field(24, ge=1, description="发布间隔小时数")
    max_daily_posts: int = Field(5, ge=1, description="每日最大发布数量")


class BotConfigCreate(BotConfigBase):
    pass


class BotConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    target_subreddits: Optional[List[str]] = None
    posts_per_subreddit: Optional[int] = Field(None, ge=1, le=500)
    comments_per_post: Optional[int] = Field(None, ge=1, le=100)
    sort_method: Optional[str] = None
    time_filter: Optional[str] = None
    enable_ai_filter: Optional[bool] = None
    ai_confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_comment_length: Optional[int] = Field(None, ge=1)
    max_comment_length: Optional[int] = Field(None, ge=1)
    auto_scrape_enabled: Optional[bool] = None
    scrape_interval_hours: Optional[int] = Field(None, ge=1)
    max_daily_posts: Optional[int] = Field(None, ge=1)


class BotConfigResponse(BotConfigBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BotConfigToggleResponse(BaseModel):
    id: int
    is_active: bool
    message: str