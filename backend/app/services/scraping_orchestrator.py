import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.reddit_scraper_service import RedditScraperService
from app.crud.bot_config import CRUDBotConfig
from app.crud.scrape_session import CRUDScrapeSession
from app.crud.reddit_content import CRUDRedditContent
from app.models.bot_config import BotConfig
from app.models.scrape_session import ScrapeSession

logger = logging.getLogger(__name__)


class ScrapingOrchestrator:
    """爬取编排器，协调整个爬取流程"""
    
    def __init__(self):
        self.reddit_scraper = RedditScraperService()
    
    async def execute_auto_scraping(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """执行自动爬取任务"""
        active_configs = await CRUDBotConfig.get_active_configs_for_auto_scraping(db)
        
        if not active_configs:
            logger.info("没有启用自动爬取的配置")
            return []
        
        config_ids = [config.id for config in active_configs]
        logger.info(f"找到 {len(config_ids)} 个启用自动爬取的配置")
        
        return await self.execute_multiple_configs(db, config_ids, 'auto')

    async def execute_multiple_configs(
        self,
        db: AsyncSession,
        config_ids: List[int],
        session_type: str = 'batch'
    ) -> List[Dict[str, Any]]:
        """并发执行多个配置的爬取"""
        tasks = []
        semaphore = asyncio.Semaphore(3)  # 限制并发数
        
        async def execute_with_semaphore(config_id: int):
            async with semaphore:
                # 每个并发任务使用独立的数据库会话
                from app.db.base import AsyncSessionLocal
                async with AsyncSessionLocal() as task_db:
                    return await self.execute_scraping_session(task_db, config_id, session_type)
        
        for config_id in config_ids:
            task = execute_with_semaphore(config_id)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 整理结果
        formatted_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                formatted_results.append({
                    'config_id': config_ids[i],
                    'status': 'error',
                    'error': str(result)
                })
            elif result:
                # 确保结果中包含config_id
                result['config_id'] = config_ids[i]
                formatted_results.append(result)
            else:
                formatted_results.append({
                    'config_id': config_ids[i],
                    'status': 'failed',
                    'error': '爬取执行失败'
                })
        
        return formatted_results
    
    async def execute_scraping_session(
        self,
        db: AsyncSession,
        bot_config_id: int,
        session_type: str = 'manual'
    ) -> Optional[Dict[str, Any]]:
        """执行爬取会话
        
        Args:
            db: 数据库会话
            bot_config_id: Bot配置ID
            session_type: 会话类型
            
        Returns:
            执行结果字典或None
        """
        try:
            # 获取bot配置并验证
            bot_config = await CRUDBotConfig.get_bot_config_by_id(db, bot_config_id)
            if not bot_config or not bot_config.is_active:
                logger.error(f"Bot配置 {bot_config_id} 不存在或未激活")
                return None
            
            # 创建新会话
            session = await self._create_new_session(db, bot_config_id, session_type)
            if not session:
                return None
            
            # 执行核心爬取逻辑
            return await self._execute_session_core(db, session, bot_config)
            
        except Exception as e:
            logger.error(f"执行爬取会话失败: {e}")
            return None
    
    async def _create_new_session(
        self,
        db: AsyncSession,
        bot_config_id: int,
        session_type: str
    ) -> Optional[ScrapeSession]:
        """创建新的爬取会话"""
        try:
            # 获取bot配置以创建快照
            bot_config = await CRUDBotConfig.get_bot_config_by_id(db, bot_config_id)
            if not bot_config:
                return None
            
            # 创建配置快照
            config_snapshot = {
                'target_subreddits': bot_config.target_subreddits,
                'posts_per_subreddit': bot_config.posts_per_subreddit,
                'comments_per_post': bot_config.comments_per_post,
                'sort_method': bot_config.sort_method,
                'time_filter': bot_config.time_filter,
                'enable_ai_filter': bot_config.enable_ai_filter,
                'ai_confidence_threshold': float(bot_config.ai_confidence_threshold),
                'min_comment_length': bot_config.min_comment_length,
                'max_comment_length': bot_config.max_comment_length
            }
            
            # 创建爬取会话
            return await CRUDScrapeSession.create_scrape_session(
                db, bot_config_id, session_type, config_snapshot
            )
        except Exception as e:
            logger.error(f"创建新会话失败: {e}")
            return None
    
    async def _execute_session_core(
        self,
        db: AsyncSession,
        session: ScrapeSession,
        bot_config: BotConfig
    ) -> Dict[str, Any]:
        """执行爬取会话的核心逻辑"""
        try:
            logger.info(f"开始执行爬取会话 {session.id}")
            
            # 开始会话
            await CRUDScrapeSession.start_session(db, session.id)
            
            # 执行爬取
            results = await self._execute_scraping(bot_config)
            
            # 保存结果到数据库
            total_posts, total_comments = await self._save_scraping_results(
                db, session.id, results
            )
            
            # 分析质量评论
            quality_comments = await self._analyze_comment_quality(
                db, session.id, bot_config
            )
            quality_comments_count = len(quality_comments) if quality_comments else 0
            
            # 完成会话
            await CRUDScrapeSession.complete_session(
                db,
                session.id,
                total_posts_found=total_posts,
                total_comments_found=total_comments,
                quality_comments_count=quality_comments_count
            )
            
            logger.info(f"爬取会话 {session.id} 完成")
            
            return {
                'session_id': session.id,
                'status': 'completed',
                'total_posts': total_posts,
                'total_comments': total_comments,
                'quality_comments': quality_comments_count,
                'subreddits_scraped': list(results.keys())
            }
            
        except Exception as e:
            logger.error(f"爬取会话 {session.id} 执行失败: {e}")
            
            # 标记会话失败
            await CRUDScrapeSession.complete_session(
                db,
                session.id,
                error_message=str(e),
                error_details={'exception_type': type(e).__name__}
            )
            
            return {
                'session_id': session.id,
                'status': 'failed',
                'error': str(e)
            }
    
    async def _execute_scraping(
        self,
        bot_config: BotConfig
    ) -> Dict[str, Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
        """执行实际的Reddit爬取"""
        # 准备并发爬取配置
        subreddit_configs = []
        for subreddit in bot_config.target_subreddits:
            config = {
                'name': subreddit,
                'limit': bot_config.posts_per_subreddit,
                'sort_by': bot_config.sort_method,
                'comments_limit': bot_config.comments_per_post,
                'time_filter': bot_config.time_filter
            }
            subreddit_configs.append(config)
        
        logger.info(f"开始并发爬取 {len(subreddit_configs)} 个subreddit")
        
        # 执行并发爬取
        results = await self.reddit_scraper.scrape_multiple_subreddits_concurrent(
            subreddit_configs
        )
        
        return results
    
    async def _save_scraping_results(
        self,
        db: AsyncSession,
        session_id: int,
        results: Dict[str, Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]
    ) -> Tuple[int, int]:
        """保存爬取结果到数据库"""
        total_posts = 0
        total_comments = 0
        
        for subreddit_name, (posts_data, comments_data) in results.items():
            if posts_data or comments_data:
                saved_posts, saved_comments = await CRUDRedditContent.save_posts_and_comments(
                    db, session_id, posts_data, comments_data
                )
                total_posts += saved_posts
                total_comments += saved_comments
                
                logger.info(
                    f"保存 r/{subreddit_name}: {saved_posts} 个帖子, {saved_comments} 条评论"
                )
        
        return total_posts, total_comments
    
    async def _analyze_comment_quality(
        self,
        db: AsyncSession,
        session_id: int,
        bot_config: BotConfig
    ) -> List[Any]:
        """分析评论质量，应用基础和AI过滤"""
        # 获取会话的评论
        comments = await CRUDRedditContent.get_comments_by_session(db, session_id)
        
        # 基础质量过滤：长度和分数
        quality_comments = [
            comment for comment in comments
            if (bot_config.min_comment_length <= len(comment.body) <= bot_config.max_comment_length
                and comment.score > 0)
        ]
        
        # 按分数排序
        quality_comments.sort(key=lambda x: x.score, reverse=True)
        
        # 这里可以扩展AI评估功能
        # if bot_config.enable_ai_filter:
        #     quality_comments = await self._ai_filter_comments(quality_comments, bot_config)
        
        return quality_comments
    
    async def cleanup_resources(self):
        """清理资源"""
        try:
            await self.reddit_scraper.close()
            logger.info("爬取编排器资源已清理")
        except Exception as e:
            logger.error(f"清理资源时出错: {e}")
    
    async def test_reddit_connection(self) -> Dict[str, Any]:
        """测试Reddit连接"""
        try:
            reddit = await self.reddit_scraper._get_reddit_instance()
            if reddit:
                # 尝试获取一个简单的subreddit信息
                test_subreddit = await reddit.subreddit('python')
                await test_subreddit.load()
                
                return {
                    'status': 'success',
                    'message': 'Reddit连接正常',
                    'test_subreddit': 'r/python'
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Reddit实例创建失败'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Reddit连接测试失败: {str(e)}'
            }