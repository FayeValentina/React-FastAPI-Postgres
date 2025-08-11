"""
任务注册中心 - 统一管理任务类型定义和Celery任务映射
"""
from enum import Enum as PyEnum
from typing import Dict, Optional, Set


class TaskType(str, PyEnum):
    """任务类型枚举"""
    
    # === 爬取相关任务 ===
    BOT_SCRAPING = "bot_scraping"
    MANUAL_SCRAPING = "manual_scraping"
    BATCH_SCRAPING = "batch_scraping"
    
    # === 清理相关任务 ===
    CLEANUP_TOKENS = "cleanup_tokens"
    CLEANUP_CONTENT = "cleanup_content"
    CLEANUP_EVENTS = "cleanup_events"
    
    # === 通知相关任务 ===
    SEND_EMAIL = "send_email"
    SEND_NOTIFICATION = "send_notification"
    
    # === 数据处理任务 ===
    DATA_EXPORT = "data_export"
    DATA_BACKUP = "data_backup"
    DATA_ANALYSIS = "data_analysis"
    
    # === 系统维护任务 ===
    HEALTH_CHECK = "health_check"
    SYSTEM_MONITOR = "system_monitor"
    LOG_ROTATION = "log_rotation"


class TaskStatus(str, PyEnum):
    """任务状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    ERROR = "error"


class SchedulerType(str, PyEnum):
    """调度器类型枚举"""
    INTERVAL = "interval"
    CRON = "cron"
    DATE = "date"
    MANUAL = "manual"


class TaskRegistry:
    """任务注册中心"""
    
    # Celery任务名称映射
    _CELERY_TASK_MAPPING: Dict[TaskType, str] = {
        # 爬取任务
        TaskType.BOT_SCRAPING: 'execute_bot_scraping_task',
        TaskType.MANUAL_SCRAPING: 'execute_manual_scraping_task',
        TaskType.BATCH_SCRAPING: 'execute_batch_scraping_task',
        
        # 清理任务
        TaskType.CLEANUP_TOKENS: 'cleanup_expired_tokens_task',
        TaskType.CLEANUP_CONTENT: 'cleanup_old_content_task',
        TaskType.CLEANUP_EVENTS: 'cleanup_schedule_events_task',
        
        # 通知任务
        TaskType.SEND_EMAIL: 'send_email_task',
        TaskType.SEND_NOTIFICATION: 'send_notification_task',
        
        # 数据处理任务
        TaskType.DATA_EXPORT: 'data_export_task',
        TaskType.DATA_BACKUP: 'data_backup_task',
        TaskType.DATA_ANALYSIS: 'data_analysis_task',
        
        # 系统维护任务
        TaskType.HEALTH_CHECK: 'health_check_task',
        TaskType.SYSTEM_MONITOR: 'system_monitor_task',
        TaskType.LOG_ROTATION: 'log_rotation_task',
    }
    
    # 任务队列映射
    _QUEUE_MAPPING: Dict[TaskType, str] = {
        TaskType.BOT_SCRAPING: 'scraping',
        TaskType.MANUAL_SCRAPING: 'scraping',
        TaskType.BATCH_SCRAPING: 'scraping',
        TaskType.CLEANUP_TOKENS: 'cleanup',
        TaskType.CLEANUP_CONTENT: 'cleanup',
        TaskType.CLEANUP_EVENTS: 'cleanup',
        TaskType.SEND_EMAIL: 'default',
        TaskType.SEND_NOTIFICATION: 'default',
        TaskType.DATA_EXPORT: 'default',
        TaskType.DATA_BACKUP: 'default',
        TaskType.DATA_ANALYSIS: 'default',
        TaskType.HEALTH_CHECK: 'default',
        TaskType.SYSTEM_MONITOR: 'default',
        TaskType.LOG_ROTATION: 'default',
    }
    
    # 任务类型缩写映射
    _TASK_TYPE_SHORTCUTS: Dict[TaskType, str] = {
        # 爬取任务
        TaskType.BOT_SCRAPING: 'scrape_bot',
        TaskType.MANUAL_SCRAPING: 'scrape_man',
        TaskType.BATCH_SCRAPING: 'scrape_batch',
        
        # 清理任务
        TaskType.CLEANUP_TOKENS: 'cleanup_tok',
        TaskType.CLEANUP_CONTENT: 'cleanup_cnt',
        TaskType.CLEANUP_EVENTS: 'cleanup_evt',
        
        # 通知任务
        TaskType.SEND_EMAIL: 'email',
        TaskType.SEND_NOTIFICATION: 'notify',
        
        # 数据处理任务
        TaskType.DATA_EXPORT: 'export',
        TaskType.DATA_BACKUP: 'backup',
        TaskType.DATA_ANALYSIS: 'analyze',
        
        # 系统维护任务
        TaskType.HEALTH_CHECK: 'health',
        TaskType.SYSTEM_MONITOR: 'monitor',
        TaskType.LOG_ROTATION: 'logrot',
    }
    
    # 调度类型缩写映射
    _SCHEDULER_TYPE_SHORTCUTS: Dict[SchedulerType, str] = {
        SchedulerType.INTERVAL: 'int',
        SchedulerType.CRON: 'cron',
        SchedulerType.DATE: 'once',
        SchedulerType.MANUAL: 'man',
    }
    
    @classmethod
    def get_celery_task_name(cls, task_type: TaskType) -> str:
        """获取Celery任务名称"""
        task_name = cls._CELERY_TASK_MAPPING.get(task_type)
        if not task_name:
            raise ValueError(f"不支持的任务类型: {task_type}")
        return task_name
    
    @classmethod
    def get_queue_name(cls, task_type: TaskType) -> str:
        """获取任务队列名称"""
        return cls._QUEUE_MAPPING.get(task_type, 'default')
    
    @classmethod
    def register_task(cls, task_type: TaskType, celery_task_name: str, queue: str = 'default'):
        """动态注册新任务类型"""
        cls._CELERY_TASK_MAPPING[task_type] = celery_task_name
        cls._QUEUE_MAPPING[task_type] = queue
    
    @classmethod
    def is_task_supported(cls, task_type: TaskType) -> bool:
        """检查任务类型是否支持"""
        return task_type in cls._CELERY_TASK_MAPPING
    
    @classmethod
    def get_all_task_types(cls) -> Dict[str, str]:
        """获取所有支持的任务类型映射"""
        return {
            task_type.value: celery_name 
            for task_type, celery_name in cls._CELERY_TASK_MAPPING.items()
        }
    
    @classmethod
    def get_supported_task_types(cls) -> Set[TaskType]:
        """获取所有支持的任务类型"""
        return set(cls._CELERY_TASK_MAPPING.keys())
    
    @classmethod
    def get_task_type_shortcut(cls, task_type: TaskType) -> str:
        """获取任务类型缩写"""
        shortcut = cls._TASK_TYPE_SHORTCUTS.get(task_type)
        if not shortcut:
            # 如果没有定义缩写，使用原值并处理
            return task_type.value.replace('_', '')[:10]
        return shortcut
    
    @classmethod
    def get_scheduler_type_shortcut(cls, scheduler_type: SchedulerType) -> str:
        """获取调度类型缩写"""
        shortcut = cls._SCHEDULER_TYPE_SHORTCUTS.get(scheduler_type)
        if not shortcut:
            return scheduler_type.value[:4]
        return shortcut
    
    @classmethod
    def generate_job_id(cls, task_type: TaskType, scheduler_type: SchedulerType, config_id: int) -> str:
        """生成有意义的job_id
        
        格式: {task_short}_{schedule_short}_{config_id}
        例如: cleanup_tok_int_1
        """
        task_short = cls.get_task_type_shortcut(task_type)
        schedule_short = cls.get_scheduler_type_shortcut(scheduler_type)
        
        job_id = f"{task_short}_{schedule_short}_{config_id}"
        
        # 验证生成的job_id长度
        if len(job_id) > 50:  # APScheduler可能有长度限制
            raise ValueError(f"生成的job_id过长: {job_id}")
        
        return job_id
    
    @classmethod
    def extract_config_id_from_job_id(cls, job_id: str) -> Optional[int]:
        """从job_id中提取config_id
        
        job_id格式: task_short_schedule_short_config_id
        例如: cleanup_tok_int_1 -> 1
        """
        try:
            parts = job_id.split('_')
            if len(parts) >= 3:
                return int(parts[-1])  # 最后一部分是config_id
        except (ValueError, AttributeError):
            pass
        return None


# 导出便捷函数
def get_celery_task_name(task_type: TaskType) -> str:
    """获取Celery任务名称的便捷函数"""
    return TaskRegistry.get_celery_task_name(task_type)


def get_queue_name(task_type: TaskType) -> str:
    """获取队列名称的便捷函数"""
    return TaskRegistry.get_queue_name(task_type)


def is_task_supported(task_type: TaskType) -> bool:
    """检查任务类型是否支持的便捷函数"""
    return TaskRegistry.is_task_supported(task_type)