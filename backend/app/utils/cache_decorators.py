"""
基于Request对象的缓存装饰器 - 简化版
提供精确的路径参数和查询参数识别
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

from fastapi import Request
from pydantic import BaseModel

from app.core.redis_manager import redis_services
from app.services.redis.cache import CacheConfig

logger = logging.getLogger(__name__)


class ParameterExtractor:
    """基于Request对象的参数提取器"""
    
    @staticmethod
    def extract_from_request(
        request: Request,
        user_specific: bool = False,
        include_query_params: bool = False
    ) -> Dict[str, Any]:
        """从Request对象提取参数信息"""
        result = {
            'user_id': None,
            'path_params': [],
            'query_params': {}
        }
        
        try:
            # 提取路径参数（最准确的方式）
            if hasattr(request, 'path_params') and request.path_params:
                result['path_params'] = list(request.path_params.values())
            
            # 提取查询参数
            if include_query_params and hasattr(request, 'query_params'):
                result['query_params'] = dict(request.query_params)
            
            # 提取用户信息
            if user_specific and hasattr(request, 'state'):
                if hasattr(request.state, 'current_user'):
                    user = request.state.current_user
                    if user and hasattr(user, 'id'):
                        result['user_id'] = user.id
                elif hasattr(request.state, 'user_payload'):
                    # 从JWT payload提取用户ID
                    user_payload = request.state.user_payload
                    if user_payload and 'sub' in user_payload:
                        try:
                            result['user_id'] = int(user_payload['sub'])
                        except (ValueError, TypeError):
                            pass
        
        except Exception as e:
            logger.warning(f"从Request提取参数失败: {e}")
        
        return result
    
    @staticmethod
    def find_request_object(args: tuple, kwargs: Dict[str, Any]) -> Optional[Request]:
        """查找Request对象"""
        # 从kwargs查找
        for value in kwargs.values():
            if isinstance(value, Request):
                return value
        
        # 从args查找
        for arg in args:
            if isinstance(arg, Request):
                return arg
        
        return None


class CacheKeyBuilder:
    """缓存键构建器"""
    
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
            # 过滤空值并排序确保一致性
            filtered_params = {
                k: v for k, v in query_params.items() 
                if v is not None and v != ""
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
    """缓存序列化器，支持循环引用检测"""
    
    @staticmethod
    def serialize(obj: Any) -> Dict[str, Any]:
        """将对象序列化为缓存兼容格式"""
        try:
            visited = set()
            return CacheSerializer._serialize_recursive(obj, visited)
        except Exception as e:
            logger.warning(f"序列化对象失败: {e}")
            return None
    
    @staticmethod  
    def _serialize_recursive(obj: Any, visited: Set[int]) -> Any:
        """递归序列化对象，支持循环引用检测"""
        if obj is None:
            return None
        
        # 基础类型
        if isinstance(obj, (str, int, float, bool)):
            return obj
        
        # 循环引用检测
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
                            continue
                result["__class_name__"] = obj.__class__.__name__
                return result
            
            # 其他类型转换为字符串
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
    condition: Callable = None,
    on_cache_hit: Callable = None,
    on_cache_miss: Callable = None
):
    """基于Request对象的API响应缓存装饰器
    
    Args:
        key_prefix: 缓存键前缀
        ttl: 缓存过期时间（秒），默认使用CacheConfig.DEFAULT_TTL
        user_specific: 是否按用户缓存
        include_query_params: 是否在缓存键中包含查询参数
        condition: 缓存条件函数，返回True时才缓存
        on_cache_hit: 缓存命中回调
        on_cache_miss: 缓存未命中回调
    
    Usage:
        @cache_response("user_list", ttl=300, include_query_params=True)
        async def get_users(request: Request, ...): ...
        
        @cache_response("user_detail", user_specific=True)  
        async def get_user_profile(request: Request, user_id: int, ...): ...
    
    注意：被装饰的函数必须包含 Request 参数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_ttl = ttl or CacheConfig.DEFAULT_TTL
            
            try:
                # 查找Request对象
                request_obj = ParameterExtractor.find_request_object(args, kwargs)
                if not request_obj:
                    logger.warning(f"函数 {func.__name__} 缺少Request参数，跳过缓存")
                    return await func(*args, **kwargs)
                
                # 从Request提取参数
                extracted_params = ParameterExtractor.extract_from_request(
                    request_obj,
                    user_specific=user_specific,
                    include_query_params=include_query_params
                )
                
                # 构建缓存键
                cache_key = CacheKeyBuilder.build_key(
                    prefix=key_prefix,
                    path_params=extracted_params['path_params'],
                    query_params=extracted_params['query_params'] if include_query_params else None,
                    user_id=extracted_params['user_id']
                )
                
                logger.info(f"[CACHE_KEY_DEBUG] 函数: {func.__name__}, 构建缓存键: {cache_key}")
                logger.info(f"[CACHE_KEY_DEBUG] 提取参数: {extracted_params}")
                
                # 检查缓存条件
                if condition and not condition(*args, **kwargs):
                    logger.info(f"缓存条件不满足，跳过缓存: {cache_key}")
                    return await func(*args, **kwargs)
                
                # 尝试从缓存获取
                try:
                    cached_result = await redis_services.cache.get_api_cache(cache_key)
                    if cached_result is not None:
                        logger.info(f"缓存命中: {cache_key}")
                        
                        # 反序列化缓存数据
                        deserialized_result = CacheSerializer.deserialize(cached_result)
                        
                        if on_cache_hit:
                            on_cache_hit(cache_key, deserialized_result)
                        return deserialized_result
                except Exception as e:
                    logger.warning(f"读取缓存失败: {e}")
                
                # 缓存未命中，执行原函数
                logger.info(f"缓存未命中: {cache_key}")
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
                                logger.info(f"结果已缓存: {cache_key}, TTL: {cache_ttl}s")
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
    key_templates: Union[str, List[str]],
    user_specific: bool = False
):
    """缓存失效装饰器 - 最终版 v3.0

    简洁、健壮，并结合了精确删除和安全的模式删除。
    使用 f-string 风格的占位符动态构建键。

    Args:
        key_templates: 要清除的缓存键模板。
            - "user_list": 静态模式，会清理 user_list:*
            - "user_profile:{user_id}": 动态键，会从函数参数中寻找 `user_id` 的值，
              并精确删除键，如 user_profile:123。
        user_specific: 是否为用户特定缓存。仅对静态模式生效。

    Usage:
        @cache_invalidate(["user_profile:{user_id}", "user_list"])
        async def update_user(request: Request, user_id: int, ...): ...
    """
    if isinstance(key_templates, str):
        key_templates = [key_templates]

    def decorator(func: Callable) -> Callable:
        func_signature = inspect.signature(func)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            logger.info(f"缓存失效装饰器开始执行: {func.__name__}, 模板: {key_templates}")

            try:
                bound_args = func_signature.bind(*args, **kwargs).arguments
                
                specific_keys_to_delete = set()
                patterns_to_delete = set()

                for template in key_templates:
                    try:
                        resolved_key = template.format(**bound_args)
                        
                        if '{' in template and '}' in template:
                            # 动态键，检查是否需要加用户前缀
                            if user_specific:
                                request_obj = ParameterExtractor.find_request_object(args, kwargs)
                                if request_obj:
                                    params = ParameterExtractor.extract_from_request(request_obj, user_specific=True)
                                    current_user_id = params.get('user_id')
                                    if current_user_id:
                                        # 在动态键中间插入用户ID（与缓存时的格式一致）
                                        # 例如: user_profile:2 -> user_profile:u1:2
                                        key_parts = resolved_key.split(':')
                                        if len(key_parts) >= 2:
                                            user_specific_key = f"{key_parts[0]}:u{current_user_id}:{':'.join(key_parts[1:])}"
                                        else:
                                            user_specific_key = f"{resolved_key}:u{current_user_id}"
                                        specific_keys_to_delete.add(user_specific_key)
                                    else:
                                        logger.warning(f"user_specific=True 但无法为键 '{resolved_key}' 找到用户ID")
                                else:
                                    logger.warning(f"user_specific=True 但无法为键 '{resolved_key}' 找到Request对象")
                            else:
                                specific_keys_to_delete.add(resolved_key)
                        else:
                            # 静态模板，视为模式前缀
                            if user_specific:
                                # 尝试从请求中获取用户ID
                                request_obj = ParameterExtractor.find_request_object(args, kwargs)
                                if request_obj:
                                    params = ParameterExtractor.extract_from_request(request_obj, user_specific=True)
                                    current_user_id = params.get('user_id')
                                    if current_user_id:
                                        patterns_to_delete.add(f"{resolved_key}:u{current_user_id}*")
                                    else: # user_specific=True 但没找到用户，为安全跳过
                                        logger.warning(f"user_specific=True 但无法为模式 '{resolved_key}' 找到用户ID")
                                else:
                                    logger.warning(f"user_specific=True 但无法为模式 '{resolved_key}' 找到Request对象")
                            else:
                                patterns_to_delete.add(f"{resolved_key}*")
                                
                    except KeyError as e:
                        logger.warning(f"缓存清理失败：在函数 '{func.__name__}' 的参数中未找到占位符 '{e}'")

                if specific_keys_to_delete:
                    logger.info(f"[CACHE_INVALIDATE_DEBUG] 准备精确删除缓存键: {specific_keys_to_delete}")
                    cleared_count = await redis_services.cache.invalidate_api_cache_keys(list(specific_keys_to_delete))
                    if cleared_count > 0:
                        logger.info(f"精确清理缓存 {cleared_count} 个: {specific_keys_to_delete}")

                for pattern in patterns_to_delete:
                    logger.info(f"[CACHE_INVALIDATE_DEBUG] 准备模式删除缓存键: {pattern}")
                    cleared_count = await redis_services.cache.invalidate_api_cache_pattern(pattern)
                    if cleared_count > 0:
                        logger.info(f"模糊清理缓存 {cleared_count} 个 (模式: {pattern})")

            except Exception as e:
                logger.warning(f"缓存清理过程发生异常: {e}", exc_info=True)

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


def cache_list_data(key_prefix: str, ttl: int = None, user_specific: bool = False):
    """列表数据缓存（包含查询参数，默认3分钟TTL）"""
    return cache_response(
        key_prefix,
        ttl=ttl or CacheConfig.API_LIST_TTL,
        include_query_params=True,
        user_specific=user_specific
    )


def cache_stats_data(key_prefix: str, ttl: int = None):
    """统计数据缓存（包含查询参数，默认10分钟TTL）"""
    return cache_response(
        key_prefix,
        ttl=ttl or CacheConfig.STATS_CACHE_TTL,
        include_query_params=True
    )