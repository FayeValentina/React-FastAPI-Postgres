from fastapi import APIRouter, Depends, Request
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from app.modules.auth.schemas import (
    LoginRequest,
    UserCreate,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordResetResponse,
    User,
    Token,
    RefreshTokenRequest,
    TokenRevocationRequest,
)
from app.infrastructure.database.postgres_base import get_async_session
from app.api.dependencies import get_current_active_user
from app.infrastructure.utils.common import handle_error
from app.infrastructure.cache.cache_decorators import cache, invalidate
from app.constant.cache_tags import CacheTags
from app.infrastructure.auth.auth_service import (
    AuthRedisService,
    get_auth_redis_service,
)
from app.modules.auth.service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    auth_redis: AuthRedisService = Depends(get_auth_redis_service),
) -> Token:
    """
    使用 JSON 数据登录获取访问令牌和刷新令牌
    
    - **username**: 用户名或邮箱
    - **password**: 密码
    - **remember_me**: 是否记住登录状态（如果为True，则延长令牌有效期）
    """
    try:
        return await auth_service.login(db=db, login_data=login_data, auth_redis=auth_redis)
    except Exception as e:
        raise handle_error(e)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    refresh_data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    auth_redis: AuthRedisService = Depends(get_auth_redis_service),
) -> Token:
    """
    使用刷新令牌获取新的访问令牌
    
    - **refresh_token**: 刷新令牌
    
    安全说明:
    本端点采用令牌轮换策略 - 每次使用刷新令牌时，旧令牌会被吊销并颁发新令牌。
    这确保用户在任何时候只有一个有效的刷新令牌，提高系统安全性。
    """
    try:
        return await auth_service.refresh_token(db=db, refresh_data=refresh_data, auth_redis=auth_redis)
    except Exception as e:
        raise handle_error(e)


@router.post("/revoke", status_code=204)
async def revoke_token(
    revocation_data: TokenRevocationRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    auth_redis: AuthRedisService = Depends(get_auth_redis_service)
) -> None:
    """
    吊销刷新令牌
    
    - **token**: 要吊销的令牌
    - **token_type**: 令牌类型，默认为"refresh_token"
    """
    try:
        await auth_service.revoke_token(revocation_data=revocation_data, auth_redis=auth_redis)
    except Exception as e:
        raise handle_error(e)


@router.post("/logout", status_code=204)
async def logout(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    auth_redis: AuthRedisService = Depends(get_auth_redis_service)
) -> None:
    """
    登出并吊销用户的所有刷新令牌
    
    此端点需要用户已通过JWT认证
    """
    try:
        await auth_service.logout(current_user=current_user, auth_redis=auth_redis)
    except Exception as e:
        raise handle_error(e)


@router.post("/register", response_model=User, status_code=201)
@invalidate([CacheTags.USER_LIST])
async def register(
    request: Request,
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
        return await auth_service.register_user(db=db, user_in=user_in)
    except Exception as e:
        raise handle_error(e)


@router.get("/me", response_model=User)
@cache([CacheTags.USER_ME], exclude_params=["request", "current_user"])
async def read_users_me(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    """
    获取当前登录用户信息
    
    此端点需要用户已通过JWT认证
    """
    return await auth_service.get_me(current_user)


@router.post("/forgot-password", response_model=PasswordResetResponse)
async def forgot_password(
    request_data: PasswordResetRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> PasswordResetResponse:
    """
    发送密码重置邮件
    
    - **email**: 用户邮箱地址
    """
    try:
        return await auth_service.forgot_password(db=db, request_data=request_data)
    except Exception as e:
        raise handle_error(e)


@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password(
    reset_data: PasswordResetConfirm,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    auth_redis: AuthRedisService = Depends(get_auth_redis_service),
) -> PasswordResetResponse:
    """
    重置密码
    
    - **token**: 密码重置令牌
    - **new_password**: 新密码
    """
    try:
        return await auth_service.reset_password(db=db, reset_data=reset_data, auth_redis=auth_redis)
    except Exception as e:
        raise handle_error(e)


@router.post("/verify-reset-token", response_model=PasswordResetResponse)
async def verify_reset_token(
    token: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> PasswordResetResponse:
    """
    验证密码重置令牌是否有效
    
    - **token**: 密码重置令牌
    """
    try:
        return await auth_service.verify_reset_token(db=db, token=token)
    except Exception as e:
        raise handle_error(e)
