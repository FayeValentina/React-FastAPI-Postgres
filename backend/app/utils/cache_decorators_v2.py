"""Tag based caching decorators."""

from __future__ import annotations

import functools
import hashlib
import inspect
import json
from typing import Callable, Iterable, Sequence

from pydantic import BaseModel

from app.constant.cache_tags import CacheTags
from app.core.redis_manager import redis_services
from .cache_serializer_v2 import CacheSerializerV2


def _make_cache_key(func: Callable, args: tuple, kwargs: dict) -> str:
    """Create a deterministic cache key from function call data."""
    bound = inspect.signature(func).bind_partial(*args, **kwargs)
    key_data = {
        "func": f"{func.__module__}.{func.__qualname__}",
        "args": bound.args,
        "kwargs": bound.kwargs,
    }
    raw = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


def cache(tags: Sequence[CacheTags], ttl: int | None = None) -> Callable:
    """Cache decorator storing Pydantic model responses with tags."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = _make_cache_key(func, args, kwargs)
            cached = await redis_services.cache.get_cache(cache_key)
            if cached is not None:
                try:
                    return CacheSerializerV2.deserialize(cached)
                except Exception:
                    pass
            result = await func(*args, **kwargs)
            if isinstance(result, BaseModel):
                serialized = CacheSerializerV2.serialize(result)
                await redis_services.cache.set_cache(
                    cache_key,
                    serialized,
                    tags=[t.value for t in tags],
                    ttl=ttl,
                )
            return result

        return wrapper

    return decorator


def invalidate(tags: Iterable[CacheTags]) -> Callable:
    """Decorator to invalidate cache entries associated with given tags."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            await redis_services.cache.invalidate_tags([t.value for t in tags])
            return result

        return wrapper

    return decorator
