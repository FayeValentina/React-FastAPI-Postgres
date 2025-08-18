# backend/app/services/auth_redis.py
from typing import Optional, Set
from datetime import datetime, timedelta
from app.core.redis_core import RedisBase
from app.core.config import settings
import json

class AuthRedisService(RedisBase):
    """认证相关的Redis服务"""
    
    def __init__(self):
        super().__init__()
        self.token_prefix = "auth:token:"
        self.user_tokens_prefix = "auth:user_tokens:"
    
    async def store_refresh_token(
        self,
        token: str,
        user_id: int,
        expires_in_days: int = None
    ) -> bool:
        """存储刷新令牌"""
        if expires_in_days is None:
            expires_in_days = settings.security.REFRESH_TOKEN_EXPIRE_DAYS
        
        ttl = expires_in_days * 24 * 3600  # 转换为秒
        
        token_data = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=expires_in_days)).isoformat()
        }
        
        client = await self.get_client()
        
        # 使用pipeline提高性能
        pipe = client.pipeline()
        # 存储token数据
        pipe.set(f"{self.token_prefix}{token}", json.dumps(token_data), ex=ttl)
        # 添加到用户token集合
        pipe.sadd(f"{self.user_tokens_prefix}{user_id}", token)
        pipe.expire(f"{self.user_tokens_prefix}{user_id}", ttl)
        
        try:
            await pipe.execute()
            return True
        except Exception:
            return False
    
    async def get_refresh_token_payload(self, token: str) -> Optional[dict]:
        """获取刷新令牌数据"""
        return await self.get_json(f"{self.token_prefix}{token}")
    
    async def revoke_token(self, token: str) -> bool:
        """撤销令牌"""
        client = await self.get_client()
        
        # 先获取token数据以便从用户集合中移除
        token_data = await self.get_refresh_token_payload(token)
        if not token_data:
            return False
        
        user_id = token_data.get("user_id")
        
        pipe = client.pipeline()
        pipe.delete(f"{self.token_prefix}{token}")
        if user_id:
            pipe.srem(f"{self.user_tokens_prefix}{user_id}", token)
        
        try:
            await pipe.execute()
            return True
        except Exception:
            return False
    
    async def revoke_all_user_tokens(self, user_id: int) -> bool:
        """撤销用户的所有令牌"""
        client = await self.get_client()
        
        # 获取用户所有token
        try:
            tokens = await client.smembers(f"{self.user_tokens_prefix}{user_id}")
            if not tokens:
                return True
            
            pipe = client.pipeline()
            # 删除所有token
            for token in tokens:
                pipe.delete(f"{self.token_prefix}{token}")
            # 删除用户token集合
            pipe.delete(f"{self.user_tokens_prefix}{user_id}")
            
            await pipe.execute()
            return True
        except Exception:
            return False