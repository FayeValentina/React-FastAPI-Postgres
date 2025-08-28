from fastapi import APIRouter, Depends, Request
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from app.schemas import (
    LoginRequest,
    UserCreate
)
from app.schemas.password_reset import (
    PasswordResetRequest, 
    PasswordResetConfirm, 
    PasswordResetResponse
)
from app.core.config import settings
from app.core.security import verify_password, create_token_pair, verify_token, get_password_hash
from app.crud.user import crud_user
from app.crud.password_reset import crud_password_reset
from app.core.redis_manager import redis_services
from app.services.email_service import email_service
from app.db.base import get_async_session
from app.schemas.token import Token, RefreshTokenRequest, TokenRevocationRequest
from app.schemas.user import User
from app.dependencies.current_user import get_current_active_user
from app.core.exceptions import InvalidCredentialsError, InvalidRefreshTokenError
from app.utils import handle_error, cache_invalidate, cache_user_data

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> Token:
    """
    使用 JSON 数据登录获取访问令牌和刷新令牌
    
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
        
        # 创建令牌对
        access_token, refresh_token, expires_at = create_token_pair(
            subject=str(user.id), 
            remember_me=login_data.remember_me
        )
        
        # 在创建新令牌前，先吊销该用户的所有现有刷新令牌
        revoke_success = await redis_services.auth.revoke_all_user_tokens(user.id)
        
        # 将刷新令牌存储到Redis而不是数据库
        store_success = await redis_services.auth.store_refresh_token(
            token=refresh_token,
            user_id=user.id,
            expires_in_days=settings.security.REFRESH_TOKEN_EXPIRE_DAYS
        )
        
        # 如果Redis存储失败，应该提供警告但不阻止登录
        if not store_success:
            logger.warning(f"刷新令牌存储到Redis失败，用户ID: {user.id}")
            # 可以考虑降级方案或通知用户
        
        return Token(
            access_token=access_token, 
            refresh_token=refresh_token,
            token_type="bearer",
            expires_at=expires_at
        )
    except Exception as e:
        raise handle_error(e)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    refresh_data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> Token:
    """
    使用刷新令牌获取新的访问令牌
    
    - **refresh_token**: 刷新令牌
    
    安全说明:
    本端点采用令牌轮换策略 - 每次使用刷新令牌时，旧令牌会被吊销并颁发新令牌。
    这确保用户在任何时候只有一个有效的刷新令牌，提高系统安全性。
    """
    try:
        # 验证刷新令牌的有效性
        is_valid, payload, error_type = verify_token(refresh_data.refresh_token)
        if not is_valid:
            if error_type == "expired":
                raise InvalidRefreshTokenError("刷新令牌已过期")
            else:
                raise InvalidRefreshTokenError()
        
        # 检查令牌类型
        if payload.get("type") != "refresh_token":
            raise InvalidRefreshTokenError("无效的令牌类型")
        
        # 从Redis检查刷新令牌是否存在
        token_data = await redis_services.auth.get_refresh_token_payload(refresh_data.refresh_token)
        if not token_data:
            raise InvalidRefreshTokenError()
        
        # 提取用户标识
        user_id = token_data.get("user_id")
        if not user_id:
            raise InvalidRefreshTokenError("令牌缺少用户标识")
        
        # 吊销当前使用的刷新令牌
        await redis_services.auth.revoke_token(refresh_data.refresh_token)
        
        # 创建新的令牌对
        access_token, new_refresh_token, expires_at = create_token_pair(subject=str(user_id))
        
        # 存储新的刷新令牌到Redis
        await redis_services.auth.store_refresh_token(
            token=new_refresh_token,
            user_id=user_id
        )
        
        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_at=expires_at
        )
    except Exception as e:
        raise handle_error(e)


@router.post("/revoke", status_code=204)
async def revoke_token(
    revocation_data: TokenRevocationRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> None:
    """
    吊销刷新令牌
    
    - **token**: 要吊销的令牌
    - **token_type**: 令牌类型，默认为"refresh_token"
    """
    try:
        if revocation_data.token_type != "refresh_token":
            return
        
        # 吊销指定的刷新令牌（使用Redis服务）
        await redis_services.auth.revoke_token(revocation_data.token)
    except Exception as e:
        raise handle_error(e)


@router.post("/logout", status_code=204)
async def logout(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> None:
    """
    登出并吊销用户的所有刷新令牌
    
    此端点需要用户已通过JWT认证
    """
    try:
        # 吊销用户的所有刷新令牌（从Redis）
        await redis_services.auth.revoke_all_user_tokens(current_user.id)
    except Exception as e:
        raise handle_error(e)


@router.post("/register", response_model=User, status_code=201)
@cache_invalidate("user_list")
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
        # 使用统一的创建用户逻辑
        return await crud_user.create_with_validation(db, obj_in=user_in)
    except Exception as e:
        raise handle_error(e)


@router.get("/me", response_model=User)
@cache_user_data("user_me")
async def read_users_me(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    """
    获取当前登录用户信息
    
    此端点需要用户已通过JWT认证
    """
    return current_user


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
        # 查找用户
        user = await crud_user.get_by_email(db, email=request_data.email)
        
        # 即使用户不存在，也返回成功消息（安全考虑，不暴露用户是否存在）
        if not user:
            return PasswordResetResponse(
                message="如果该邮箱地址存在于我们的系统中，您将收到密码重置邮件"
            )
        
        # 创建密码重置令牌
        reset_token = await crud_password_reset.create(db, user_id=user.id)
        
        # 发送邮件
        email_sent = await email_service.send_password_reset_email(
            to_email=user.email,
            reset_token=reset_token.token,
            user_name=user.full_name or user.username
        )
        
        if not email_sent:
            raise ValueError("邮件发送失败，请稍后重试")
        
        return PasswordResetResponse(
            message="如果该邮箱地址存在于我们的系统中，您将收到密码重置邮件"
        )
        
    except Exception as e:
        raise handle_error(e)


@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password(
    reset_data: PasswordResetConfirm,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> PasswordResetResponse:
    """
    重置密码
    
    - **token**: 密码重置令牌
    - **new_password**: 新密码
    """
    try:
        # 验证令牌
        reset_token = await crud_password_reset.get_by_token(db, token=reset_data.token)
        
        if not reset_token or not reset_token.is_valid:
            raise ValueError("无效或已过期的重置令牌")
        
        # 获取用户
        user = await crud_user.get(db, id=reset_token.user_id)
        if not user:
            raise ValueError("用户不存在")
        
        # 更新密码
        hashed_password = get_password_hash(reset_data.new_password)
        user.hashed_password = hashed_password
        
        # 将修改后的用户对象添加到会话中（确保 SQLAlchemy 知道对象已被修改）
        db.add(user)
        
        # 标记令牌为已使用
        await crud_password_reset.use_token(db, token=reset_data.token)
        
        # 吊销用户的所有刷新令牌（强制重新登录）- 使用Redis服务
        await redis_services.auth.revoke_all_user_tokens(user.id)
        
        await db.commit()
        await db.refresh(user)
        
        return PasswordResetResponse(
            message="密码重置成功，请使用新密码登录"
        )
        
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
        reset_token = await crud_password_reset.get_by_token(db, token=token)
        
        if not reset_token or not reset_token.is_valid:
            return PasswordResetResponse(
                message="令牌无效或已过期",
                success=False
            )
        
        return PasswordResetResponse(
            message="令牌有效"
        )
        
    except Exception as e:
        raise handle_error(e)