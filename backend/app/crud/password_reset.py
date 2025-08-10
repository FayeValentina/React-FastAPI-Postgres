from datetime import timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
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
    
    async def cleanup_expired(self, db: AsyncSession, days_old: int = 7) -> int:
        """
        删除创建时间早于指定天数且已失效的密码重置令牌。
        
        删除条件：
        1. 创建时间早于 days_old 天前
        2. is_valid 为 False (已使用或已过期)
        """
        # 计算时间阈值
        creation_date_threshold = get_current_time() - timedelta(days=days_old)
        current_time = get_current_time()
        
        # 定义失效条件 (is_valid == False)
        # 条件1: 令牌已使用 (is_used == True)
        # 条件2: 令牌已过期 (expires_at < 当前时间)
        is_invalid_condition = (
            (PasswordReset.is_used == True) | 
            (PasswordReset.expires_at < current_time)
        )

        # 定义旧记录条件
        is_old_condition = PasswordReset.created_at < creation_date_threshold

        # 执行删除：删除既旧又失效的令牌
        statement = delete(PasswordReset).where(
            and_(
                is_old_condition,
                is_invalid_condition
            )
        )
        
        result = await db.execute(statement)
        return result.rowcount


crud_password_reset = CRUDPasswordReset()