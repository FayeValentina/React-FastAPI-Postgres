from typing import List, Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, desc, asc

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
    UserResponse,
    UserUpdate,
)
from app.modules.auth.repository import crud_user, crud_password_reset
from app.core.config import settings
from app.core.security import verify_password, create_token_pair, verify_token, get_password_hash
from app.infrastructure.external.email_service import email_service
from app.core.exceptions import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserNotFoundError,
    InsufficientPermissionsError,
)
from app.infrastructure.auth.auth_service import AuthRedisService

logger = logging.getLogger(__name__)


class AuthService:
    """Business logic for authentication and user management."""

    async def login(
        self,
        db: AsyncSession,
        login_data: LoginRequest,
        auth_redis: AuthRedisService,
    ) -> Token:
        user = await crud_user.get_by_username(db, username=login_data.username)
        if not user:
            user = await crud_user.get_by_email(db, email=login_data.username)

        if not user or not verify_password(login_data.password, user.hashed_password):
            raise InvalidCredentialsError()

        access_token, refresh_token, expires_at = create_token_pair(
            subject=str(user.id),
            remember_me=login_data.remember_me,
        )

        await auth_redis.revoke_all_user_tokens(user.id)
        store_success = await auth_redis.store_refresh_token(
            token=refresh_token,
            user_id=user.id,
            expires_in_days=settings.security.REFRESH_TOKEN_EXPIRE_DAYS,
        )
        if not store_success:
            logger.warning("刷新令牌存储到Redis失败，用户ID: %s", user.id)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_at=expires_at,
        )

    async def refresh_token(
        self,
        db: AsyncSession,
        refresh_data: RefreshTokenRequest,
        auth_redis: AuthRedisService,
    ) -> Token:
        is_valid, payload, error_type = verify_token(refresh_data.refresh_token)
        if not is_valid:
            if error_type == "expired":
                raise InvalidRefreshTokenError("刷新令牌已过期")
            raise InvalidRefreshTokenError()

        if payload.get("type") != "refresh_token":
            raise InvalidRefreshTokenError("无效的令牌类型")

        token_data = await auth_redis.get_refresh_token_payload(refresh_data.refresh_token)
        if not token_data:
            raise InvalidRefreshTokenError()

        user_id = token_data.get("user_id")
        if not user_id:
            raise InvalidRefreshTokenError("令牌缺少用户标识")

        await auth_redis.revoke_token(refresh_data.refresh_token)
        access_token, new_refresh_token, expires_at = create_token_pair(subject=str(user_id))
        await auth_redis.store_refresh_token(token=new_refresh_token, user_id=user_id)
        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_at=expires_at,
        )

    async def revoke_token(
        self,
        revocation_data: TokenRevocationRequest,
        auth_redis: AuthRedisService,
    ) -> None:
        if revocation_data.token_type != "refresh_token":
            return
        await auth_redis.revoke_token(revocation_data.token)

    async def logout(
        self,
        current_user: User,
        auth_redis: AuthRedisService,
    ) -> None:
        await auth_redis.revoke_all_user_tokens(current_user.id)

    async def register_user(
        self,
        db: AsyncSession,
        user_in: UserCreate,
    ) -> User:
        return await crud_user.create_with_validation(db, obj_in=user_in)

    async def get_me(self, current_user: User) -> User:
        return current_user

    async def forgot_password(
        self,
        db: AsyncSession,
        request_data: PasswordResetRequest,
    ) -> PasswordResetResponse:
        user = await crud_user.get_by_email(db, email=request_data.email)
        if not user:
            return PasswordResetResponse(
                message="如果该邮箱地址存在于我们的系统中，您将收到密码重置邮件",
            )

        reset_token = await crud_password_reset.create(db, user_id=user.id)
        email_sent = await email_service.send_password_reset_email(
            to_email=user.email,
            reset_token=reset_token.token,
            user_name=user.full_name or user.username,
        )
        if not email_sent:
            raise ValueError("邮件发送失败，请稍后重试")
        return PasswordResetResponse(
            message="如果该邮箱地址存在于我们的系统中，您将收到密码重置邮件",
        )

    async def reset_password(
        self,
        db: AsyncSession,
        reset_data: PasswordResetConfirm,
        auth_redis: AuthRedisService,
    ) -> PasswordResetResponse:
        reset_token = await crud_password_reset.get_by_token(db, token=reset_data.token)
        if not reset_token or not reset_token.is_valid:
            raise ValueError("无效或已过期的重置令牌")

        user = await crud_user.get(db, id=reset_token.user_id)
        if not user:
            raise ValueError("用户不存在")

        hashed_password = get_password_hash(reset_data.new_password)
        user.hashed_password = hashed_password
        db.add(user)
        await crud_password_reset.use_token(db, token=reset_data.token)
        await auth_redis.revoke_all_user_tokens(user.id)
        await db.commit()
        await db.refresh(user)
        return PasswordResetResponse(message="密码重置成功，请使用新密码登录")

    async def verify_reset_token(
        self,
        db: AsyncSession,
        token: str,
    ) -> PasswordResetResponse:
        reset_token = await crud_password_reset.get_by_token(db, token=token)
        if not reset_token or not reset_token.is_valid:
            return PasswordResetResponse(
                message="令牌无效或已过期",
                success=False,
            )
        return PasswordResetResponse(message="令牌有效")

    # ----------------------- User management methods -----------------------
    async def create_user(
        self,
        db: AsyncSession,
        user_data: UserCreate,
    ) -> UserResponse:
        return await crud_user.create_with_validation(db, obj_in=user_data)

    async def update_user(
        self,
        db: AsyncSession,
        user_id: int,
        user_update: UserUpdate,
        current_user: User,
    ) -> UserResponse:
        if current_user.id != user_id and not current_user.is_superuser:
            raise InsufficientPermissionsError("没有足够权限更新其他用户")
        if user_update.is_superuser is not None and not current_user.is_superuser:
            raise InsufficientPermissionsError("只有超级管理员才能修改 is_superuser 字段")
        db_user = await crud_user.get(db, id=user_id)
        if not db_user:
            raise UserNotFoundError()
        return await crud_user.update(db, db_obj=db_user, obj_in=user_update)

    async def get_users(
        self,
        db: AsyncSession,
        current_user: User,
        name: Optional[str] = None,
        email: Optional[str] = None,
        age: Optional[int] = None,
        is_active: Optional[bool] = None,
        sort_by: Optional[List[str]] = None,
    ) -> List[UserResponse]:
        query = select(User)
        filters = []
        if name:
            filters.append(or_(User.username.ilike(f"%{name}%"), User.full_name.ilike(f"%{name}%")))
        if email:
            filters.append(User.email.ilike(f"%{email}%"))
        if age is not None:
            filters.append(User.age == age)
        if is_active is not None:
            filters.append(User.is_active == is_active)
        else:
            if not current_user.is_superuser:
                filters.append(User.is_active == True)
        if filters:
            query = query.where(and_(*filters))
        sort_fields = sort_by or ["created_at"]
        for sort_field in sort_fields:
            if sort_field.startswith('-'):
                field_name = sort_field[1:]
                if hasattr(User, field_name):
                    query = query.order_by(desc(getattr(User, field_name)))
            else:
                if hasattr(User, sort_field):
                    query = query.order_by(asc(getattr(User, sort_field)))
        result = await db.execute(query)
        return result.scalars().all()

    async def get_user(
        self,
        db: AsyncSession,
        user_id: int,
        current_user: User,
    ) -> UserResponse:
        if current_user.id == user_id:
            return current_user
        if not current_user.is_superuser:
            raise InsufficientPermissionsError("没有足够权限查看其他用户详情")
        db_user = await crud_user.get(db, id=user_id)
        if not db_user:
            raise UserNotFoundError()
        return db_user

    async def delete_user(
        self,
        db: AsyncSession,
        user_id: int,
        current_user: User,
    ) -> UserResponse:
        db_user = await crud_user.get(db, id=user_id)
        if not db_user:
            raise UserNotFoundError()
        if current_user.id == user_id:
            raise ValueError("不能删除自己的账户")
        return await crud_user.delete(db, id=user_id)


auth_service = AuthService()

