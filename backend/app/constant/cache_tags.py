"""
缓存标签枚举定义
"""

from enum import Enum


class CacheTags(str, Enum):
    """缓存标签枚举"""
    
    # 用户相关
    USER_PROFILE = "user_profile"
    USER_LIST = "user_list" 
    USER_ME = "user_me"
    
    # 任务系统
    TASK_CONFIGS = "task_configs"
    TASK_CONFIG_DETAIL = "task_config_detail"
    SCHEDULE_LIST = "schedule_list"
    EXECUTION_STATS = "execution_stats"
    
    # 系统状态
    SYSTEM_STATUS = "system_status"
    SYSTEM_DASHBOARD = "system_dashboard"
    SYSTEM_ENUMS = "system_enums"
    TASK_INFO = "task_info"