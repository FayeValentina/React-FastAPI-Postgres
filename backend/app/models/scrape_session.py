from datetime import datetime
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from sqlalchemy import String, DateTime, func, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base_class import Base

if TYPE_CHECKING:
    from .bot_config import BotConfig
    from .reddit_content import RedditPost, RedditComment


class ScrapeSession(Base):
    __tablename__ = "scrape_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bot_config_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("bot_configs.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    # 会话信息
    session_type: Mapped[str] = mapped_column(String(20), default='manual')  # manual, scheduled, auto
    status: Mapped[str] = mapped_column(String(20), default='pending')  # pending, running, completed, failed, cancelled
    
    # 执行时间
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    
    # 结果统计
    total_posts_found: Mapped[int] = mapped_column(Integer, default=0)
    total_comments_found: Mapped[int] = mapped_column(Integer, default=0)
    quality_comments_count: Mapped[int] = mapped_column(Integer, default=0)
    published_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    
    # 配置快照（记录执行时的配置）
    config_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关联关系
    bot_config: Mapped["BotConfig"] = relationship("BotConfig", back_populates="scrape_sessions")
    reddit_posts: Mapped[List["RedditPost"]] = relationship(
        "RedditPost", back_populates="scrape_session", cascade="all, delete-orphan"
    )
    reddit_comments: Mapped[List["RedditComment"]] = relationship(
        "RedditComment", back_populates="scrape_session", cascade="all, delete-orphan"
    )