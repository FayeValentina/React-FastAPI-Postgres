from fastapi import APIRouter, Depends
from typing import Annotated
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import (
    LoginRequest,
    UserCreate
)
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.crud.user import user as crud_user
from app.db.base import get_async_session
from app.schemas.token import Token
from app.schemas.user import User
from app.api.v1.dependencies.current_user import get_current_active_user
from app.core.exceptions import InvalidCredentialsError
from app.utils.common import handle_error

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> Token:
    """
    使用 JSON 数据登录获取访问令牌
    
    - **username**: 用户名或邮箱
    - **password**: 密码
    - **remember_me**: 是否记住登录状态（如果为True，则延长令牌有效期）
    """
    try:
        # 先尝试通过用户名查找
        user = await crud_user.get_by_username(db, username=login_data.username)
        if not user:
            # 如果用户名未找到，尝试通过邮箱查找
            user = await crud_user.get_by_email(db, email=login_data.username)
        
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise InvalidCredentialsError()
        
        # 根据remember_me决定令牌过期时间
        if login_data.remember_me:
            access_token_expires = timedelta(days=7)  # 记住登录状态延长到7天
        else:
            access_token_expires = timedelta(minutes=settings.security.ACCESS_TOKEN_EXPIRE_MINUTES)
            
        access_token = create_access_token(
            subject=user.email, expires_delta=access_token_expires
        )
        
        return Token(access_token=access_token, token_type="bearer")
    except Exception as e:
        raise handle_error(e)


@router.post("/register", response_model=User)
async def register(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    """
    注册新用户
    
    - **email**: 电子邮件地址
    - **username**: 用户名（3-50个字符，只能包含字母、数字、下划线和连字符）
    - **password**: 密码
    - **full_name**: 全名（可选）
    """
    try:
        # 使用统一的创建用户逻辑
        return await crud_user.create_with_validation(db, obj_in=user_in)
    except Exception as e:
        raise handle_error(e)


@router.get("/me", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    """
    获取当前登录用户信息
    
    此端点需要用户已通过JWT认证
    """
    return current_user 