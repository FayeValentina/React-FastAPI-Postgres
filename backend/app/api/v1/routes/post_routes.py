from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Annotated, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.post import (
    PostCreate, PostResponse, PostUpdateFull, PostUpdatePartial, PostDetailResponse
)
from app.crud.post import post
from app.db.base import get_async_session
from app.models.user import User
from app.api.v1.dependencies.current_user import (
    get_current_active_user,
    get_current_superuser
)
from app.core.exceptions import (
    ResourceNotFoundError,
    InsufficientPermissionsError
)
from app.utils.common import handle_error

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostResponse)
async def create_post(
    post_data: PostCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    创建新帖子
    
    需要登录权限
    """
    try:
        return await post.create(db, obj_in=post_data, author_id=current_user.id)
    except Exception as e:
        raise handle_error(e)


@router.get("", response_model=List[PostResponse])
async def get_posts(
    db: AsyncSession = Depends(get_async_session),
    search: Annotated[Optional[str], Query(description="搜索标题、内容或摘要")] = None,
    author_id: Annotated[Optional[int], Query(description="作者ID")] = None,
    published: Annotated[Optional[bool], Query(description="是否已发布")] = None,
    skip: Annotated[int, Query(ge=0, description="跳过记录数")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="返回记录数")] = 20,
    sort_by: Annotated[List[str], Query(description="排序字段，前缀'-'表示降序")] = ["created_at"],
    current_user: Optional[User] = Depends(get_current_active_user)
):
    """
    获取帖子列表
    
    支持过滤条件：
    - search: 搜索标题、内容或摘要（模糊匹配）
    - author_id: 作者ID（精确匹配）
    - published: 是否已发布
    
    支持分页：
    - skip: 跳过记录数
    - limit: 返回记录数
    
    支持排序：
    - 默认按创建时间排序
    - 在字段名前加'-'表示降序排序，例如：-created_at
    """
    try:
        # 构建过滤条件
        filters = {}
        if search:
            filters["search"] = search
        if author_id:
            filters["author_id"] = author_id
            
        # 如果不是超级用户，普通用户只能看到已发布的帖子，或者自己的所有帖子
        if not current_user.is_superuser:
            if published is not None:
                filters["published"] = published
            elif author_id != current_user.id:
                # 如果查看的不是自己的帖子，只显示已发布的
                filters["published"] = True
        else:
            # 超级用户可以按发布状态过滤
            if published is not None:
                filters["published"] = published
                
        # 获取帖子列表
        posts = await post.get_multi(
            db, 
            filters=filters, 
            skip=skip, 
            limit=limit, 
            sort_by=sort_by
        )
        return posts
    except Exception as e:
        raise handle_error(e)


@router.get("/{post_id}", response_model=PostDetailResponse)
async def get_post(
    post_id: Annotated[int, Path(description="帖子ID")],
    db: AsyncSession = Depends(get_async_session),
    current_user: Optional[User] = Depends(get_current_active_user)
):
    """
    获取指定ID的帖子详情
    
    需要登录权限，如果帖子未发布，只有作者和管理员可以查看
    """
    try:
        db_post = await post.get(db, id=post_id)
        if not db_post:
            raise ResourceNotFoundError(detail="帖子不存在")
        
        # 如果帖子未发布，检查权限
        if not db_post.published:
            is_author = await post.is_author(db_post, current_user.id)
            if not is_author and not current_user.is_superuser:
                raise InsufficientPermissionsError("没有权限查看未发布的帖子")
                
        return db_post
    except Exception as e:
        raise handle_error(e)


@router.put("/{post_id}", response_model=PostResponse)
async def update_post_full(
    post_id: Annotated[int, Path(description="帖子ID")],
    post_data: PostUpdateFull,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    完整更新帖子信息
    
    需要作者权限或管理员权限
    """
    try:
        db_post = await post.get(db, id=post_id)
        if not db_post:
            raise ResourceNotFoundError(detail="帖子不存在")
            
        # 检查权限
        is_author = await post.is_author(db_post, current_user.id)
        if not is_author and not current_user.is_superuser:
            raise InsufficientPermissionsError("只有作者或管理员可以更新帖子")
            
        # 更新帖子
        return await post.update(db, db_obj=db_post, obj_in=post_data)
    except Exception as e:
        raise handle_error(e)


@router.patch("/{post_id}", response_model=PostResponse)
async def update_post_partial(
    post_id: Annotated[int, Path(description="帖子ID")],
    post_data: PostUpdatePartial,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    部分更新帖子信息
    
    需要作者权限或管理员权限
    """
    try:
        db_post = await post.get(db, id=post_id)
        if not db_post:
            raise ResourceNotFoundError(detail="帖子不存在")
            
        # 检查权限
        is_author = await post.is_author(db_post, current_user.id)
        if not is_author and not current_user.is_superuser:
            raise InsufficientPermissionsError("只有作者或管理员可以更新帖子")
            
        # 更新帖子
        return await post.update(db, db_obj=db_post, obj_in=post_data)
    except Exception as e:
        raise handle_error(e)


@router.delete("/{post_id}", response_model=PostResponse)
async def delete_post(
    post_id: Annotated[int, Path(description="帖子ID")],
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    删除帖子
    
    需要作者权限或管理员权限
    """
    try:
        db_post = await post.get(db, id=post_id)
        if not db_post:
            raise ResourceNotFoundError(detail="帖子不存在")
            
        # 检查权限
        is_author = await post.is_author(db_post, current_user.id)
        if not is_author and not current_user.is_superuser:
            raise InsufficientPermissionsError("只有作者或管理员可以删除帖子")
            
        # 删除帖子
        return await post.delete(db, db_obj=db_post)
    except Exception as e:
        raise handle_error(e) 