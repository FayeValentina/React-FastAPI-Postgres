import asyncpraw
from datetime import datetime
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.reddit_content import RedditPost, RedditComment
from app.models.scrape_session import ScrapeSession

logger = logging.getLogger(__name__)


class RedditScraperService:
    """Reddit爬取服务类，用于爬取Reddit内容"""
    
    def __init__(self):
        self.reddit = None
        self._session_lock = asyncio.Lock()
        
    async def _get_reddit_instance(self):
        """获取Reddit实例，使用单例模式"""
        if self.reddit is None:
            async with self._session_lock:
                if self.reddit is None:
                    # 从设置中获取Reddit配置
                    reddit_config = {
                        'client_id': settings.reddit.CLIENT_ID,
                        'client_secret': settings.reddit.CLIENT_SECRET,
                        'user_agent': settings.reddit.USER_AGENT,
                        'username': settings.reddit.USERNAME,
                        'password': settings.reddit.PASSWORD
                    }
                    
                    if reddit_config['username'] and reddit_config['password']:
                        self.reddit = asyncpraw.Reddit(
                            client_id=reddit_config['client_id'],
                            client_secret=reddit_config['client_secret'],
                            user_agent=reddit_config['user_agent'],
                            username=reddit_config['username'],
                            password=reddit_config['password']
                        )
                    else:
                        self.reddit = asyncpraw.Reddit(
                            client_id=reddit_config['client_id'],
                            client_secret=reddit_config['client_secret'],
                            user_agent=reddit_config['user_agent']
                        )
        return self.reddit
    
    async def scrape_posts_with_details(
        self, 
        subreddit_name: str, 
        limit: int = 50, 
        sort_by: str = 'hot', 
        comments_limit: int = 20, 
        time_filter: str = 'all'
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        异步爬取指定subreddit的帖子及其详细内容和评论
        
        Args:
            subreddit_name: subreddit名称
            limit: 爬取帖子数量限制
            sort_by: 排序方式 ('hot', 'new', 'top', 'controversial', 'rising', 'gilded')
            comments_limit: 每个帖子的评论数量限制
            time_filter: 时间筛选 ('all', 'day', 'hour', 'month', 'week', 'year')
        
        Returns:
            Tuple[posts_data, comments_data]
        """
        logger.info(f"开始爬取 r/{subreddit_name}，排序方式: {sort_by}")
        
        # 爬取帖子列表
        posts_data = await self._scrape_subreddit_async(
            subreddit_name, limit, sort_by, time_filter
        )
        
        if not posts_data:
            logger.warning(f"从 r/{subreddit_name} 未获取到帖子")
            return [], []
        
        logger.info(f"从 r/{subreddit_name} 获取了 {len(posts_data)} 个帖子，开始爬取评论")
        
        # 并发爬取所有帖子的评论
        all_comments = await self._scrape_all_comments_async(
            posts_data, comments_limit, subreddit_name
        )
        
        logger.info(f"完成爬取：{len(posts_data)} 个帖子，{len(all_comments)} 条评论")
        return posts_data, all_comments
    
    async def _scrape_subreddit_async(
        self, 
        subreddit_name: str, 
        limit: int = 100, 
        sort_by: str = 'hot', 
        time_filter: str = 'all'
    ) -> List[Dict[str, Any]]:
        """异步爬取指定subreddit的帖子"""
        try:
            reddit = await self._get_reddit_instance()
            subreddit = await reddit.subreddit(subreddit_name)
            posts_data = []
            
            logger.info(f"使用排序方式: {sort_by}，时间筛选: {time_filter if sort_by in ['top', 'controversial'] else 'N/A'}")
            
            # 根据排序方式获取帖子
            if sort_by == 'hot':
                posts = subreddit.hot(limit=limit)
            elif sort_by == 'new':
                posts = subreddit.new(limit=limit)
            elif sort_by == 'top':
                posts = subreddit.top(limit=limit, time_filter=time_filter)
            elif sort_by == 'controversial':
                posts = subreddit.controversial(limit=limit, time_filter=time_filter)
            elif sort_by == 'rising':
                posts = subreddit.rising(limit=limit)
            elif sort_by == 'gilded':
                posts = subreddit.gilded(limit=limit)
            else:
                logger.warning(f"未知排序方式 {sort_by}，回退到 'hot'")
                posts = subreddit.hot(limit=limit)
            
            # 异步处理每个帖子
            async for post in posts:
                try:
                    post_data = {
                        'id': post.id,
                        'title': post.title,
                        'author': str(post.author) if post.author else '[deleted]',
                        'score': post.score,
                        'upvote_ratio': post.upvote_ratio,
                        'num_comments': post.num_comments,
                        'created_utc': datetime.fromtimestamp(post.created_utc),
                        'url': post.url,
                        'selftext': post.selftext,
                        'subreddit': subreddit_name,
                        'permalink': f"https://reddit.com{post.permalink}",
                        'is_self': post.is_self,
                        'domain': post.domain,
                        'flair': post.link_flair_text,
                        'is_nsfw': post.over_18,
                        'is_spoiler': post.spoiler
                    }
                    posts_data.append(post_data)
                    
                    if len(posts_data) % 10 == 0:
                        logger.info(f"爬取进度: {len(posts_data)}/{limit}")
                        
                except Exception as e:
                    logger.error(f"处理帖子时出错: {e}")
                    continue
            
            logger.info(f"成功爬取了 {len(posts_data)} 个帖子")
            return posts_data
            
        except Exception as e:
            logger.error(f"爬取 r/{subreddit_name} 时出错: {e}")
            return []
    
    async def _scrape_all_comments_async(
        self, 
        posts_data: List[Dict[str, Any]], 
        comments_limit: int, 
        subreddit_name: str
    ) -> List[Dict[str, Any]]:
        """并发爬取所有帖子的评论"""
        # 创建并发任务列表
        tasks = []
        semaphore = asyncio.Semaphore(10)  # 限制并发数为10，避免过载
        
        async def scrape_with_semaphore(post_id: str) -> List[Dict[str, Any]]:
            async with semaphore:
                return await self._scrape_post_comments_async(post_id, comments_limit, subreddit_name)
        
        for post in posts_data:
            task = scrape_with_semaphore(post['id'])
            tasks.append(task)
        
        # 并发执行所有评论爬取任务
        comments_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 合并所有评论
        all_comments = []
        successful_scrapes = 0
        
        for i, result in enumerate(comments_results):
            if isinstance(result, Exception):
                logger.error(f"爬取第{i+1}个帖子的评论时出错: {result}")
                continue
            
            if result:
                all_comments.extend(result)
                successful_scrapes += 1
        
        logger.info(f"成功爬取了 {successful_scrapes}/{len(posts_data)} 个帖子的评论")
        return all_comments
    
    async def _scrape_post_comments_async(
        self, 
        post_id: str, 
        limit: int = 50, 
        subreddit_name: str = ""
    ) -> List[Dict[str, Any]]:
        """异步爬取指定帖子的评论"""
        try:
            reddit = await self._get_reddit_instance()
            submission = await reddit.submission(id=post_id)
            
            # 扩展评论树（异步）
            await submission.comments.replace_more(limit=0)
            
            comments_data = []
            comment_count = 0
            
            # 异步处理评论
            for comment in submission.comments.list():
                if comment_count >= limit:
                    break
                
                try:
                    if hasattr(comment, 'body') and comment.body != '[deleted]':
                        comment_data = {
                            'id': comment.id,
                            'post_id': post_id,
                            'author': str(comment.author) if comment.author else '[deleted]',
                            'body': comment.body,
                            'score': comment.score,
                            'created_utc': datetime.fromtimestamp(comment.created_utc),
                            'parent_id': comment.parent_id,
                            'is_submitter': comment.is_submitter,
                            'subreddit': subreddit_name,
                            'depth': comment.depth if hasattr(comment, 'depth') else 0,
                            'controversiality': getattr(comment, 'controversiality', 0)
                        }
                        comments_data.append(comment_data)
                        comment_count += 1
                
                except Exception as e:
                    logger.error(f"处理评论时出错: {e}")
                    continue
            
            return comments_data
            
        except Exception as e:
            logger.error(f"爬取帖子 {post_id} 的评论时出错: {e}")
            return []
    
    async def scrape_multiple_subreddits_concurrent(
        self, 
        subreddit_configs: List[Dict[str, Any]]
    ) -> Dict[str, Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
        """
        并发爬取多个subreddit
        
        Args:
            subreddit_configs: 包含subreddit配置的列表
                每个配置包含: {
                    'name': 'subreddit名称',
                    'limit': 帖子数量,
                    'sort_by': 排序方式,
                    'comments_limit': 评论数量,
                    'time_filter': 时间筛选
                }
        
        Returns:
            Dict[subreddit_name: (posts_data, comments_data)]
        """
        logger.info(f"开始并发爬取 {len(subreddit_configs)} 个subreddit")
        
        # 创建并发任务
        tasks = []
        semaphore = asyncio.Semaphore(5)  # 限制同时爬取的subreddit数量
        
        async def scrape_with_semaphore(config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
            async with semaphore:
                return await self.scrape_posts_with_details(
                    subreddit_name=config['name'],
                    limit=config.get('limit', 50),
                    sort_by=config.get('sort_by', 'hot'),
                    comments_limit=config.get('comments_limit', 20),
                    time_filter=config.get('time_filter', 'all')
                )
        
        for config in subreddit_configs:
            task = scrape_with_semaphore(config)
            tasks.append(task)
        
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 整理结果
        scraped_data = {}
        for i, result in enumerate(results):
            subreddit_name = subreddit_configs[i]['name']
            
            if isinstance(result, Exception):
                logger.error(f"爬取 r/{subreddit_name} 时出错: {result}")
                scraped_data[subreddit_name] = ([], [])
            else:
                scraped_data[subreddit_name] = result
        
        logger.info("完成所有subreddit的并发爬取")
        return scraped_data
    
    async def close(self):
        """关闭Reddit连接"""
        if self.reddit:
            await self.reddit.close()
            logger.info("Reddit连接已关闭")