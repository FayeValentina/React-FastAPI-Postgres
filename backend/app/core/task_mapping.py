"""
任务类型到Celery任务名称的映射配置
"""
from typing import Dict

# 任务类型到Celery任务名称的映射
TASK_TYPE_TO_CELERY_MAPPING: Dict[str, str] = {
    # 爬取相关任务
    'bot_scraping': 'execute_bot_scraping_task',
    'manual_scraping': 'execute_manual_scraping_task',
    'batch_scraping': 'execute_batch_scraping_task',
    
    # 清理相关任务
    'cleanup_tokens': 'cleanup_expired_tokens_task',
    'cleanup_content': 'cleanup_old_content_task',
    'cleanup_events': 'cleanup_schedule_events_task',
    
    # 通知相关任务
    'send_email': 'send_email_task',
    'send_notification': 'send_notification_task',
    
    # 数据处理任务
    'data_export': 'data_export_task',
    'data_backup': 'data_backup_task',
    'data_analysis': 'data_analysis_task',
    
    # 系统维护任务
    'health_check': 'health_check_task',
    'system_monitor': 'system_monitor_task',
    'log_rotation': 'log_rotation_task',
}


def get_celery_task_name(task_type: str) -> str:
    """
    根据任务类型获取对应的Celery任务名称
    
    Args:
        task_type: 任务类型 (可以是字符串或枚举值)
        
    Returns:
        str: Celery任务名称
        
    Raises:
        ValueError: 当任务类型不支持时
    """
    # 处理枚举类型
    task_type_str = task_type.value if hasattr(task_type, 'value') else str(task_type)
    
    celery_task = TASK_TYPE_TO_CELERY_MAPPING.get(task_type_str)
    if not celery_task:
        raise ValueError(f"不支持的任务类型: {task_type_str}")
    
    return celery_task


def register_task_type(task_type: str, celery_task: str) -> None:
    """
    注册新的任务类型映射
    
    Args:
        task_type: 任务类型
        celery_task: Celery任务名称
    """
    TASK_TYPE_TO_CELERY_MAPPING[task_type] = celery_task


def get_all_task_types() -> Dict[str, str]:
    """
    获取所有支持的任务类型映射
    
    Returns:
        Dict[str, str]: 任务类型到Celery任务名称的映射字典
    """
    return TASK_TYPE_TO_CELERY_MAPPING.copy()


def is_task_type_supported(task_type: str) -> bool:
    """
    检查是否支持指定的任务类型
    
    Args:
        task_type: 任务类型
        
    Returns:
        bool: 是否支持
    """
    task_type_str = task_type.value if hasattr(task_type, 'value') else str(task_type)
    return task_type_str in TASK_TYPE_TO_CELERY_MAPPING