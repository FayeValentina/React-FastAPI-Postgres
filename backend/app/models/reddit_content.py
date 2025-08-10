from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, func, Integer, Text, Boolean, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class RedditPost(Base):
    __tablename__ = "reddit_posts"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # Reddit的帖子ID
    
    # 帖子基本信息
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(100))
    subreddit: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subreddit_subscribers: Mapped[Optional[int]] = mapped_column(Integer)
    
    # 内容
    content: Mapped[Optional[str]] = mapped_column(Text)  # 自发帖的文本内容
    url: Mapped[Optional[str]] = mapped_column(Text)
    domain: Mapped[Optional[str]] = mapped_column(String(200))
    
    # 统计数据
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    upvote_ratio: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    num_comments: Mapped[int] = mapped_column(Integer, default=0)
    
    # 分类和标签
    flair_text: Mapped[Optional[str]] = mapped_column(String(200))
    is_self: Mapped[bool] = mapped_column(Boolean, default=False)
    is_nsfw: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spoiler: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # 时间信息
    reddit_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关联关系
    comments: Mapped[List["RedditComment"]] = relationship(
        "RedditComment", back_populates="post", cascade="all, delete-orphan"
    )


class RedditComment(Base):
    __tablename__ = "reddit_comments"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # Reddit的评论ID
    post_id: Mapped[str] = mapped_column(
        String(50), 
        ForeignKey("reddit_posts.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    # 评论基本信息
    author: Mapped[Optional[str]] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    subreddit: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    # 评论层级
    parent_id: Mapped[Optional[str]] = mapped_column(String(50))  # 父评论ID
    depth: Mapped[int] = mapped_column(Integer, default=0)
    is_submitter: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否是原帖作者的评论
    
    # 统计数据
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    controversiality: Mapped[int] = mapped_column(Integer, default=0)
    
    # 时间信息
    reddit_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 关联关系
    post: Mapped["RedditPost"] = relationship("RedditPost", back_populates="comments")