from datetime import timedelta
from operator import and_
from typing import Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.models.token import RefreshToken
from app.utils.common import get_current_time


class CRUDRefreshToken:
    async def create(
        self, 
        db: AsyncSession, 
        token: str, 
        user_id: Union[str, int], 
        expires_in_days: int = 7,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> RefreshToken:
        """创建新的刷新令牌"""
        # 确保user_id是整数
        user_id_int = int(user_id) if isinstance(user_id, str) else user_id
        
        refresh_token = RefreshToken.create(
            token=token,
            user_id=user_id_int,  # 直接传递整数
            expires_in_days=expires_in_days,
            user_agent=user_agent,
            ip_address=ip_address
        )
        db.add(refresh_token)
        await db.commit()
        await db.refresh(refresh_token)
        return refresh_token
    
    async def get_by_token(
        self, 
        db: AsyncSession, 
        token: str
    ) -> Optional[RefreshToken]:
        """通过令牌获取刷新令牌记录"""
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token == token,
                RefreshToken.is_valid == True
            )
        )
        return result.scalars().first()
    
    async def revoke(
        self, 
        db: AsyncSession, 
        token: str
    ) -> bool:
        """吊销刷新令牌"""
        result = await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token == token,
                RefreshToken.is_valid == True
            )
            .values(
                is_valid=False,
                revoked_at=get_current_time()
            )
        )
        await db.commit()
        return result.rowcount > 0
    
    async def revoke_all_for_user(
        self, 
        db: AsyncSession, 
        user_id: Union[str, int]
    ) -> int:
        """吊销用户的所有刷新令牌"""
        # 确保user_id是整数
        user_id_int = int(user_id) if isinstance(user_id, str) else user_id
        
        result = await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id_int,
                RefreshToken.is_valid == True
            )
            .values(
                is_valid=False,
                revoked_at=get_current_time()
            )
        )
        await db.commit()
        return result.rowcount
    
    async def cleanup_expired(self, db: AsyncSession, days_old: int = 7) -> int:
        """
        删除创建时间早于指定天数且已失效的刷新令牌。
        
        删除条件：
        1. 创建时间早于 days_old 天前
        2. is_valid 为 False (已被撤销或已过期)
        """
        # 计算时间阈值
        creation_date_threshold = get_current_time() - timedelta(days=days_old)
        current_time = get_current_time()
        
        # 定义失效条件 (is_valid == False)
        # 条件1: 令牌已被撤销 (revoked_at 不为 NULL)
        # 条件2: 令牌已过期 (expires_at < 当前时间)
        is_invalid_condition = (
            (RefreshToken.revoked_at.isnot(None)) | 
            (RefreshToken.expires_at < current_time)
        )

        # 定义旧记录条件（使用 issued_at 字段）
        is_old_condition = RefreshToken.issued_at < creation_date_threshold

        # 执行删除：删除既旧又失效的令牌
        statement = delete(RefreshToken).where(
            and_(
                is_old_condition,
                is_invalid_condition
            )
        )
        
        result = await db.execute(statement)
        return result.rowcount


crud_refresh_token = CRUDRefreshToken() 