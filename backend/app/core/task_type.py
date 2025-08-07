"""
任务类型枚举定义
"""
from enum import Enum as PyEnum


class TaskType(str, PyEnum):
    """任务类型枚举 - 定义系统支持的所有任务类型"""
    
    # === 爬取相关任务 ===
    BOT_SCRAPING = "bot_scraping"           # Bot自动爬取任务
    MANUAL_SCRAPING = "manual_scraping"     # 手动爬取任务
    BATCH_SCRAPING = "batch_scraping"       # 批量爬取任务
    
    # === 清理相关任务 ===
    CLEANUP_SESSIONS = "cleanup_sessions"   # 清理过期会话
    CLEANUP_TOKENS = "cleanup_tokens"       # 清理过期令牌  
    CLEANUP_CONTENT = "cleanup_content"     # 清理过期内容
    CLEANUP_EVENTS = "cleanup_events"       # 清理调度事件
    
    # === 通知相关任务 ===
    SEND_EMAIL = "send_email"               # 发送邮件通知
    SEND_NOTIFICATION = "send_notification" # 发送系统通知
    
    # === 数据处理任务 ===
    DATA_EXPORT = "data_export"             # 数据导出
    DATA_BACKUP = "data_backup"             # 数据备份
    DATA_ANALYSIS = "data_analysis"         # 数据分析
    
    # === 系统维护任务 ===
    HEALTH_CHECK = "health_check"           # 健康检查
    SYSTEM_MONITOR = "system_monitor"       # 系统监控
    LOG_ROTATION = "log_rotation"           # 日志轮转


class TaskStatus(str, PyEnum):
    """任务状态枚举"""
    ACTIVE = "active"       # 活跃状态
    INACTIVE = "inactive"   # 非活跃状态  
    PAUSED = "paused"       # 暂停状态
    ERROR = "error"         # 错误状态


class SchedulerType(str, PyEnum):
    """调度器类型枚举"""
    INTERVAL = "interval"   # 间隔调度
    CRON = "cron"          # Cron表达式调度
    DATE = "date"          # 指定时间调度
    MANUAL = "manual"      # 手动触发