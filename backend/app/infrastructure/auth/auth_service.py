from typing import Optional, Set
from datetime import timedelta
import json
from app.infrastructure.redis.keyspace import redis_keys
from app.infrastructure.redis.redis_base import RedisBase
from app.core.config import settings
from app.infrastructure.utils.common import get_current_time
import logging

logger = logging.getLogger(__name__)

class AuthRedisService(RedisBase):
    """认证相关的Redis服务 - 使用新的连接池架构"""
    
    def __init__(self):
        super().__init__(key_prefix="auth:")
    
    async def store_refresh_token(
        self,
        token: str,
        user_id: int,
        expires_in_days: int = None
    ) -> bool:
        """存储刷新令牌 (使用新的 pipeline 上下文管理器)"""
        if expires_in_days is None:
            expires_in_days = settings.security.REFRESH_TOKEN_EXPIRE_DAYS
        
        ttl = expires_in_days * 24 * 3600  # 转换为秒
        
        now = get_current_time()
        token_data = {
            "user_id": user_id,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=expires_in_days)).isoformat()
        }
        
        token_key = redis_keys.auth.token(token)
        user_tokens_key = redis_keys.auth.user_tokens(user_id)

        try:
            async with self.pipeline() as pipe:
                # 1. 存储令牌本身的数据
                pipe.set(self._make_key(token_key), json.dumps(token_data), ex=ttl)
                # 2. 将令牌添加到用户的令牌集合中
                pipe.sadd(self._make_key(user_tokens_key), token)
                # 3. 为用户的令牌集合续期，防止内存泄漏
                pipe.expire(self._make_key(user_tokens_key), ttl)
                
                results = await pipe.execute()
            
            # 检查所有操作是否都成功
            # set -> True, sadd -> 1, expire -> True
            return all(results)
        except Exception as e:
            logger.error(f"存储刷新令牌失败 (user_id={user_id}): {e}")
            return False
    
    async def get_refresh_token_payload(self, token: str) -> Optional[dict]:
        """获取刷新令牌数据"""
        return await self.get_json(redis_keys.auth.token(token))
    
    async def revoke_token(self, token: str) -> bool:
        """撤销令牌 (使用新的 pipeline 上下文管理器)"""
        # 先获取token数据以便从用户集合中移除
        token_data = await self.get_refresh_token_payload(token)
        if not token_data:
            return False
        
        user_id = token_data.get("user_id")
        token_key = redis_keys.auth.token(token)

        try:
            async with self.pipeline() as pipe:
                # 1. 删除令牌本身
                pipe.delete(self._make_key(token_key))
                # 2. 如果有关联的用户，从用户的令牌集合中移除
                if user_id:
                    user_tokens_key = redis_keys.auth.user_tokens(user_id)
                    pipe.srem(self._make_key(user_tokens_key), token)
                
                results = await pipe.execute()
            
            # 只要删除令牌的操作成功即可 (返回删除的键数量 > 0)
            return results[0] > 0
        except Exception as e:
            logger.error(f"撤销令牌失败 (token={token}): {e}")
            return False
    
    async def revoke_all_user_tokens(self, user_id: int) -> bool:
        """撤销用户的所有令牌 (使用新的 pipeline 上下文管理器)"""
        user_tokens_key = redis_keys.auth.user_tokens(user_id)
        
        # 获取用户所有token（decode_responses=True 下为 str 集合）
        tokens_set = await self.smembers(user_tokens_key)
        if not tokens_set:
            return True
        tokens = [str(t) for t in tokens_set]

        try:
            async with self.pipeline() as pipe:
                # 1. 准备删除所有单独的令牌键
                token_keys_to_delete = [self._make_key(redis_keys.auth.token(token)) for token in tokens]
                if token_keys_to_delete:
                    pipe.delete(*token_keys_to_delete)
                
                # 2. 删除用户的令牌集合本身
                pipe.delete(self._make_key(user_tokens_key))
                
                await pipe.execute()
            
            return True
        except Exception as e:
            logger.error(f"撤销用户 {user_id} 的所有令牌失败: {e}")
            return False
    
    async def get_user_token_count(self, user_id: int) -> int:
        """获取用户token数量"""
        try:
            count = await self.scard(redis_keys.auth.user_tokens(user_id))
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
            from datetime import datetime as _dt
            expires_at = _dt.fromisoformat(token_data["expires_at"])
            return get_current_time() < expires_at
        except (KeyError, ValueError):
            return False
    
    async def cleanup_expired_tokens(self) -> int:
        """清理过期的token（这个方法可以被定时任务调用）"""
        # 获取所有token键

        token_keys = await self.scan_keys(f"{redis_keys.auth.TOKEN_PREFIX}*")
        
        expired_count = 0
        for key in token_keys:
            # 检查每个token是否过期
            token = key.replace(redis_keys.auth.TOKEN_PREFIX, "")
            if not await self.is_token_valid(token):
                await self.revoke_token(token)
                expired_count += 1
        
        return expired_count


# 全局实例和依赖提供函数
auth_redis_service = AuthRedisService()


def get_auth_redis_service() -> AuthRedisService:
    """FastAPI 依赖项：获取认证相关的 Redis 服务"""
    return auth_redis_service
