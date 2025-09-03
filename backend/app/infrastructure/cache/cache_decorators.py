"""
基于标签的缓存装饰器V3 (最终版 - 解耦优化)
"""

import functools
import hashlib
import inspect
import logging
from typing import Callable, List, Any

from app.infrastructure.cache.cache_serializer import CacheSerializer 
from app.constant.cache_tags import CacheTags
from app.core.redis_manager import redis_services
from app.infrastructure.cache.cache_service import CacheConfig

logger = logging.getLogger(__name__)


def _generate_cache_key(
    func: Callable, 
    tags: List[CacheTags], 
    exclude_params: List[str] = None,
    *args, 
    **kwargs
) -> str:
    """
    根据函数签名和业务参数，自动生成唯一的缓存键。
    通过 inspect 模块动态绑定参数，并根据 exclude_params 列表排除指定参数。
    
    :param func: 目标函数
    :param tags: 缓存标签列表
    :param exclude_params: 要排除的参数名列表
    :param args: 函数位置参数
    :param kwargs: 函数关键字参数
    :return: 生成的缓存键
    """
    exclude_params = set(exclude_params) if exclude_params else set()
    
    # 使用 inspect 获取函数签名，并将 args 和 kwargs 绑定到参数名
    sig = inspect.signature(func)
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()
    
    # 过滤掉需要排除的参数
    filtered_params = {}
    for name, value in bound_args.arguments.items():
        if name not in exclude_params:
            filtered_params[name] = value
    
    # 从过滤后的参数生成稳定的字符串表示
    # 注意：使用 sorted 确保参数顺序一致性
    params_repr = repr(sorted(filtered_params.items()))
    
    # 基础键：函数名 + 业务参数
    base_key = f"{func.__module__}.{func.__name__}({params_repr})"
    
    prefix = tags[0].value if tags else "cache"
    key_hash = hashlib.md5(base_key.encode('utf-8')).hexdigest()
    
    return f"{prefix}:{key_hash}"


def cache(tags: List[CacheTags], ttl: int = None, exclude_params: List[str] = None):
    """
    缓存装饰器 (解耦版)。
    
    :param tags: 缓存标签列表，用于批量失效
    :param ttl: 缓存过期时间（秒）
    :param exclude_params: 要排除的参数名列表，常用于排除 db session, request, current_user 等对象
    
    使用示例：
    @cache(tags=[CacheTags.USER_PROFILE], exclude_params=["db", "current_user"])
    async def get_user_profile(user_id: int, db: AsyncSession, current_user: User):
        ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                # 将 exclude_params 传递给缓存键生成函数
                cache_key = _generate_cache_key(func, tags, exclude_params, *args, **kwargs)
                logger.info(f"[CACHE] 函数: {func.__name__}, 缓存键: {cache_key}")
                
                # 1. 尝试从缓存获取
                try:
                    cached_data = await redis_services.cache.get_binary_data(cache_key)
                    if cached_data:
                        # 使用新的序列化器进行反序列化
                        result = CacheSerializer.deserialize(cached_data)
                        logger.info(f"[CACHE_HIT] {cache_key}")
                        return result
                except Exception as e:
                    # 如果反序列化失败（如数据格式错误、模型未注册），则降级处理
                    logger.warning(f"缓存反序列化失败，将执行原函数: {e}")

                logger.info(f"[CACHE_MISS] {cache_key}")
                
                # 2. 执行原函数
                result = await func(*args, **kwargs)
                
                # 3. 缓存结果 (统一处理)
                if result is not None:
                    try:
                        # 直接尝试序列化，让序列化器自己处理类型判断
                        serialized_data = CacheSerializer.serialize(result)
                        
                        cache_ttl = ttl or CacheConfig.DEFAULT_TTL
                        
                        # 存储缓存数据
                        await redis_services.cache.set_binary_data(cache_key, serialized_data, ttl=cache_ttl)
                        
                        # 将缓存键关联到标签
                        for tag in tags:
                            await redis_services.cache.add_key_to_tag(tag.value, cache_key)
                            
                    except TypeError as e:
                        # 如果序列化器抛出 TypeError，说明是不支持的缓存类型，记录并跳过
                        logger.warning(f"对象类型不支持缓存，跳过: {e}")
                    except Exception as e:
                        # 其他序列化错误
                        logger.error(f"缓存序列化失败: {e}")

                return result
                
            except Exception as e:
                # 装饰器自身的其他异常
                logger.error(f"缓存装饰器执行异常，将执行原函数: {e}")
                # 保证即使缓存系统出问题，也不影响主业务逻辑
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# invalidate 装饰器保持不变，它与数据类型无关
def invalidate(tags: List[CacheTags]):
    """缓存失效装饰器"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            try:
                for tag in tags:
                    deleted_count = await redis_services.cache.invalidate_by_tag(tag.value)
                    logger.info(f"[CACHE_INVALIDATE] 标签: {tag.value}, 清理缓存项: {deleted_count}")
            except Exception as e:
                logger.warning(f"缓存清理失败: {e}")
            
            return result
        return wrapper
    return decorator