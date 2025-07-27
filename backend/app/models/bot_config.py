from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, func, Boolean, Integer, Text, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User
    from .scrape_session import ScrapeSession


class BotConfig(Base):
    __tablename__ = "bot_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # 爬取配置
    target_subreddits: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)
    posts_per_subreddit: Mapped[int] = mapped_column(Integer, default=50)
    comments_per_post: Mapped[int] = mapped_column(Integer, default=20)
    sort_method: Mapped[str] = mapped_column(String(20), default='hot')
    time_filter: Mapped[str] = mapped_column(String(20), default='day')
    
    # AI评估配置
    enable_ai_filter: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_confidence_threshold: Mapped[float] = mapped_column(Numeric(3, 2), default=0.8)
    min_comment_length: Mapped[int] = mapped_column(Integer, default=10)
    max_comment_length: Mapped[int] = mapped_column(Integer, default=280)
    
    # 自动化配置
    auto_publish_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    publish_interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    max_daily_posts: Mapped[int] = mapped_column(Integer, default=5)
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=func.now(),
        server_onupdate=func.now()
    )

    # 关联关系
    user: Mapped["User"] = relationship("User", back_populates="bot_configs")
    scrape_sessions: Mapped[List["ScrapeSession"]] = relationship(
        "ScrapeSession", back_populates="bot_config", cascade="all, delete-orphan"
    )