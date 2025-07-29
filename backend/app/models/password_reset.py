from datetime import datetime, timedelta, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4

from app.db.base_class import Base
from app.utils.common import get_current_time

if TYPE_CHECKING:
    from .user import User


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # 关联关系
    user: Mapped["User"] = relationship("User", back_populates="password_resets")

    @property
    def is_expired(self) -> bool:
        """检查令牌是否已过期"""
        current_time = get_current_time()
        expires_at = self.expires_at
        
        # 如果 expires_at 是 timezone-naive，转换为 UTC
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        return current_time > expires_at

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