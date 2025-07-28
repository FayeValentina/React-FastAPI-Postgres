from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_
from sqlalchemy.orm import selectinload

from app.models.reddit_content import RedditPost, RedditComment
from app.models.scrape_session import ScrapeSession


class CRUDRedditContent:
    """Reddit内容服务类，用于管理Reddit帖子和评论数据"""
    
    @staticmethod
    async def save_posts_and_comments(
        db: AsyncSession,
        session_id: int,
        posts_data: List[Dict[str, Any]],
        comments_data: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        """保存帖子和评论数据到数据库"""
        saved_posts = 0
        saved_comments = 0
        
        # 保存帖子
        for post_data in posts_data:
            # 检查帖子是否已存在
            existing_post = await db.execute(
                select(RedditPost).where(RedditPost.id == post_data['id'])
            )
            if existing_post.scalar_one_or_none():
                continue
            
            post = RedditPost(
                id=post_data['id'],
                scrape_session_id=session_id,
                title=post_data['title'],
                author=post_data.get('author'),
                subreddit=post_data['subreddit'],
                content=post_data.get('selftext'),
                url=post_data.get('url'),
                domain=post_data.get('domain'),
                score=post_data.get('score', 0),
                upvote_ratio=post_data.get('upvote_ratio'),
                num_comments=post_data.get('num_comments', 0),
                flair_text=post_data.get('flair'),
                is_self=post_data.get('is_self', False),
                is_nsfw=post_data.get('is_nsfw', False),
                is_spoiler=post_data.get('is_spoiler', False),
                reddit_created_at=post_data['created_utc']
            )
            db.add(post)
            saved_posts += 1
        
        # 保存评论
        for comment_data in comments_data:
            # 检查评论是否已存在
            existing_comment = await db.execute(
                select(RedditComment).where(RedditComment.id == comment_data['id'])
            )
            if existing_comment.scalar_one_or_none():
                continue
            
            comment = RedditComment(
                id=comment_data['id'],
                post_id=comment_data['post_id'],
                scrape_session_id=session_id,
                author=comment_data.get('author'),
                body=comment_data['body'],
                subreddit=comment_data['subreddit'],
                parent_id=comment_data.get('parent_id'),
                depth=comment_data.get('depth', 0),
                is_submitter=comment_data.get('is_submitter', False),
                score=comment_data.get('score', 0),
                controversiality=comment_data.get('controversiality', 0),
                reddit_created_at=comment_data['created_utc']
            )
            db.add(comment)
            saved_comments += 1
        
        await db.commit()
        return saved_posts, saved_comments
    
    @staticmethod
    async def get_posts_by_session(
        db: AsyncSession,
        session_id: int,
        limit: int = 100
    ) -> List[RedditPost]:
        """获取指定会话的帖子列表"""
        result = await db.execute(
            select(RedditPost)
            .where(RedditPost.scrape_session_id == session_id)
            .order_by(RedditPost.score.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_comments_by_session(
        db: AsyncSession,
        session_id: int,
        limit: int = 500
    ) -> List[RedditComment]:
        """获取指定会话的评论列表"""
        result = await db.execute(
            select(RedditComment)
            .where(RedditComment.scrape_session_id == session_id)
            .order_by(RedditComment.score.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
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
    async def get_top_comments_by_subreddit(
        db: AsyncSession,
        subreddit: str,
        days: int = 7,
        limit: int = 50
    ) -> List[RedditComment]:
        """获取指定subreddit最近N天的热门评论"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await db.execute(
            select(RedditComment)
            .where(
                and_(
                    RedditComment.subreddit == subreddit,
                    RedditComment.scraped_at >= start_date
                )
            )
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
            start_date = datetime.utcnow() - timedelta(days=days)
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
        start_date = datetime.utcnow() - timedelta(days=days)
        
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
    async def get_content_by_score_range(
        db: AsyncSession,
        min_score: int,
        max_score: Optional[int] = None,
        content_type: str = 'comment',  # 'comment' or 'post'
        subreddits: Optional[List[str]] = None,
        limit: int = 100
    ) -> List:
        """根据分数范围获取内容"""
        if content_type == 'post':
            model = RedditPost
            score_field = RedditPost.score
        else:
            model = RedditComment
            score_field = RedditComment.score
        
        conditions = [score_field >= min_score]
        
        if max_score is not None:
            conditions.append(score_field <= max_score)
        
        if subreddits:
            if content_type == 'post':
                conditions.append(RedditPost.subreddit.in_(subreddits))
            else:
                conditions.append(RedditComment.subreddit.in_(subreddits))
        
        result = await db.execute(
            select(model)
            .where(and_(*conditions))
            .order_by(score_field.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def delete_old_content(
        db: AsyncSession,
        days_to_keep: int = 90
    ) -> Tuple[int, int]:
        """删除旧的Reddit内容数据"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # 删除旧评论
        old_comments = await db.execute(
            select(RedditComment.id)
            .where(RedditComment.scraped_at < cutoff_date)
        )
        comment_ids = [row[0] for row in old_comments.all()]
        
        if comment_ids:
            await db.execute(
                select(RedditComment)
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
                select(RedditPost)
                .where(RedditPost.id.in_(post_ids))
            )
        
        await db.commit()
        return len(post_ids), len(comment_ids)