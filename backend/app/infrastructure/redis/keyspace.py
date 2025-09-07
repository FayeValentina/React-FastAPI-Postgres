"""
Centralized Redis key naming helpers.

Goals:
- Single source of truth for key formats and prefixes across services.
- Keep current behavior (backward-compatible key strings) while removing hard-coded literals scattered in code.

Usage pattern with RedisBase(key_prefix=...):
- Services keep their own top-level namespace via RedisBase.key_prefix (e.g., "auth:", "cache:", "schedule:").
- This module defines the per-service subkeys only (e.g., token:{token}, status:{id}).
"""
from __future__ import annotations

from typing import Union


class _AuthKeys:
    """Auth-related keys inside the "auth:" namespace."""

    TOKEN_PREFIX = "token:"
    USER_TOKENS_PREFIX = "user_tokens:"

    def token(self, token: str) -> str:
        return f"{self.TOKEN_PREFIX}{token}"

    def user_tokens(self, user_id: Union[int, str]) -> str:
        return f"{self.USER_TOKENS_PREFIX}{user_id}"


class _CacheKeys:
    """Cache-related keys inside the "cache:" namespace."""

    TAG_PREFIX = "tag:"

    def tag(self, tag: str) -> str:
        return f"{self.TAG_PREFIX}{tag}"


class _SchedulerKeys:
    """Scheduler/Task state keys inside the "schedule:" namespace."""

    STATUS_PREFIX = "status:"
    META_PREFIX = "meta:"
    HISTORY_PREFIX = "history:"
    STATS_PREFIX = "stats:"

    # TaskIQ schedule_id builder (keep current convention for compatibility)
    def schedule_id_for_config(self, config_id: Union[int, str]) -> str:
        return f"scheduled_task_{config_id}"

    # Per-config subkeys
    def status(self, config_id: Union[int, str]) -> str:
        return f"{self.STATUS_PREFIX}{config_id}"

    def metadata(self, config_id: Union[int, str]) -> str:
        return f"{self.META_PREFIX}{config_id}"

    def history(self, config_id: Union[int, str]) -> str:
        return f"{self.HISTORY_PREFIX}{config_id}"

    def stats(self, config_id: Union[int, str]) -> str:
        return f"{self.STATS_PREFIX}{config_id}"


class RedisKeys:
    """Root container for key helpers."""

    def __init__(self) -> None:
        self.auth = _AuthKeys()
        self.cache = _CacheKeys()
        self.scheduler = _SchedulerKeys()


# Public singleton
redis_keys = RedisKeys()

