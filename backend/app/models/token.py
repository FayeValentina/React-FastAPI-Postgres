from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Integer
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import timedelta

from app.db.base_class import Base
from app.utils.common import get_current_time

class RefreshToken(Base):
    """刷新令牌模型"""
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid4()))
    token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_valid = Column(Boolean, default=True, nullable=False)
    issued_at = Column(DateTime, default=get_current_time, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    
    # 关系
    user = relationship("User", back_populates="refresh_tokens")
    
    @property
    def is_expired(self) -> bool:
        """检查令牌是否已过期"""
        return get_current_time() > self.expires_at
    
    @classmethod
    def create(cls, token: str, user_id: str, expires_in_days: int = 7, 
               user_agent: str = None, ip_address: str = None) -> "RefreshToken":
        """创建新的刷新令牌"""
        return cls(
            token=token,
            user_id=int(user_id),  # 确保转换为整数
            expires_at=get_current_time() + timedelta(days=expires_in_days),
            user_agent=user_agent,
            ip_address=ip_address
        ) 