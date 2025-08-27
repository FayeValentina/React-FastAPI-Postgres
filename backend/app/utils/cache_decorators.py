"""
通用缓存装饰器
提供健壮的API响应缓存功能，支持多种缓存策略和序列化方式
"""

import functools
import hashlib
import inspect
import json
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Union, Set
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.redis_manager import redis_services
from app.models.user import User
from app.services.redis.cache import CacheConfig

logger = logging.getLogger(__name__)

class ParameterExtractor:
    """增强的参数提取器，使用inspect模块精确解析函数签名"""
    
    @staticmethod
    def extract_parameters(
        func: Callable, 
        args: tuple, 
        kwargs: Dict[str, Any],
        user_specific: bool = False,
        include_query_params: bool = False,
        exclude_params: List[str] = None
    ) -> Dict[str, Any]:
        """使用函数签名精确提取参数
        
        Args:
            func: 被装饰的函数
            args: 位置参数
            kwargs: 关键字参数
            user_specific: 是否提取用户信息
            include_query_params: 是否包含查询参数
            exclude_params: 要排除的参数
        
        Returns:
            Dict包含: user_id, path_params, query_params
        """
        if exclude_params is None:
            exclude_params = ['db', 'current_user']
        
        result = {
            'user_id': None,
            'path_params': [],
            'query_params': {}
        }
        
        try:
            # 获取函数签名
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())
            
            # 构建完整的参数映射
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            all_params = bound_args.arguments
            
            # 提取用户ID
            if user_specific and 'current_user' in all_params:
                user = all_params.get('current_user')
                if user and hasattr(user, 'id'):
                    result['user_id'] = user.id
            
            # 分类参数
            path_params = []
            query_params = {}
            
            for param_name, param_value in all_params.items():
                if param_name in exclude_params:
                    continue
                
                param_info = sig.parameters.get(param_name)
                if not param_info:
                    continue
                
                # 判断是否为路径参数（通常没有默认值且类型为基础类型）
                is_path_param = (
                    param_info.default == inspect.Parameter.empty and
                    param_info.annotation in (int, str, float) and
                    not param_name.startswith('_')
                )
                
                if is_path_param:
                    path_params.append(param_value)
                elif include_query_params and param_value is not None:
                    query_params[param_name] = param_value
            
            result['path_params'] = path_params
            result['query_params'] = query_params if include_query_params else {}
            
        except Exception as e:
            logger.warning(f"参数提取失败，使用回退方案: {e}")
            # 回退到简单提取
            result = ParameterExtractor._fallback_extract(args, kwargs, user_specific, include_query_params, exclude_params)
        
        return result
    
    @staticmethod
    def _fallback_extract(
        args: tuple, 
        kwargs: Dict[str, Any], 
        user_specific: bool, 
        include_query_params: bool,
        exclude_params: List[str]
    ) -> Dict[str, Any]:
        """回退的参数提取方案"""
        result = {
            'user_id': None,
            'path_params': [],
            'query_params': {}
        }
        
        # 提取用户ID
        if user_specific and 'current_user' in kwargs:
            user = kwargs.get('current_user')
            if user and hasattr(user, 'id'):
                result['user_id'] = user.id
        
        # 简单的路径参数提取（跳过数据库连接等）
        for arg in args:
            if not isinstance(arg, (AsyncSession, type(None))):
                if isinstance(arg, (str, int, float)):
                    result['path_params'].append(arg)
        
        # 查询参数提取
        if include_query_params:
            for key, value in kwargs.items():
                if key not in exclude_params and value is not None:
                    result['query_params'][key] = value
        
        return result

class CacheKeyBuilder:
    """优化的缓存键构建器"""
    
    @staticmethod
    def build_key(
        prefix: str,
        path_params: List[Union[str, int]] = None,
        query_params: Dict[str, Any] = None,
        user_id: Optional[int] = None,
        hash_long_keys: bool = True
    ) -> str:
        """构建缓存键"""
        key_parts = [prefix]
        
        # 添加用户ID
        if user_id:
            key_parts.append(f"u{user_id}")
        
        # 添加路径参数
        if path_params:
            key_parts.extend([str(p) for p in path_params if p is not None])
        
        # 添加查询参数
        if query_params:
            # 过滤和排序参数确保一致性
            filtered_params = {
                k: v for k, v in query_params.items() 
                if v is not None
            }
            
            if filtered_params:
                sorted_params = sorted(filtered_params.items())
                param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
                key_parts.append(f"q({param_str})")
        
        cache_key = ":".join(key_parts)
        
        # 对过长的键进行哈希
        if hash_long_keys and len(cache_key) > 200:
            key_hash = hashlib.md5(cache_key.encode()).hexdigest()[:16]
            return f"{prefix}:hash:{key_hash}"
        
        return cache_key

class CacheSerializer:
    """增强的缓存序列化器，支持循环引用检测和反序列化"""
    
    @staticmethod
    def serialize(obj: Any) -> Dict[str, Any]:
        """将对象序列化为缓存兼容格式"""
        try:
            visited = set()  # 循环引用检测
            return CacheSerializer._serialize_recursive(obj, visited)
        except Exception as e:
            logger.warning(f"序列化对象失败: {e}")
            return None
    
    @staticmethod  
    def _serialize_recursive(obj: Any, visited: Set[int]) -> Any:
        """递归序列化对象，支持循环引用检测"""
        # None值
        if obj is None:
            return None
        
        # 基础类型
        if isinstance(obj, (str, int, float, bool)):
            return obj
        
        # 循环引用检测（对可能产生循环引用的复杂对象）
        if hasattr(obj, '__dict__') or isinstance(obj, (dict, list, tuple)):
            obj_id = id(obj)
            if obj_id in visited:
                logger.warning(f"检测到循环引用，跳过对象: {type(obj)}")
                return f"<circular_reference:{type(obj).__name__}>"
            visited.add(obj_id)
        
        try:
            # 日期时间类型
            if isinstance(obj, (datetime, date)):
                return {"__datetime__": obj.isoformat()}
            
            # Decimal类型
            if isinstance(obj, Decimal):
                return {"__decimal__": str(obj)}
            
            # 枚举类型
            if isinstance(obj, Enum):
                return obj.value
            
            # Pydantic模型
            if isinstance(obj, BaseModel):
                result = obj.dict()
                result["__pydantic_model__"] = obj.__class__.__name__
                return result
            
            # 字典
            if isinstance(obj, dict):
                return {k: CacheSerializer._serialize_recursive(v, visited.copy()) for k, v in obj.items()}
            
            # 列表/元组
            if isinstance(obj, (list, tuple)):
                return [CacheSerializer._serialize_recursive(item, visited.copy()) for item in obj]
            
            # SQLAlchemy模型或其他对象
            if hasattr(obj, '__dict__'):
                result = {}
                for key, value in obj.__dict__.items():
                    if not key.startswith('_'):  # 跳过私有属性
                        try:
                            result[key] = CacheSerializer._serialize_recursive(value, visited.copy())
                        except Exception:
                            # 跳过无法序列化的属性
                            continue
                result["__class_name__"] = obj.__class__.__name__
                return result
            
            # 其他类型尝试转换为字符串
            try:
                return str(obj)
            except Exception:
                logger.warning(f"无法序列化类型: {type(obj)}")
                return None
                
        finally:
            # 清理访问记录
            if hasattr(obj, '__dict__') or isinstance(obj, (dict, list, tuple)):
                visited.discard(id(obj))
    
    @staticmethod
    def deserialize(data: Any) -> Any:
        """反序列化数据，将特殊标记的数据转换回原始类型"""
        if isinstance(data, dict):
            # 处理日期时间
            if "__datetime__" in data:
                try:
                    return datetime.fromisoformat(data["__datetime__"])
                except ValueError:
                    return data["__datetime__"]
            
            # 处理Decimal
            if "__decimal__" in data:
                try:
                    return Decimal(data["__decimal__"])
                except (ValueError, TypeError):
                    return data["__decimal__"]
            
            # 递归处理字典
            return {k: CacheSerializer.deserialize(v) for k, v in data.items()}
        
        elif isinstance(data, list):
            # 递归处理列表
            return [CacheSerializer.deserialize(item) for item in data]
        
        else:
            # 基础类型直接返回
            return data

def cache_response(
    key_prefix: str,
    ttl: Optional[int] = None,
    user_specific: bool = False,
    include_query_params: bool = False,
    exclude_params: List[str] = None,
    condition: Callable = None,
    on_cache_hit: Callable = None,
    on_cache_miss: Callable = None
):
    """API响应缓存装饰器
    
    Args:
        key_prefix: 缓存键前缀
        ttl: 缓存过期时间（秒），默认使用CacheConfig.DEFAULT_TTL
        user_specific: 是否按用户缓存
        include_query_params: 是否在缓存键中包含查询参数
        exclude_params: 要排除的参数名列表
        condition: 缓存条件函数，返回True时才缓存
        on_cache_hit: 缓存命中回调
        on_cache_miss: 缓存未命中回调
    
    Usage:
        @cache_response("user_list", ttl=300, include_query_params=True)
        async def get_users(...): ...
        
        @cache_response("user_detail", user_specific=True)  
        async def get_user_profile(...): ...
    """
    if exclude_params is None:
        exclude_params = []
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取实际TTL
            cache_ttl = ttl or CacheConfig.DEFAULT_TTL
            
            try:
                # 使用增强的参数提取器
                extracted_params = ParameterExtractor.extract_parameters(
                    func=func,
                    args=args,
                    kwargs=kwargs,
                    user_specific=user_specific,
                    include_query_params=include_query_params,
                    exclude_params=exclude_params
                )
                
                # 构建缓存键
                cache_key = CacheKeyBuilder.build_key(
                    prefix=key_prefix,
                    path_params=extracted_params['path_params'],
                    query_params=extracted_params['query_params'] if include_query_params else None,
                    user_id=extracted_params['user_id']
                )
                
                # 检查缓存条件
                if condition and not condition(*args, **kwargs):
                    logger.debug(f"缓存条件不满足，跳过缓存: {cache_key}")
                    return await func(*args, **kwargs)
                
                # 尝试从缓存获取
                try:
                    cached_result = await redis_services.cache.get_api_cache(cache_key)
                    if cached_result is not None:
                        logger.debug(f"缓存命中: {cache_key}")
                        
                        # 反序列化缓存数据
                        deserialized_result = CacheSerializer.deserialize(cached_result)
                        
                        if on_cache_hit:
                            on_cache_hit(cache_key, deserialized_result)
                        return deserialized_result
                except Exception as e:
                    logger.warning(f"读取缓存失败: {e}")
                
                # 缓存未命中，执行原函数
                logger.debug(f"缓存未命中: {cache_key}")
                if on_cache_miss:
                    on_cache_miss(cache_key)
                
                result = await func(*args, **kwargs)
                
                # 序列化并缓存结果
                if result is not None:
                    try:
                        serialized_result = CacheSerializer.serialize(result)
                        if serialized_result is not None:
                            success = await redis_services.cache.set_api_cache(
                                cache_key, 
                                serialized_result, 
                                ttl=cache_ttl
                            )
                            if success:
                                logger.debug(f"结果已缓存: {cache_key}, TTL: {cache_ttl}s")
                            else:
                                logger.warning(f"缓存写入失败: {cache_key}")
                        else:
                            logger.warning(f"序列化失败，跳过缓存: {cache_key}")
                    except Exception as e:
                        logger.warning(f"缓存写入异常: {cache_key}, 错误: {e}")
                
                return result
                
            except Exception as e:
                logger.error(f"缓存装饰器执行异常: {e}")
                # 缓存失败时仍然执行原函数
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def cache_invalidate(
    key_patterns: Union[str, List[str]],
    user_specific: bool = False
):
    """缓存失效装饰器
    
    用于在执行写操作后自动清理相关缓存
    
    Args:
        key_patterns: 要清除的缓存键模式
        user_specific: 是否包含用户特定缓存
    
    Usage:
        @cache_invalidate(["user_list", "user_detail"], user_specific=True)
        async def update_user(...): ...
    """
    if isinstance(key_patterns, str):
        key_patterns = [key_patterns]
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 执行原函数
            result = await func(*args, **kwargs)
            
            try:
                # 使用参数提取器获取用户信息
                extracted_params = ParameterExtractor.extract_parameters(
                    func=func,
                    args=args,
                    kwargs=kwargs,
                    user_specific=user_specific,
                    include_query_params=False,
                    exclude_params=['db', 'current_user']
                )
                
                # 构建失效模式
                patterns_to_clear = []
                
                for pattern in key_patterns:
                    patterns_to_clear.append(f"{pattern}*")
                    
                    # 如果是用户特定的，还要清理用户相关缓存
                    if user_specific and extracted_params['user_id']:
                        patterns_to_clear.append(f"{pattern}:u{extracted_params['user_id']}*")
                
                # 清理缓存
                for pattern in patterns_to_clear:
                    cleared_count = await redis_services.cache.invalidate_api_cache_pattern(pattern)
                    if cleared_count > 0:
                        logger.debug(f"清理缓存: {pattern}, 数量: {cleared_count}")
                        
            except Exception as e:
                logger.warning(f"缓存清理失败: {e}")
            
            return result
        return wrapper
    return decorator

# 预设装饰器，使用常见配置
def cache_static(key_prefix: str):
    """静态数据缓存（1小时TTL）"""
    return cache_response(key_prefix, ttl=CacheConfig.STATIC_TTL)

def cache_user_data(key_prefix: str, ttl: int = None):
    """用户数据缓存（用户特定，默认5分钟TTL）"""
    return cache_response(
        key_prefix, 
        ttl=ttl or CacheConfig.USER_CACHE_TTL, 
        user_specific=True
    )

def cache_list_data(key_prefix: str, ttl: int = None):
    """列表数据缓存（包含查询参数，默认3分钟TTL）"""
    return cache_response(
        key_prefix,
        ttl=ttl or CacheConfig.API_LIST_TTL,
        include_query_params=True
    )

def cache_stats_data(key_prefix: str, ttl: int = None):
    """统计数据缓存（包含查询参数，默认10分钟TTL）"""
    return cache_response(
        key_prefix,
        ttl=ttl or CacheConfig.STATS_CACHE_TTL,
        include_query_params=True
    )