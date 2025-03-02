from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_
from sqlalchemy.exc import IntegrityError
from typing import Optional, List, Dict, Any

from app.models.post import Post
from app.schemas.post import PostCreate, PostUpdateFull, PostUpdatePartial
from app.core.exceptions import (
    ResourceNotFoundError,
    DatabaseError,
    InsufficientPermissionsError
)


# 错误常量
ERROR_CREATE_POST = "创建帖子时出错"
ERROR_UPDATE_POST = "更新帖子时出错"
ERROR_DELETE_POST = "删除帖子时出错"


class CRUDPost:
    async def get(self, db: AsyncSession, id: int) -> Optional[Post]:
        """获取指定ID的帖子"""
        result = await db.execute(select(Post).filter(Post.id == id))
        return result.scalar_one_or_none()

    async def get_multi(
        self, 
        db: AsyncSession, 
        *,
        filters: Dict[str, Any] = None,
        skip: int = 0, 
        limit: int = 100,
        sort_by: List[str] = ["created_at"]
    ) -> List[Post]:
        """
        获取多个帖子
        
        参数:
            db: 数据库会话
            filters: 过滤条件
            skip: 跳过记录数
            limit: 返回记录数
            sort_by: 排序字段列表
            
        返回:
            帖子列表
        """
        query = select(Post)
        
        # 应用过滤条件
        if filters:
            filter_conditions = []
            
            # 按标题或内容查询
            if filters.get("search"):
                search = filters["search"]
                filter_conditions.append(
                    or_(
                        Post.title.ilike(f"%{search}%"),
                        Post.content.ilike(f"%{search}%"),
                        Post.summary.ilike(f"%{search}%")
                    )
                )
            
            # 按作者ID查询
            if filters.get("author_id") is not None:
                filter_conditions.append(Post.author_id == filters["author_id"])
                
            # 按发布状态查询
            if filters.get("published") is not None:
                filter_conditions.append(Post.published == filters["published"])
                
            if filter_conditions:
                query = query.where(and_(*filter_conditions))
        
        # 应用排序
        for sort_field in sort_by:
            # 检查是否是降序排序
            if sort_field.startswith('-'):
                field_name = sort_field[1:]
                if hasattr(Post, field_name):
                    query = query.order_by(desc(getattr(Post, field_name)))
            else:
                if hasattr(Post, sort_field):
                    query = query.order_by(getattr(Post, sort_field))
        
        # 应用分页
        query = query.offset(skip).limit(limit)
        
        # 执行查询
        result = await db.execute(query)
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: PostCreate, author_id: int) -> Post:
        """
        创建新帖子
        
        参数:
            db: 数据库会话
            obj_in: 帖子创建数据
            author_id: 作者ID
            
        返回:
            创建的帖子对象
        """
        try:
            db_obj = Post(
                title=obj_in.title,
                content=obj_in.content,
                summary=obj_in.summary,
                published=obj_in.published,
                author_id=author_id
            )
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            await db.rollback()
            raise DatabaseError(detail=ERROR_CREATE_POST)

    async def update(
        self, 
        db: AsyncSession, 
        *, 
        db_obj: Post, 
        obj_in: PostUpdateFull | PostUpdatePartial
    ) -> Post:
        """
        更新帖子
        
        参数:
            db: 数据库会话
            db_obj: 数据库中的帖子对象
            obj_in: 更新数据
            
        返回:
            更新后的帖子对象
        """
        try:
            # 如果是部分更新，只更新非None字段
            update_data = obj_in.model_dump(exclude_unset=True)
            
            for field, value in update_data.items():
                setattr(db_obj, field, value)
                
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            await db.rollback()
            raise DatabaseError(detail=ERROR_UPDATE_POST)

    async def delete(
        self, 
        db: AsyncSession, 
        *, 
        db_obj: Post
    ) -> Post:
        """
        删除帖子
        
        参数:
            db: 数据库会话
            db_obj: 要删除的帖子对象
            
        返回:
            被删除的帖子对象
        """
        try:
            await db.delete(db_obj)
            await db.commit()
            return db_obj
        except IntegrityError:
            await db.rollback()
            raise DatabaseError(detail=ERROR_DELETE_POST)

    async def is_author(self, db_obj: Post, user_id: int) -> bool:
        """
        检查用户是否是帖子的作者
        
        参数:
            db_obj: 帖子对象
            user_id: 用户ID
            
        返回:
            如果用户是作者则返回True，否则返回False
        """
        return db_obj.author_id == user_id


# 创建CRUDPost的单例实例
post = CRUDPost() 