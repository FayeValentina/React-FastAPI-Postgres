from enum import Enum

class CacheTags(str, Enum):
    """Central definition for cache tags used with the tag-based caching system."""

    TASK_CONFIG = "task_config"
    SYSTEM_STATUS = "system_status"
    SYSTEM_DASHBOARD = "system_dashboard"
    USER = "user"
    SCHEDULE = "schedule"
    EXECUTION_STATS = "execution_stats"
