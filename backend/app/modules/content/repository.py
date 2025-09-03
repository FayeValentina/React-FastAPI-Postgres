from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_, delete

from app.modules.content.models import RedditPost, RedditComment
from app.infrastructure.utils.common import get_current_time


class CRUDRedditContent:
    """Reddit内容服务类，用于管理Reddit帖子和评论数据"""
    @staticmethod
    async def get_comments_by_post(
        db: AsyncSession,
        post_id: str,
        limit: int = 100
    ) -> List[RedditComment]:
        """获取指定帖子的评论列表"""
        result = await db.execute(
            select(RedditComment)
            .where(RedditComment.post_id == post_id)
            .order_by(RedditComment.score.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    
    @staticmethod
    async def search_comments(
        db: AsyncSession,
        query: str,
        subreddits: Optional[List[str]] = None,
        min_score: int = 0,
        days: Optional[int] = None,
        limit: int = 100
    ) -> List[RedditComment]:
        """搜索评论内容"""
        conditions = [
            RedditComment.body.ilike(f'%{query}%'),
            RedditComment.score >= min_score
        ]
        
        if subreddits:
            conditions.append(RedditComment.subreddit.in_(subreddits))
        
        if days:
            start_date = get_current_time() - timedelta(days=days)
            conditions.append(RedditComment.scraped_at >= start_date)
        
        result = await db.execute(
            select(RedditComment)
            .where(and_(*conditions))
            .order_by(RedditComment.score.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_subreddit_stats(
        db: AsyncSession,
        subreddit: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """获取subreddit的统计信息"""
        start_date = get_current_time() - timedelta(days=days)
        
        # 帖子统计
        posts_stats = await db.execute(
            select(
                func.count(RedditPost.id),
                func.avg(RedditPost.score),
                func.max(RedditPost.score),
                func.avg(RedditPost.num_comments)
            )
            .where(
                and_(
                    RedditPost.subreddit == subreddit,
                    RedditPost.scraped_at >= start_date
                )
            )
        )
        post_data = posts_stats.first()
        
        # 评论统计
        comments_stats = await db.execute(
            select(
                func.count(RedditComment.id),
                func.avg(RedditComment.score),
                func.max(RedditComment.score)
            )
            .where(
                and_(
                    RedditComment.subreddit == subreddit,
                    RedditComment.scraped_at >= start_date
                )
            )
        )
        comment_data = comments_stats.first()
        
        # 热门作者
        top_authors = await db.execute(
            select(
                RedditComment.author,
                func.count(RedditComment.id).label('comment_count'),
                func.avg(RedditComment.score).label('avg_score')
            )
            .where(
                and_(
                    RedditComment.subreddit == subreddit,
                    RedditComment.scraped_at >= start_date,
                    RedditComment.author.isnot(None),
                    RedditComment.author != '[deleted]'
                )
            )
            .group_by(RedditComment.author)
            .order_by(func.count(RedditComment.id).desc())
            .limit(10)
        )
        
        return {
            'subreddit': subreddit,
            'period_days': days,
            'posts': {
                'total_count': post_data[0] or 0,
                'avg_score': float(post_data[1]) if post_data[1] else 0,
                'max_score': post_data[2] or 0,
                'avg_comments_per_post': float(post_data[3]) if post_data[3] else 0
            },
            'comments': {
                'total_count': comment_data[0] or 0,
                'avg_score': float(comment_data[1]) if comment_data[1] else 0,
                'max_score': comment_data[2] or 0
            },
            'top_authors': [
                {
                    'author': row.author,
                    'comment_count': row.comment_count,
                    'avg_score': float(row.avg_score)
                }
                for row in top_authors.all()
            ]
        }
    
    
    @staticmethod
    async def delete_old_content(
        db: AsyncSession,
        days_to_keep: int = 90
    ) -> Tuple[int, int]:
        """删除旧的Reddit内容数据"""
        cutoff_date = get_current_time() - timedelta(days=days_to_keep)
        
        # 删除旧评论
        old_comments = await db.execute(
            select(RedditComment.id)
            .where(RedditComment.scraped_at < cutoff_date)
        )
        comment_ids = [row[0] for row in old_comments.all()]
        
        if comment_ids:
            await db.execute(
                delete(RedditComment)
                .where(RedditComment.id.in_(comment_ids))
            )
        
        # 删除旧帖子
        old_posts = await db.execute(
            select(RedditPost.id)
            .where(RedditPost.scraped_at < cutoff_date)
        )
        post_ids = [row[0] for row in old_posts.all()]
        
        if post_ids:
            await db.execute(
                delete(RedditPost)
                .where(RedditPost.id.in_(post_ids))
            )
        
        await db.commit()
        return len(post_ids), len(comment_ids)

crud_reddit_content = CRUDRedditContent()