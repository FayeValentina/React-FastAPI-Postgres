"""
任务注册中心 - 统一管理任务类型定义和worker任务映射
"""
from enum import Enum as PyEnum
from typing import Dict, Optional, Set, Callable
import logging

logger = logging.getLogger(__name__)


class TaskType(str, PyEnum):
    """任务类型枚举"""
    
    # === 爬取相关任务 ===
    BOT_SCRAPING = "bot_scraping"
    MANUAL_SCRAPING = "manual_scraping"
    BATCH_SCRAPING = "batch_scraping"
    
    # === 清理相关任务 ===
    CLEANUP_TOKENS = "cleanup_tokens"
    CLEANUP_CONTENT = "cleanup_content"
    
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
    TIMEOUT_MONITOR = "timeout_monitor"
    CLEANUP_TIMEOUT_TASKS = "cleanup_timeout_tasks"
    
    # === test ===
    TEST_TIMEOUT = "test_timeout"
    TEST_FAILURE = "test_failure"
    TEST_SHORT_TIMEOUT = "test_short_timeout" 


class ConfigStatus(str, PyEnum):
    """任务配置状态"""
    ACTIVE = "active"      # 配置激活，可以被调度
    INACTIVE = "inactive"  # 配置未激活，不会被调度
    PAUSED = "paused"      # 配置暂停，临时停止调度
    ERROR = "error"        # 配置错误，需要修复


class RuntimeStatus(str, PyEnum):
    """任务运行时状态"""
    IDLE = "idle"           # 空闲
    SCHEDULED = "scheduled" # 已调度等待执行
    RUNNING = "running"     # 正在执行
    COMPLETED = "completed" # 执行完成
    FAILED = "failed"       # 执行失败
    TIMEOUT = "timeout"     # 执行超时
    MISFIRED = "misfired"   # 错过执行时间


class SchedulerType(str, PyEnum):
    """调度器类型枚举"""
    CRON = "cron"
    DATE = "date"
    MANUAL = "manual"


class ScheduleAction(str, PyEnum):
    """调度操作类型枚举"""
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    RELOAD = "reload"


class TaskRegistry:
    """任务注册中心"""
    
    # 默认队列名称
    DEFAULT_QUEUE = "default"
    
    # 任务ID前缀常量
    SCHEDULED_TASK_PREFIX = "scheduled_task_"
    
    # 任务状态常量
    TASK_STATUS_PENDING = "pending"
    TASK_STATUS_COMPLETED = "completed"
    TASK_STATUS_ERROR = "error"
    
    # 队列状态常量
    QUEUE_STATUS_ACTIVE = "active"
    QUEUE_STATUS_DISCONNECTED = "disconnected"
    
    # 调度相关常量
    UNKNOWN_VALUE = "unknown"
    CRON_WILDCARD = "*"
    CRON_EVERY_MINUTE = "* * * * *"
    
    
    # worker任务名称映射
    _worker_TASK_MAPPING: Dict[TaskType, str] = {
        # 爬取任务
        TaskType.BOT_SCRAPING: 'execute_bot_scraping_task',
        TaskType.MANUAL_SCRAPING: 'execute_manual_scraping_task',
        TaskType.BATCH_SCRAPING: 'execute_batch_scraping_task',
        
        # 清理任务
        TaskType.CLEANUP_TOKENS: 'cleanup_expired_tokens_task',
        TaskType.CLEANUP_CONTENT: 'cleanup_old_content_task',
        
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
        TaskType.TIMEOUT_MONITOR: 'timeout_monitor',
        TaskType.CLEANUP_TIMEOUT_TASKS: 'cleanup_timeout_tasks',
        
        # test
        TaskType.TEST_TIMEOUT: 'test_timeout_task',
        TaskType.TEST_FAILURE: 'test_failure_task',
        TaskType.TEST_SHORT_TIMEOUT: 'test_short_timeout_task',
    }
    
    # 任务队列映射
    _QUEUE_MAPPING: Dict[TaskType, str] = {
        TaskType.BOT_SCRAPING: 'scraping',
        TaskType.MANUAL_SCRAPING: 'scraping',
        TaskType.BATCH_SCRAPING: 'scraping',
        TaskType.CLEANUP_TOKENS: 'cleanup',
        TaskType.CLEANUP_CONTENT: 'cleanup',
        TaskType.SEND_EMAIL: 'default',
        TaskType.SEND_NOTIFICATION: 'default',
        TaskType.DATA_EXPORT: 'default',
        TaskType.DATA_BACKUP: 'default',
        TaskType.DATA_ANALYSIS: 'default',
        TaskType.HEALTH_CHECK: 'default',
        TaskType.SYSTEM_MONITOR: 'default',
        TaskType.LOG_ROTATION: 'default',
        TaskType.TIMEOUT_MONITOR: 'monitor',
        TaskType.CLEANUP_TIMEOUT_TASKS: 'cleanup',
        TaskType.TEST_TIMEOUT: 'test',
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
        TaskType.TIMEOUT_MONITOR: 'timeout_mon',
        TaskType.CLEANUP_TIMEOUT_TASKS: 'cleanup_timeout',
    }
    
    # 调度类型缩写映射
    _SCHEDULER_TYPE_SHORTCUTS: Dict[SchedulerType, str] = {
        SchedulerType.CRON: 'cron',
        SchedulerType.DATE: 'once',
        SchedulerType.MANUAL: 'man',
    }
    
    @classmethod
    def get_worker_task_name(cls, task_type: TaskType) -> str:
        """获取worker任务名称"""
        task_name = cls._worker_TASK_MAPPING.get(task_type)
        if not task_name:
            raise ValueError(f"不支持的任务类型: {task_type}")
        return task_name
    
    @classmethod
    def get_queue_name(cls, task_type: TaskType) -> str:
        """获取任务队列名称"""
        return cls._QUEUE_MAPPING.get(task_type, cls.DEFAULT_QUEUE)
    
    @classmethod
    def register_task(cls, task_type: TaskType, worker_task_name: str, queue: str = 'default'):
        """动态注册新任务类型"""
        cls._worker_TASK_MAPPING[task_type] = worker_task_name
        cls._QUEUE_MAPPING[task_type] = queue
    
    @classmethod
    def is_task_supported(cls, task_type: TaskType) -> bool:
        """检查任务类型是否支持"""
        return task_type in cls._worker_TASK_MAPPING
    
    @classmethod
    def get_all_task_types(cls) -> Dict[str, str]:
        """获取所有支持的任务类型映射"""
        return {
            task_type.value: worker_name 
            for task_type, worker_name in cls._worker_TASK_MAPPING.items()
        }
    
    @classmethod
    def get_supported_task_types(cls) -> Set[TaskType]:
        """获取所有支持的任务类型"""
        return set(cls._worker_TASK_MAPPING.keys())
    
    @classmethod
    def get_all_queue_names(cls) -> Set[str]:
        """获取所有队列名称"""
        all_queues = set(cls._QUEUE_MAPPING.values())
        all_queues.add(cls.DEFAULT_QUEUE)  # 确保包含默认队列
        return all_queues
    
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


# 保持 ExecutionStatus 引用，但使用 models 中的定义
from app.models.task_execution import ExecutionStatus

# 全局任务函数映射缓存
_task_function_cache: Dict[TaskType, Callable] = {}

def _load_task_functions():
    """加载所有任务函数到缓存"""
    global _task_function_cache
    
    # 动态导入避免循环导入
    from app.tasks import cleanup_tasks, notification_tasks, data_tasks, test_timeout_task
    
    # 构建任务函数映射
    _task_function_cache = {
        TaskType.CLEANUP_TOKENS: cleanup_tasks.cleanup_expired_tokens,
        TaskType.CLEANUP_CONTENT: cleanup_tasks.cleanup_old_content,
        TaskType.SEND_EMAIL: notification_tasks.send_email,
        TaskType.DATA_EXPORT: data_tasks.export_data,
        TaskType.DATA_BACKUP: data_tasks.backup_data,
        # 为将来的任务类型预留
        # TaskType.BOT_SCRAPING: scraping_tasks.bot_scraping,
        # TaskType.MANUAL_SCRAPING: scraping_tasks.manual_scraping,
        TaskType.TEST_TIMEOUT: test_timeout_task.test_timeout_task,
        TaskType.TEST_FAILURE: test_timeout_task.test_failure_task,
        TaskType.TEST_SHORT_TIMEOUT: test_timeout_task.test_short_timeout_task,
    }
    
    logger.info(f"已加载 {len(_task_function_cache)} 个任务函数")


def get_task_function(task_type: TaskType) -> Optional[Callable]:
    """
    根据任务类型获取任务函数
    
    Args:
        task_type: 任务类型
        
    Returns:
        对应的任务函数，如果不存在返回None
    """
    if not _task_function_cache:
        _load_task_functions()
    
    return _task_function_cache.get(task_type)


# 导出便捷函数
def get_worker_task_name(task_type: TaskType) -> str:
    """获取worker任务名称的便捷函数"""
    return TaskRegistry.get_worker_task_name(task_type)


def get_queue_name(task_type: TaskType) -> str:
    """获取队列名称的便捷函数"""
    return TaskRegistry.get_queue_name(task_type)


def is_task_supported(task_type: TaskType) -> bool:
    """检查任务类型是否支持的便捷函数"""
    return TaskRegistry.is_task_supported(task_type)

# 更新导出列表
__all__ = [
    "TaskType",
    "ConfigStatus",
    "RuntimeStatus",
    "ExecutionStatus",
    "SchedulerType",
    "ScheduleAction",
    "TaskRegistry",
    "get_worker_task_name",
    "get_queue_name",
    "is_task_supported",
    "get_task_function",  # 新增导出
]