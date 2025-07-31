from typing import List, Optional, Dict, Any, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload

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
    async def get_bot_configs(
        db: AsyncSession,
        config_id: Optional[int] = None,
        user_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        include_relations: bool = True
    ) -> Union[Optional[BotConfig], List[BotConfig]]:
        """
        统一的配置获取方法
        
        Args:
            db: 数据库会话
            config_id: 配置ID，如果提供则返回单个配置
            user_id: 用户ID，如果提供则过滤该用户的配置
            is_active: 活跃状态过滤
            include_relations: 是否包含关联数据（用户、会话等）
            
        Returns:
            如果提供config_id，返回单个BotConfig或None
            否则返回BotConfig列表
        """
        query = select(BotConfig)
        
        # 添加关联数据加载
        if include_relations:
            if config_id is not None:
                # 单个配置需要加载会话关联
                query = query.options(
                    selectinload(BotConfig.scrape_sessions), 
                    joinedload(BotConfig.user)
                )
            else:
                # 列表查询只加载用户关联
                query = query.options(joinedload(BotConfig.user))
        
        # 根据config_id筛选（返回单个结果）
        if config_id is not None:
            query = query.where(BotConfig.id == config_id)
            result = await db.execute(query)
            config = result.scalar_one_or_none()
            
            # 添加计算字段
            if config and include_relations:
                config.user_username = config.user.username if config.user else None
                config.user_fullname = config.user.full_name if config.user else None
            
            return config
        
        # 根据user_id筛选
        if user_id is not None:
            query = query.where(BotConfig.user_id == user_id)
        
        # 根据is_active筛选
        if is_active is not None:
            query = query.where(BotConfig.is_active == is_active)
        
        # 按创建时间倒序排列
        query = query.order_by(BotConfig.created_at.desc())
        
        result = await db.execute(query)
        configs = result.scalars().all()
        
        # 添加计算字段
        if include_relations:
            for config in configs:
                config.user_username = config.user.username if config.user else None
                config.user_fullname = config.user.full_name if config.user else None
        
        return configs
    
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
    
