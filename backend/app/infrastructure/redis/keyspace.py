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
import time 
import random

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
    """Scheduler/Task state keys inside the "schedule:" namespace.

    New schedule_id-first helpers and a config→schedule index to support
    multiple runtime instances per template.
    """

    STATUS_PREFIX = "status:"
    META_PREFIX = "meta:"
    HISTORY_PREFIX = "history:"
    STATS_PREFIX = "stats:"
    DATA_PREFIX = "data:"
    INDEX_CONFIG_PREFIX = "index:config:"

    # Legacy helper (will be unused after refactor)
    def schedule_id_for_config(self, config_id: Union[int, str]) -> str:
        """Deprecated: old schedule id format used in previous versions."""
        return f"scheduled_task_{config_id}"

    # New schedule_id helpers (schedule-scoped keys)
    def schedule_status(self, schedule_id: str) -> str:
        return f"{self.STATUS_PREFIX}{schedule_id}"

    def schedule_metadata(self, schedule_id: str) -> str:
        return f"{self.META_PREFIX}{schedule_id}"

    def schedule_history(self, schedule_id: str) -> str:
        return f"{self.HISTORY_PREFIX}{schedule_id}"

    def schedule_stats(self, schedule_id: str) -> str:
        return f"{self.STATS_PREFIX}{schedule_id}"

    def schedule_data(self, schedule_id: str) -> str:
        """TaskIQ schedule payload key (if present)."""
        return f"{self.DATA_PREFIX}{schedule_id}"

    # Config → schedules index (a Set of schedule_ids)
    def config_index(self, config_id: Union[int, str]) -> str:
        return f"{self.INDEX_CONFIG_PREFIX}{config_id}"

    # New schedule_id builder
    def build_schedule_id(self, config_id: Union[int, str], uid: str | None = None) -> str:
        """Build schedule_id as scheduled_task:{config_id}:{uuid}.

        Note: UID should be a uuid4 string when not provided by caller.
        """
        if uid is None:
            try:
                import uuid  # local import to avoid module-level overhead
                uid = str(uuid.uuid4())
            except Exception:
                # Fallback: simple entropy if uuid is unavailable
                uid = f"{int(time.time())}{random.randint(1000, 9999)}"
        return f"scheduled_task:{config_id}:{uid}"


class RedisKeys:
    """Root container for key helpers."""

    def __init__(self) -> None:
        self.auth = _AuthKeys()
        self.cache = _CacheKeys()
        self.scheduler = _SchedulerKeys()


# Public singleton
redis_keys = RedisKeys()
