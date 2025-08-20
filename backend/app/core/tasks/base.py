"""
任务服务基类
提供通用的任务操作方法
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class TaskServiceBase:
    """任务服务基类"""
    
    def __init__(self, service_name: str = ""):
        """
        初始化任务服务
        
        Args:
            service_name: 服务名称，用于日志记录
        """
        self.service_name = service_name
        self._broker = None
        self._redis_services = None
        self._initialized = False
    
    @property
    def broker(self):
        """获取broker，延迟加载"""
        if self._broker is None:
            from app.broker import broker
            self._broker = broker
        return self._broker
    
    @property
    def redis_services(self):
        """获取redis_services，延迟加载"""
        if self._redis_services is None:
            from app.core.redis_manager import redis_services
            self._redis_services = redis_services
        return self._redis_services
    
    async def initialize(self):
        """初始化服务"""
        if self._initialized:
            return
        
        try:
            # 触发延迟加载
            _ = self.broker
            _ = self.redis_services
            
            # 子类可以重写此方法进行特定初始化
            self._initialized = True
            logger.info(f"{self.service_name} 初始化成功")
        except Exception as e:
            logger.error(f"{self.service_name} 初始化失败: {e}")
            raise
    
    async def shutdown(self):
        """关闭服务"""
        try:
            self._initialized = False
            logger.info(f"{self.service_name} 已关闭")
        except Exception as e:
            logger.error(f"{self.service_name} 关闭失败: {e}")
    
    def _get_task_function(self, task_type: str):
        """根据任务类型获取任务函数"""
        from app.core.tasks import registry as tr
        return tr.get_function(task_type)