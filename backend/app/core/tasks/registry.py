"""
极简任务注册系统
"""
from typing import Dict, Optional, Callable, Set
import logging
import importlib
import pkgutil

logger = logging.getLogger(__name__)

# 全局任务注册表
TASKS: Dict[str, Dict] = {}

def task(name: str, queue: str = "default"):
    """任务注册装饰器"""
    def decorator(func: Callable) -> Callable:
        TASKS[name] = {
            'worker_name': getattr(func, 'task_name', func.__name__),
            'queue': queue,
            'func': func
        }
        logger.info(f"注册任务: {name} -> {TASKS[name]['worker_name']} (队列: {queue})")
        return func
    return decorator

# 简单的访问函数
def get_worker_name(task_type: str) -> str:
    """获取worker任务名"""
    if task_type not in TASKS:
        raise ValueError(f"未知任务类型: {task_type}")
    return TASKS[task_type]['worker_name']

def get_queue(task_type: str) -> str:
    """获取队列名"""
    return TASKS.get(task_type, {}).get('queue', 'default')

def get_function(task_type: str) -> Optional[Callable]:
    """获取任务函数"""
    return TASKS.get(task_type, {}).get('func')

def all_queues() -> Set[str]:
    """获取所有队列名"""
    queues = {t['queue'] for t in TASKS.values()}
    queues.add('default')
    return queues

def is_supported(task_type: str) -> bool:
    """检查任务是否支持"""
    return task_type in TASKS 

# 保留必要的枚举
from enum import Enum

class ConfigStatus(str, Enum):
    """任务配置状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    ERROR = "error"

class SchedulerType(str, Enum):
    """调度器类型枚举"""
    CRON = "cron"
    DATE = "date"
    MANUAL = "manual"

class ScheduleAction(str, Enum):
    """调度操作类型枚举"""
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    RELOAD = "reload"

class ExecutionStatus(str, Enum):
    """执行状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RUNNING = "running"

# 工具函数
def make_job_id(task_type: str, config_id: int) -> str:
    """生成job_id"""
    return f"{task_type}_{config_id}"

def extract_config_id(job_id: str) -> Optional[int]:
    """从job_id提取config_id"""
    try:
        return int(job_id.split('_')[-1])
    except:
        return None

def auto_discover_tasks(package_path: str = "app.tasks"):
    """
    自动发现并导入所有任务模块
    
    Args:
        package_path: 任务包路径
    """
    try:
        # 导入任务包
        package = importlib.import_module(package_path)
        
        # 遍历包中的所有模块
        for importer, modname, ispkg in pkgutil.iter_modules(
            package.__path__, 
            prefix=package.__name__ + "."
        ):
            if not ispkg:  # 只导入模块，不导入子包
                try:
                    importlib.import_module(modname)
                    logger.info(f"自动导入任务模块: {modname}")
                except Exception as e:
                    logger.warning(f"导入任务模块 {modname} 失败: {e}")
        
        logger.info(f"任务自动发现完成，共注册 {len(TASKS)} 个任务: {list(TASKS.keys())}")
        
    except Exception as e:
        logger.error(f"任务自动发现失败: {e}")
        raise