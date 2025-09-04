from datetime import datetime, timedelta
from typing import Optional, List
from uuid import uuid4
from sqlalchemy import ForeignKey, String, DateTime, func, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.postgres_base import Base
from app.infrastructure.cache.cache_serializer import register_sqlalchemy_model
from app.infrastructure.utils.common import get_current_time

@register_sqlalchemy_model
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String, index=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=func.now(),
        server_onupdate=func.now(),
    )

    # 关联关系
    password_resets: Mapped[List["PasswordReset"]] = relationship(
        "PasswordReset", back_populates="user", cascade="all, delete-orphan"
    )

class PasswordReset(Base):
    __tablename__ = "password_resets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 关联关系
    user: Mapped["User"] = relationship("User", back_populates="password_resets")

    @property
    def is_expired(self) -> bool:
        """检查令牌是否已过期"""
        current_time = get_current_time()
        return current_time > self.expires_at

    @property
    def is_valid(self) -> bool:
        """检查令牌是否有效（未使用且未过期）"""
        return not self.is_used and not self.is_expired

    @classmethod
    def create(cls, user_id: int, token: str, expires_in_hours: int = 1) -> "PasswordReset":
        """创建新的密码重置令牌"""
        return cls(
            user_id=user_id,
            token=token,
            expires_at=get_current_time() + timedelta(hours=expires_in_hours)
        )