import asyncio
from functools import wraps
from typing import Callable
import logging

logger = logging.getLogger(__name__)


def with_retry(max_retries: int = 3, retry_interval: int = 60):
    """任务重试装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retry_count = 0
            last_error = None
            
            while retry_count <= max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    retry_count += 1
                    
                    if retry_count <= max_retries:
                        await asyncio.sleep(retry_interval)
                        logger.warning(f"任务执行失败，第{retry_count}次重试...")
                    else:
                        logger.error(f"任务执行失败，已达最大重试次数: {e}")
                        raise
                        
            raise last_error
            
        return wrapper
    return decorator


def with_timeout(timeout_seconds: int):
    """任务超时装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"任务执行超时（{timeout_seconds}秒）")
                
        return wrapper
    return decorator


def with_retry_and_timeout(max_retries: int = 3, retry_interval: int = 60, timeout_seconds: int = 300):
    """结合重试和超时的装饰器"""
    def decorator(func: Callable):
        @with_retry(max_retries=max_retries, retry_interval=retry_interval)
        @with_timeout(timeout_seconds=timeout_seconds)
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
                
        return wrapper
    return decorator