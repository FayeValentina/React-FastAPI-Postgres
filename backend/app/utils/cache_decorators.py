"""
基于Request对象的缓存装饰器 - v4.0 优雅版
- 使用统一的 CacheKeyFactory 保证创建和失效的Key绝对一致
- 简化了 cache_invalidate 的逻辑，移除了复杂的字符串操作
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


# ==============================================================================
# 统一的Key生成工厂,确保缓存创建和失效时使用同一个key，避免不必要的复杂性
# ==============================================================================

class CacheKeyFactory:
    """
    缓存Key生成的单一来源。
    确保所有缓存键的创建和失效都遵循完全相同的逻辑。
    """
    @staticmethod
    def create(
        prefix: str,
        user_id: Optional[int] = None,
        path_params: List[Union[str, int]] = None,
        query_params: Dict[str, Any] = None,
        hash_long_keys: bool = True
    ) -> str:
        """
        根据所有组件构建一个确定性的缓存键。
        """
        key_parts = [prefix]

        # 1. 添加用户ID (如果提供)
        if user_id:
            key_parts.append(f"u{user_id}")

        # 2. 添加路径参数 (如果提供)
        if path_params:
            key_parts.extend([str(p) for p in path_params if p is not None])

        # 3. 添加查询参数 (如果提供)
        if query_params:
            filtered_params = {k: v for k, v in query_params.items() if v is not None and v != ""}
            if filtered_params:
                sorted_params = sorted(filtered_params.items())
                param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
                key_parts.append(f"q({param_str})")

        cache_key = ":".join(key_parts)

        # 4. 对过长的键进行哈希处理
        if hash_long_keys and len(cache_key) > 200:
            key_hash = hashlib.md5(cache_key.encode()).hexdigest()[:16]
            return f"{prefix}:hash:{key_hash}"

        return cache_key

# ==============================================================================
# 参数提取器，从Request中精确提取路径参数和查询参数。注意！这要求API端点必须有Request参数
# ==============================================================================

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

# ==============================================================================
# 缓存序列化器,将对象序列化为缓存兼容格式,或反序列化数据，将特殊标记的数据转换回原始类型
# ==============================================================================

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

# ==============================================================================
# API响应缓存构建装饰器
# ==============================================================================

def cache_response(
    key_prefix: str,
    ttl: Optional[int] = None,
    user_specific: bool = False,
    include_query_params: bool = False,
    condition: Callable = None,
    on_cache_hit: Callable = None,
    on_cache_miss: Callable = None
):
    """基于Request对象的API响应缓存装饰器 - 使用 CacheKeyFactory"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_ttl = ttl or CacheConfig.DEFAULT_TTL
            
            try:
                request_obj = ParameterExtractor.find_request_object(args, kwargs)
                if not request_obj:
                    logger.warning(f"函数 {func.__name__} 缺少Request参数，跳过缓存")
                    return await func(*args, **kwargs)
                
                # 从Request中提取所有需要的参数
                extracted_params = ParameterExtractor.extract_from_request(
                    request_obj,
                    user_specific=user_specific,
                    include_query_params=include_query_params
                )
                
                # ⭐ 使用统一的工厂创建Key
                cache_key = CacheKeyFactory.create(
                    prefix=key_prefix,
                    user_id=extracted_params['user_id'],
                    path_params=extracted_params['path_params'],
                    query_params=extracted_params['query_params'] if include_query_params else None
                )
                
                logger.info(f"[CACHE_KEY_DEBUG] 函数: {func.__name__}, 构建缓存键: {cache_key}")
                
                if condition and not condition(*args, **kwargs):
                    return await func(*args, **kwargs)
                
                cached_result = await redis_services.cache.get_api_cache(cache_key)
                if cached_result is not None:
                    logger.info(f"缓存命中: {cache_key}")
                    deserialized_result = CacheSerializer.deserialize(cached_result)
                    if on_cache_hit:
                        on_cache_hit(cache_key, deserialized_result)
                    return deserialized_result

                logger.info(f"缓存未命中: {cache_key}")
                if on_cache_miss:
                    on_cache_miss(cache_key)
                
                result = await func(*args, **kwargs)
                
                if result is not None:
                    serialized_result = CacheSerializer.serialize(result)
                    if serialized_result is not None:
                        await redis_services.cache.set_api_cache(
                            cache_key, 
                            serialized_result, 
                            ttl=cache_ttl
                        )
                
                return result
                
            except Exception as e:
                logger.error(f"缓存装饰器执行异常: {e}", exc_info=True)
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator

# ==============================================================================
# API响应缓存失效装饰器
# ==============================================================================

def cache_invalidate(
    key_templates: Union[str, List[str]],
    user_specific: bool = False
):
    """
    缓存失效装饰器 - v4.1 显式版
    - 废除了隐式约定，现在必须在模板中明确使用 `*` 来进行模式删除。
    - 提供了精确删除不带参数的静态键的能力。
    - 保证与 cache_response 的对称性。
    """
    if isinstance(key_templates, str):
        key_templates = [key_templates]

    def decorator(func: Callable) -> Callable:
        func_signature = inspect.signature(func)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 先执行被装饰的函数（例如，更新数据库的操作）
            result = await func(*args, **kwargs)
            
            try:
                bound_args = func_signature.bind(*args, **kwargs).arguments
                
                specific_keys_to_delete = set()
                patterns_to_delete = set()

                for template in key_templates:
                    # ===== 核心修改：明确判断模板类型 =====

                    # 1. 显式模式匹配：模板中包含 `*`
                    if '*' in template:
                        # 示例: "user_list:*"
                        # 注意：如果需要用户特定的模式，模板应为 "user_list:u{user_id}:*"
                        # 这里我们简化处理，直接使用模板
                        if user_specific:
                             request_obj = ParameterExtractor.find_request_object(args, kwargs)
                             if request_obj:
                                 params = ParameterExtractor.extract_from_request(request_obj, user_specific=True)
                                 current_user_id = params.get('user_id')
                                 if current_user_id:
                                     # 动态替换模板中的用户ID部分
                                     final_pattern = template.format(user_id=current_user_id)
                                     patterns_to_delete.add(final_pattern)
                                 else:
                                      patterns_to_delete.add(template) # user_id不存在则按原模板匹配
                             else:
                                patterns_to_delete.add(template)
                        else:
                            patterns_to_delete.add(template)

                    # 2. 动态键构造：模板中包含 `{}` 但不包含 `*`
                    elif '{' in template and '}' in template:
                        # 示例: "user_profile:{user_id}"
                        # 使用统一的工厂创建要精确删除的Key
                        key_prefix = template.split(':')[0]
                        
                        path_params_values = [
                            bound_args.get(param.strip('{}'))
                            for param in template.split(':')[1:]
                            if param # 过滤掉空字符串
                        ]
                        
                        current_user_id = None
                        if user_specific:
                            request_obj = ParameterExtractor.find_request_object(args, kwargs)
                            if request_obj:
                                params = ParameterExtractor.extract_from_request(request_obj, user_specific=True)
                                current_user_id = params.get('user_id')

                        key_to_delete = CacheKeyFactory.create(
                            prefix=key_prefix,
                            user_id=current_user_id,
                            path_params=path_params_values
                        )
                        specific_keys_to_delete.add(key_to_delete)
                    
                    # 3. 静态键：模板是纯字符串，不含 `*` 和 `{}`
                    else:
                        # 示例: "all_permissions"
                        # 精确删除一个固定的键
                        key_to_delete = CacheKeyFactory.create(prefix=template)
                        specific_keys_to_delete.add(key_to_delete)

                # 执行删除操作
                if specific_keys_to_delete:
                    logger.info(f"准备精确删除缓存键: {specific_keys_to_delete}")
                    await redis_services.cache.invalidate_api_cache_keys(list(specific_keys_to_delete))

                for pattern in patterns_to_delete:
                    logger.info(f"准备模式删除缓存键: {pattern}")
                    await redis_services.cache.invalidate_api_cache_pattern(pattern)

            except Exception as e:
                logger.warning(f"缓存清理过程发生异常: {e}", exc_info=True)

            return result
        return wrapper
    return decorator

# ==============================================================================
# 一部分预设的装饰器
# ==============================================================================


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

