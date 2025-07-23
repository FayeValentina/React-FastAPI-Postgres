from typing import Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import timedelta

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
    
    async def cleanup_expired(
        self, 
        db: AsyncSession
    ) -> int:
        """清理过期的刷新令牌"""
        current_time = get_current_time()
        result = await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.expires_at < current_time,
                RefreshToken.is_valid == True
            )
            .values(
                is_valid=False,
                revoked_at=current_time
            )
        )
        await db.commit()
        return result.rowcount


refresh_token = CRUDRefreshToken() 