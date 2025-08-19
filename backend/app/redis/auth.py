# backend/app/redis/auth.py
from typing import Optional, Set
from datetime import datetime, timedelta
import json

from app.core.redis import RedisBase
from app.core.config import settings

class AuthRedisService(RedisBase):
    """认证相关的Redis服务 - 使用新的连接池架构"""
    
    def __init__(self):
        super().__init__(key_prefix="auth:")
        self.token_prefix = "token:"
        self.user_tokens_prefix = "user_tokens:"
    
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
        
        # 使用管道操作提高性能
        operations = [
            {
                "method": "set",
                "args": [f"{self.token_prefix}{token}", json.dumps(token_data)],
                "kwargs": {"ex": ttl}
            },
            {
                "method": "sadd", 
                "args": [f"{self.user_tokens_prefix}{user_id}", token]
            },
            {
                "method": "expire",
                "args": [f"{self.user_tokens_prefix}{user_id}", ttl]
            }
        ]
        
        results = await self.pipeline_execute(operations)
        return len(results) == 3 and all(results)
    
    async def get_refresh_token_payload(self, token: str) -> Optional[dict]:
        """获取刷新令牌数据"""
        return await self.get_json(f"{self.token_prefix}{token}")
    
    async def revoke_token(self, token: str) -> bool:
        """撤销令牌"""
        # 先获取token数据以便从用户集合中移除
        token_data = await self.get_refresh_token_payload(token)
        if not token_data:
            return False
        
        user_id = token_data.get("user_id")
        
        operations = [
            {
                "method": "delete",
                "args": [f"{self.token_prefix}{token}"]
            }
        ]
        
        if user_id:
            operations.append({
                "method": "srem",
                "args": [f"{self.user_tokens_prefix}{user_id}", token]
            })
        
        results = await self.pipeline_execute(operations)
        return len(results) > 0 and results[0] > 0
    
    async def revoke_all_user_tokens(self, user_id: int) -> bool:
        """撤销用户的所有令牌"""
        # 获取用户所有token
        tokens = await self.smembers(f"{self.user_tokens_prefix}{user_id}")
        if not tokens:
            return True
        
        operations = []
        
        # 删除所有token
        for token in tokens:
            operations.append({
                "method": "delete", 
                "args": [f"{self.token_prefix}{token}"]
            })
        
        # 删除用户token集合
        operations.append({
            "method": "delete",
            "args": [f"{self.user_tokens_prefix}{user_id}"]
        })
        
        results = await self.pipeline_execute(operations)
        return len(results) > 0
    
    async def get_user_token_count(self, user_id: int) -> int:
        """获取用户token数量"""
        try:
            async with self._connection_manager.get_connection() as client:
                count = await client.scard(self._make_key(f"{self.user_tokens_prefix}{user_id}"))
                return count or 0
        except Exception:
            return 0
    
    async def is_token_valid(self, token: str) -> bool:
        """检查token是否有效"""
        token_data = await self.get_refresh_token_payload(token)
        if not token_data:
            return False
        
        # 检查是否过期
        try:
            expires_at = datetime.fromisoformat(token_data["expires_at"])
            return datetime.utcnow() < expires_at
        except (KeyError, ValueError):
            return False
    
    async def cleanup_expired_tokens(self) -> int:
        """清理过期的token（这个方法可以被定时任务调用）"""
        # 获取所有token键
        token_keys = await self.keys(f"{self.token_prefix}*")
        
        expired_count = 0
        for key in token_keys:
            # 检查每个token是否过期
            token = key.replace(self.token_prefix, "")
            if not await self.is_token_valid(token):
                await self.revoke_token(token)
                expired_count += 1
        
        return expired_count