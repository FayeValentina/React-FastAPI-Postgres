from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from app.models.scrape_session import ScrapeSession
from app.models.reddit_content import RedditPost, RedditComment
from app.models.bot_config import BotConfig


class CRUDScrapeSession:
    """爬取会话服务类，用于管理爬取会话的生命周期"""
    
    @staticmethod
    async def create_scrape_session(
        db: AsyncSession,
        bot_config_id: int,
        session_type: str = 'manual',
        config_snapshot: Optional[Dict[str, Any]] = None
    ) -> ScrapeSession:
        """创建新的爬取会话"""
        session = ScrapeSession(
            bot_config_id=bot_config_id,
            session_type=session_type,
            status='pending',
            config_snapshot=config_snapshot or {}
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session
    
    @staticmethod
    async def start_session(
        db: AsyncSession,
        session_id: int
    ) -> Optional[ScrapeSession]:
        """开始爬取会话"""
        result = await db.execute(
            select(ScrapeSession).where(ScrapeSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        session.status = 'running'
        session.started_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(session)
        return session
    
    @staticmethod
    async def complete_session(
        db: AsyncSession,
        session_id: int,
        total_posts_found: int = 0,
        total_comments_found: int = 0,
        quality_comments_count: int = 0,
        published_count: int = 0,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> Optional[ScrapeSession]:
        """完成爬取会话"""
        result = await db.execute(
            select(ScrapeSession).where(ScrapeSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        current_time = datetime.utcnow()
        session.completed_at = current_time
        session.status = 'failed' if error_message else 'completed'
        session.total_posts_found = total_posts_found
        session.total_comments_found = total_comments_found
        session.quality_comments_count = quality_comments_count
        session.published_count = published_count
        session.error_message = error_message
        session.error_details = error_details
        
        if session.started_at:
            session.duration_seconds = int((current_time - session.started_at).total_seconds())
        
        await db.commit()
        await db.refresh(session)
        return session
    
    @staticmethod
    async def get_session_by_id(
        db: AsyncSession,
        session_id: int,
        include_content: bool = False
    ) -> Optional[ScrapeSession]:
        """根据ID获取爬取会话"""
        query = select(ScrapeSession).where(ScrapeSession.id == session_id)
        
        if include_content:
            query = query.options(
                selectinload(ScrapeSession.reddit_posts),
                selectinload(ScrapeSession.reddit_comments)
            )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_sessions_by_config(
        db: AsyncSession,
        bot_config_id: int,
        limit: int = 50,
        status: Optional[str] = None
    ) -> List[ScrapeSession]:
        """获取指定配置的爬取会话列表"""
        query = select(ScrapeSession).where(ScrapeSession.bot_config_id == bot_config_id)
        
        if status:
            query = query.where(ScrapeSession.status == status)
        
        query = query.order_by(ScrapeSession.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_running_sessions(db: AsyncSession) -> List[ScrapeSession]:
        """获取所有正在运行的会话"""
        result = await db.execute(
            select(ScrapeSession)
            .where(ScrapeSession.status == 'running')
            .order_by(ScrapeSession.started_at)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_recent_sessions_stats(
        db: AsyncSession,
        days: int = 7
    ) -> Dict[str, Any]:
        """获取最近N天的会话统计信息"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # 总会话数
        total_sessions_result = await db.execute(
            select(func.count(ScrapeSession.id))
            .where(ScrapeSession.created_at >= start_date)
        )
        total_sessions = total_sessions_result.scalar()
        
        # 成功会话数
        successful_sessions_result = await db.execute(
            select(func.count(ScrapeSession.id))
            .where(
                and_(
                    ScrapeSession.created_at >= start_date,
                    ScrapeSession.status == 'completed'
                )
            )
        )
        successful_sessions = successful_sessions_result.scalar()
        
        # 总帖子数和评论数
        posts_comments_result = await db.execute(
            select(
                func.sum(ScrapeSession.total_posts_found),
                func.sum(ScrapeSession.total_comments_found),
                func.sum(ScrapeSession.quality_comments_count),
                func.sum(ScrapeSession.published_count)
            )
            .where(ScrapeSession.created_at >= start_date)
        )
        posts_stats = posts_comments_result.first()
        
        # 平均会话时长
        avg_duration_result = await db.execute(
            select(func.avg(ScrapeSession.duration_seconds))
            .where(
                and_(
                    ScrapeSession.created_at >= start_date,
                    ScrapeSession.duration_seconds.isnot(None)
                )
            )
        )
        avg_duration = avg_duration_result.scalar()
        
        return {
            'period_days': days,
            'total_sessions': total_sessions or 0,
            'successful_sessions': successful_sessions or 0,
            'success_rate': (successful_sessions / total_sessions * 100) if total_sessions > 0 else 0,
            'total_posts_found': posts_stats[0] or 0,
            'total_comments_found': posts_stats[1] or 0,
            'quality_comments_found': posts_stats[2] or 0,
            'total_published': posts_stats[3] or 0,
            'avg_duration_seconds': int(avg_duration) if avg_duration else 0
        }
    
    @staticmethod
    async def cleanup_old_sessions(
        db: AsyncSession,
        days_to_keep: int = 30
    ) -> int:
        """清理旧的爬取会话（保留指定天数内的数据）"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # 获取要删除的会话ID
        result = await db.execute(
            select(ScrapeSession.id)
            .where(ScrapeSession.created_at < cutoff_date)
        )
        session_ids = [row[0] for row in result.all()]
        
        if not session_ids:
            return 0
        
        # 删除相关的Reddit内容
        await db.execute(
            select(RedditPost)
            .where(RedditPost.scrape_session_id.in_(session_ids))
        )
        await db.execute(
            select(RedditComment)
            .where(RedditComment.scrape_session_id.in_(session_ids))
        )
        
        # 删除会话
        deleted_count = len(session_ids)
        await db.execute(
            select(ScrapeSession)
            .where(ScrapeSession.id.in_(session_ids))
        )
        
        await db.commit()
        return deleted_count