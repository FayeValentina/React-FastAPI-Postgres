from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from sqlalchemy.orm import selectinload, joinedload
from app.models.bot_config import BotConfig
from app.models.scrape_session import ScrapeSession, SessionStatus, SessionType
from app.models.reddit_content import RedditPost, RedditComment
from app.models.user import User


class CRUDScrapeSession:
    """爬取会话服务类，用于管理爬取会话的生命周期"""
    
    @staticmethod
    async def create_scrape_session(
        db: AsyncSession,
        bot_config_id: int,
        session_type: SessionType = SessionType.MANUAL,
        config_snapshot: Optional[Dict[str, Any]] = None
    ) -> ScrapeSession:
        """创建新的爬取会话"""
        session = ScrapeSession(
            bot_config_id=bot_config_id,
            session_type=session_type,
            status=SessionStatus.PENDING,
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
        
        session.status = SessionStatus.RUNNING
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
        session.status = SessionStatus.FAILED if error_message else SessionStatus.COMPLETED
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
    async def get_sessions(
        db: AsyncSession,
        session_id: Optional[int] = None,
        bot_config_id: Optional[int] = None,
        user_id: Optional[int] = None,
        limit: int = 50,
        status: Optional[str] = None,
        session_type: Optional[str] = None,
        include_content: bool = False
    ) -> Union[Optional[ScrapeSession], List[ScrapeSession]]:
        """统一的会话查询方法
        
        Args:
            db: 数据库会话
            session_id: 会话ID，如果提供则返回单个会话
            bot_config_id: Bot配置ID (按配置查询)
            user_id: 用户ID (按用户查询)
            limit: 查询限制
            status: 状态过滤
            session_type: 类型过滤
            include_content: 是否包含Reddit内容数据
            
        Returns:
            如果提供session_id，返回单个ScrapeSession或None
            否则返回ScrapeSession列表
        """
        query = select(ScrapeSession)
        
        # 联表查询bot_config和user信息
        query = query.options(
            joinedload(ScrapeSession.bot_config).joinedload(BotConfig.user)
        )
        
        # 如果需要包含内容数据
        if include_content:
            query = query.options(
                selectinload(ScrapeSession.reddit_posts),
                selectinload(ScrapeSession.reddit_comments)
            )
        
        # 根据session_id筛选（返回单个结果）
        if session_id is not None:
            query = query.where(ScrapeSession.id == session_id)
            result = await db.execute(query)
            session = result.scalar_one_or_none()
            
            # 添加计算字段
            if session:
                session.bot_config_name = session.bot_config.name if session.bot_config else None
                session.user_username = session.bot_config.user.username if session.bot_config and session.bot_config.user else None
            
            return session
        
        # 根据bot_config_id筛选
        if bot_config_id:
            query = query.where(ScrapeSession.bot_config_id == bot_config_id)
        elif user_id:
            # 按用户查询 - 先获取用户的配置IDs
            config_result = await db.execute(
                select(BotConfig.id).where(BotConfig.user_id == user_id)
            )
            config_ids = [row[0] for row in config_result.all()]
            if config_ids:
                query = query.where(ScrapeSession.bot_config_id.in_(config_ids))
            else:
                return []
        
        # 应用过滤条件
        if status:
            query = query.where(ScrapeSession.status == status)
        if session_type:
            query = query.where(ScrapeSession.session_type == session_type)
        
        # 排序和限制
        query = query.order_by(ScrapeSession.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        sessions = result.scalars().all()
        
        # 添加计算字段
        for session in sessions:
            session.bot_config_name = session.bot_config.name if session.bot_config else None
            session.user_username = session.bot_config.user.username if session.bot_config and session.bot_config.user else None
        
        return sessions
    
    # 保留向后兼容的方法
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
            delete(RedditPost)
            .where(RedditPost.scrape_session_id.in_(session_ids))
        )
        await db.execute(
            delete(RedditComment)
            .where(RedditComment.scrape_session_id.in_(session_ids))
        )
        
        # 删除会话
        deleted_count = len(session_ids)
        await db.execute(
            delete(ScrapeSession)
            .where(ScrapeSession.id.in_(session_ids))
        )
        
        await db.commit()
        return deleted_count
    
    @staticmethod
    async def get_sessions_before_date(
        db: AsyncSession,
        cutoff_date: datetime
    ) -> List[ScrapeSession]:
        """获取指定日期之前的会话"""
        result = await db.execute(
            select(ScrapeSession)
            .where(ScrapeSession.created_at < cutoff_date)
            .order_by(ScrapeSession.created_at)
        )
        return result.scalars().all()
    
    @staticmethod
    async def delete_sessions_before_date(
        db: AsyncSession,
        cutoff_date: datetime
    ) -> int:
        """删除指定日期之前的会话"""
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
            delete(RedditPost)
            .where(RedditPost.scrape_session_id.in_(session_ids))
        )
        await db.execute(
            delete(RedditComment)
            .where(RedditComment.scrape_session_id.in_(session_ids))
        )
        
        # 删除会话
        deleted_count = len(session_ids)
        await db.execute(
            delete(ScrapeSession)
            .where(ScrapeSession.id.in_(session_ids))
        )
        
        await db.commit()
        return deleted_count