from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class ScrapeSessionBase(BaseModel):
    session_type: str = Field("manual", description="会话类型")
    status: str = Field("pending", description="会话状态")


class ScrapeSessionCreate(ScrapeSessionBase):
    bot_config_id: int = Field(..., description="Bot配置ID")


class ScrapeSessionResponse(ScrapeSessionBase):
    id: int
    bot_config_id: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    total_posts_found: int = 0
    total_comments_found: int = 0
    quality_comments_count: int = 0
    published_count: int = 0
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    config_snapshot: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ScrapeSessionStats(BaseModel):
    period_days: int
    total_sessions: int
    successful_sessions: int
    success_rate: float
    total_posts_found: int
    total_comments_found: int
    quality_comments_found: int
    total_published: int
    avg_duration_seconds: int


class ScrapeSessionListResponse(BaseModel):
    sessions: List[ScrapeSessionResponse]
    total_count: int
    page: int
    page_size: int


class BatchScrapeRequest(BaseModel):
    config_ids: List[int] = Field(..., description="Bot配置ID列表", min_items=1)
    session_type: str = Field("manual", description="会话类型")


class BatchScrapeResult(BaseModel):
    config_id: int
    session_id: Optional[int] = None
    status: str  # 'success', 'error', 'completed', 'failed'
    message: str
    total_posts: Optional[int] = None
    total_comments: Optional[int] = None
    error: Optional[str] = None


class BatchScrapeResponse(BaseModel):
    total_configs: int
    successful_configs: int
    results: List[BatchScrapeResult]
    message: str