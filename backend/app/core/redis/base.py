# backend/app/core/redis/base.py (最终确认版)

"""
Redis基础操作类
提供通用的Redis操作方法，使用连接池和上下文管理器
"""
import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import timedelta
from contextlib import asynccontextmanager

# 假设连接管理器在同级目录的 pool.py 文件中
from .pool import redis_connection_manager

logger = logging.getLogger(__name__)



class RedisBase:
    """Redis服务基类，使用共享连接池和上下文管理器"""

    def __init__(self, key_prefix: str = ""):
        """
        初始化Redis基类
        
        Args:
            key_prefix: 键前缀，用于命名空间隔离
        """
        self.key_prefix = key_prefix
        self._connection_manager = redis_connection_manager

    def _make_key(self, key: str) -> str:
        """生成带前缀的键名"""
        if self.key_prefix:
            return f"{self.key_prefix}{key}"
        return key

    async def ensure_connection(self) -> None:
        """确保连接池已初始化"""
        if self._connection_manager._pool is None:
            await self._connection_manager.initialize()

    # ========== 字符串操作 ==========
    
    async def set(self, key: str, value: Union[str, bytes], ttl: Optional[int] = None) -> bool:
        """设置字符串值"""
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.set(self._make_key(key), value, ex=ttl)
                return result is True
        except Exception as e:
            logger.error(f"Redis set error (key={key}): {e}")
            return False

    async def get(self, key: str) -> Optional[Union[str, bytes]]:
        """获取字符串或字节值"""
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.get(self._make_key(key))
                return result
        except Exception as e:
            logger.error(f"Redis get error (key={key}): {e}")
            return None

    async def delete(self, *keys: str) -> int:
        """删除键，返回删除数量"""
        if not keys:
            return 0
        try:
            async with self._connection_manager.get_connection() as client:
                prefixed_keys = [self._make_key(key) for key in keys]
                result = await client.delete(*prefixed_keys)
                return result
        except Exception as e:
            logger.error(f"Redis delete error (keys={keys}): {e}")
            return 0

    async def exists(self, *keys: str) -> int:
        """检查键是否存在，返回存在的数量"""
        if not keys:
            return 0
        try:
            async with self._connection_manager.get_connection() as client:
                prefixed_keys = [self._make_key(key) for key in keys]
                result = await client.exists(*prefixed_keys)
                return result
        except Exception as e:
            logger.error(f"Redis exists error (keys={keys}): {e}")
            return 0

    async def expire(self, key: str, ttl: int) -> bool:
        """设置键的过期时间"""
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.expire(self._make_key(key), ttl)
                return result is True
        except Exception as e:
            logger.error(f"Redis expire error (key={key}): {e}")
            return False

    # ========== JSON操作 ==========
    
    async def set_json(self, key: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """存储JSON数据"""
        try:
            # 使用 default=str 来处理 datetime 等非原生JSON支持的类型
            json_str = json.dumps(data, ensure_ascii=False, default=str)
            return await self.set(key, json_str, ttl)
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization error (key={key}): {e}")
            return False

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """获取JSON数据"""
        try:
            data = await self.get(key)
            if data is None:
                return None
            return json.loads(data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"JSON deserialization error (key={key}): {e}")
            return None

    # ========== 哈希操作 ==========
    
    async def hset(self, name: str, mapping: Dict[str, Any]) -> int:
        """设置哈希字段"""
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.hset(self._make_key(name), mapping=mapping)
                return result
        except Exception as e:
            logger.error(f"Redis hset error (name={name}): {e}")
            return 0

    async def hget(self, name: str, key: str) -> Optional[str]:
        """获取哈希字段"""
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.hget(self._make_key(name), key)
                return result
        except Exception as e:
            logger.error(f"Redis hget error (name={name}, key={key}): {e}")
            return None

    async def hgetall(self, name: str) -> Dict[str, str]:
        """获取所有哈希字段"""
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.hgetall(self._make_key(name))
                return result or {}
        except Exception as e:
            logger.error(f"Redis hgetall error (name={name}): {e}")
            return {}

    async def hdel(self, name: str, *keys: str) -> int:
        """删除哈希字段"""
        if not keys:
            return 0
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.hdel(self._make_key(name), *keys)
                return result
        except Exception as e:
            logger.error(f"Redis hdel error (name={name}, keys={keys}): {e}")
            return 0

    # ========== 集合操作 ==========
    
    async def sadd(self, name: str, *values: Any) -> int:
        """添加到集合"""
        if not values:
            return 0
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.sadd(self._make_key(name), *values)
                return result
        except Exception as e:
            logger.error(f"Redis sadd error (name={name}): {e}")
            return 0

    async def srem(self, name: str, *values: Any) -> int:
        """从集合删除"""
        if not values:
            return 0
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.srem(self._make_key(name), *values)
                return result
        except Exception as e:
            logger.error(f"Redis srem error (name={name}): {e}")
            return 0

    async def smembers(self, name: str) -> set:
        """获取集合所有成员"""
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.smembers(self._make_key(name))
                return result or set()
        except Exception as e:
            logger.error(f"Redis smembers error (name={name}): {e}")
            return set()

    async def sismember(self, name: str, value: Any) -> bool:
        """检查是否是集合成员"""
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.sismember(self._make_key(name), value)
                return result is True
        except Exception as e:
            logger.error(f"Redis sismember error (name={name}, value={value}): {e}")
            return False

    # ========== 列表操作 ==========
    
    async def lpush(self, name: str, *values: Any) -> int:
        """从左边推入列表"""
        if not values:
            return 0
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.lpush(self._make_key(name), *values)
                return result
        except Exception as e:
            logger.error(f"Redis lpush error (name={name}): {e}")
            return 0

    async def rpush(self, name: str, *values: Any) -> int:
        """从右边推入列表"""
        if not values:
            return 0
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.rpush(self._make_key(name), *values)
                return result
        except Exception as e:
            logger.error(f"Redis rpush error (name={name}): {e}")
            return 0

    async def lrange(self, name: str, start: int = 0, end: int = -1) -> List[str]:
        """获取列表范围"""
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.lrange(self._make_key(name), start, end)
                return result or []
        except Exception as e:
            logger.error(f"Redis lrange error (name={name}): {e}")
            return []
            
    # ========== SCAN操作（非阻塞，推荐） ==========

    # 修复 redis/base.py 中的 SCAN 操作
    
    async def scan_keys(self, pattern: str = "*", scan_count: int = 1000) -> List[str]:
        """使用SCAN获取匹配的键列表（非阻塞）"""
        try:
            pattern_with_prefix = self._make_key(pattern)
            keys = []
            cursor = 0  # 使用整数
            async with self._connection_manager.get_connection() as client:
                while True:
                    cursor, batch_keys = await client.scan(
                        cursor, match=pattern_with_prefix, count=scan_count
                    )
                    if self.key_prefix:
                        prefix_len = len(self.key_prefix)
                        keys.extend([key[prefix_len:] for key in batch_keys if key.startswith(self.key_prefix)])
                    else:
                        keys.extend(batch_keys)
                    if cursor == 0:  # cursor为0表示扫描完成
                        break
            return keys
        except Exception as e:
            logger.error(f"Redis scan keys error (pattern={pattern}): {e}")
            return []
    
    async def scan_count(self, pattern: str = "*", scan_count: int = 1000) -> int:
        """使用SCAN统计匹配键的数量（非阻塞）"""
        try:
            pattern_with_prefix = self._make_key(pattern)
            count = 0
            cursor = 0
            async with self._connection_manager.get_connection() as client:
                while True:
                    cursor, batch_keys = await client.scan(
                        cursor, match=pattern_with_prefix, count=scan_count
                    )
                    count += len(batch_keys)
                    if cursor == 0:
                        break
            return count
        except Exception as e:
            logger.error(f"Redis scan count error (pattern={pattern}): {e}")
            return 0
    
    async def scan_delete(self, pattern: str, scan_count: int = 500) -> int:
        """使用SCAN批量删除匹配的键（非阻塞）"""
        total_deleted = 0
        try:
            pattern_with_prefix = self._make_key(pattern)
            cursor = 0
            async with self._connection_manager.get_connection() as client:
                while True:
                    cursor, keys = await client.scan(cursor, match=pattern_with_prefix, count=scan_count)
                    if keys:
                        deleted = await client.delete(*keys)
                        total_deleted += deleted
                    if cursor == 0:
                        break
            return total_deleted
        except Exception as e:
            logger.error(f"Redis scan delete error (pattern={pattern}): {e}")
            return 0

    # ========== Pipeline / Transaction Support ========== #

    @asynccontextmanager
    async def pipeline(self, transaction: bool = True):
        """
        提供一个 Pipeline 上下文管理器，支持事务。

        Args:
            transaction: 是否作为事务执行 (使用 MULTI/EXEC)。默认为 True。

        Usage:
            async with self.pipeline() as pipe:
                await pipe.set("key1", "value1")
                await pipe.sadd("set_key", "member1")
                results = await pipe.execute()
        """
        try:
            async with self._connection_manager.get_connection() as client:
                async with client.pipeline(transaction=transaction) as pipe:
                    yield pipe
        except Exception as e:
            logger.error(f"Redis pipeline context error: {e}")
            # 重新抛出异常，以便调用方可以处理它
            raise

    
    # ========== 工具方法 ==========
    
    async def ping(self) -> bool:
        """测试连接"""
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.ping()
                return result is True
        except Exception as e:
            logger.error(f"Redis ping error: {e}")
            return False

    async def flushdb(self) -> bool:
        """清空当前数据库（慎用）"""
        try:
            async with self._connection_manager.get_connection() as client:
                result = await client.flushdb()
                return result is True
        except Exception as e:
            logger.error(f"Redis flushdb error: {e}")
            return False

