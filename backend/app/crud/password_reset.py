from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from datetime import timedelta
from uuid import uuid4

from app.models.password_reset import PasswordReset
from app.utils.common import get_current_time


class CRUDPasswordReset:
    async def create(
        self, 
        db: AsyncSession, 
        user_id: int,
        expires_in_hours: int = 1
    ) -> PasswordReset:
        """创建新的密码重置令牌"""
        # 先将该用户的所有未使用令牌标记为已使用（确保一次只有一个有效令牌）
        await self.invalidate_user_tokens(db, user_id)
        
        # 生成新令牌
        token = str(uuid4())
        reset_token = PasswordReset.create(
            user_id=user_id,
            token=token,
            expires_in_hours=expires_in_hours
        )
        
        db.add(reset_token)
        await db.commit()
        await db.refresh(reset_token)
        return reset_token
    
    async def get_by_token(
        self, 
        db: AsyncSession, 
        token: str
    ) -> Optional[PasswordReset]:
        """通过令牌获取密码重置记录"""
        result = await db.execute(
            select(PasswordReset).where(PasswordReset.token == token)
        )
        return result.scalar_one_or_none()
    
    async def use_token(
        self, 
        db: AsyncSession, 
        token: str
    ) -> bool:
        """使用密码重置令牌"""
        result = await db.execute(
            update(PasswordReset)
            .where(PasswordReset.token == token)
            .values(
                is_used=True,
                used_at=get_current_time()
            )
        )
        await db.commit()
        return result.rowcount > 0
    
    async def invalidate_user_tokens(
        self, 
        db: AsyncSession, 
        user_id: int
    ) -> int:
        """使用户的所有未使用令牌失效"""
        result = await db.execute(
            update(PasswordReset)
            .where(
                PasswordReset.user_id == user_id,
                PasswordReset.is_used == False
            )
            .values(
                is_used=True,
                used_at=get_current_time()
            )
        )
        await db.commit()
        return result.rowcount
    
    async def cleanup_expired(
        self, 
        db: AsyncSession
    ) -> int:
        """清理过期的密码重置令牌"""
        current_time = get_current_time()
        result = await db.execute(
            delete(PasswordReset)
            .where(PasswordReset.is_valid == False)
        )
        await db.commit()
        return result.rowcount


password_reset = CRUDPasswordReset()