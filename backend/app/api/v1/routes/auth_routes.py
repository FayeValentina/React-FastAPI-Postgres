from fastapi import APIRouter, Depends, Request
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import (
    LoginRequest,
    UserCreate
)
from app.core.config import settings
from app.core.security import verify_password, create_token_pair, verify_token
from app.crud.user import user as crud_user
from app.crud.token import refresh_token as crud_refresh_token
from app.db.base import get_async_session
from app.schemas.token import Token, RefreshTokenRequest, TokenRevocationRequest
from app.schemas.user import User
from app.api.v1.dependencies.current_user import get_current_active_user
from app.core.exceptions import InvalidCredentialsError, InvalidRefreshTokenError
from app.utils.common import handle_error

router = APIRouter(prefix="/auth", tags=["auth"])


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
        await crud_refresh_token.revoke_all_for_user(db, user_id=user.id)
        
        # 将刷新令牌存储到数据库
        await crud_refresh_token.create(
            db=db,
            token=refresh_token,
            user_id=user.id,
            expires_in_days=settings.security.REFRESH_TOKEN_EXPIRE_DAYS,  # 使用配置的过期天数
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None
        )
        
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
        
        # 检查刷新令牌是否在数据库中存在且有效
        token_record = await crud_refresh_token.get_by_token(db, token=refresh_data.refresh_token)
        if not token_record or not token_record.is_valid or token_record.is_expired:
            raise InvalidRefreshTokenError()
        
        # 提取用户标识
        subject = payload.get("sub")
        if not subject:
            raise InvalidRefreshTokenError("令牌缺少用户标识")
        
        # 吊销当前使用的刷新令牌
        await crud_refresh_token.revoke(db, token=refresh_data.refresh_token)
        
        # 创建新的令牌对（旧刷新令牌已被吊销，确保用户只有一个有效的刷新令牌）
        access_token, new_refresh_token, expires_at = create_token_pair(subject=subject)
        
        # 存储新的刷新令牌
        await crud_refresh_token.create(
            db=db,
            token=new_refresh_token,
            user_id=token_record.user_id,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None
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
        
        # 吊销指定的刷新令牌
        await crud_refresh_token.revoke(db, token=revocation_data.token)
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
        # 吊销用户的所有刷新令牌
        await crud_refresh_token.revoke_all_for_user(db, user_id=current_user.id)
    except Exception as e:
        raise handle_error(e)


@router.post("/register", response_model=User, status_code=201)
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