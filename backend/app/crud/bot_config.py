from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.bot_config import BotConfig
from app.models.scrape_session import ScrapeSession
from app.models.user import User


class CRUDBotConfig:
    """Bot配置服务类，用于管理爬虫机器人的配置"""
    
    @staticmethod
    async def create_bot_config(
        db: AsyncSession,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        target_subreddits: List[str] = None,
        posts_per_subreddit: int = 50,
        comments_per_post: int = 20,
        sort_method: str = 'hot',
        time_filter: str = 'day',
        enable_ai_filter: bool = True,
        ai_confidence_threshold: float = 0.8,
        min_comment_length: int = 10,
        max_comment_length: int = 280,
        auto_scrape_enabled: bool = False,
        scrape_interval_hours: int = 24,
        max_daily_posts: int = 5
    ) -> BotConfig:
        """创建新的bot配置"""
        if target_subreddits is None:
            target_subreddits = ['python', 'programming', 'MachineLearning']
        
        bot_config = BotConfig(
            user_id=user_id,
            name=name,
            description=description,
            target_subreddits=target_subreddits,
            posts_per_subreddit=posts_per_subreddit,
            comments_per_post=comments_per_post,
            sort_method=sort_method,
            time_filter=time_filter,
            enable_ai_filter=enable_ai_filter,
            ai_confidence_threshold=ai_confidence_threshold,
            min_comment_length=min_comment_length,
            max_comment_length=max_comment_length,
            auto_scrape_enabled=auto_scrape_enabled,
            scrape_interval_hours=scrape_interval_hours,
            max_daily_posts=max_daily_posts
        )
        
        db.add(bot_config)
        await db.commit()
        await db.refresh(bot_config)
        return bot_config
    
    @staticmethod
    async def get_bot_config_by_id(
        db: AsyncSession, 
        config_id: int
    ) -> Optional[BotConfig]:
        """根据ID获取bot配置"""
        result = await db.execute(
            select(BotConfig)
            .options(selectinload(BotConfig.scrape_sessions), selectinload(BotConfig.user))
            .where(BotConfig.id == config_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_bot_configs(
        db: AsyncSession, 
        user_id: int, 
        is_active: Optional[bool] = None
    ) -> List[BotConfig]:
        """获取用户的bot配置列表"""
        query = select(BotConfig).options(selectinload(BotConfig.user)).where(BotConfig.user_id == user_id)
        
        if is_active is not None:
            query = query.where(BotConfig.is_active == is_active)
        
        query = query.order_by(BotConfig.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_all_bot_configs(
        db: AsyncSession, 
        is_active: Optional[bool] = None
    ) -> List[BotConfig]:
        """获取所有bot配置列表（超级用户使用）"""
        query = select(BotConfig).options(selectinload(BotConfig.user))
        
        if is_active is not None:
            query = query.where(BotConfig.is_active == is_active)
        
        query = query.order_by(BotConfig.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def update_bot_config(
        db: AsyncSession,
        config_id: int,
        **updates
    ) -> Optional[BotConfig]:
        """更新bot配置"""
        result = await db.execute(
            select(BotConfig).where(BotConfig.id == config_id)
        )
        bot_config = result.scalar_one_or_none()
        
        if not bot_config:
            return None
        
        for key, value in updates.items():
            if hasattr(bot_config, key):
                setattr(bot_config, key, value)
        
        await db.commit()
        await db.refresh(bot_config)
        return bot_config
    
    @staticmethod
    async def delete_bot_config(
        db: AsyncSession, 
        config_id: int
    ) -> bool:
        """删除bot配置"""
        result = await db.execute(
            select(BotConfig).where(BotConfig.id == config_id)
        )
        bot_config = result.scalar_one_or_none()
        
        if not bot_config:
            return False
        
        await db.delete(bot_config)
        await db.commit()
        return True
    
    
    @staticmethod
    async def get_active_configs_for_auto_scraping(
        db: AsyncSession
    ) -> List[BotConfig]:
        """获取所有启用自动爬取的配置"""
        result = await db.execute(
            select(BotConfig)
            .where(
                BotConfig.is_active == True,
                BotConfig.auto_scrape_enabled == True
            )
            .order_by(BotConfig.scrape_interval_hours)
        )
        return result.scalars().all()
    
