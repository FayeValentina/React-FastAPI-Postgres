"""
纯配置管理器 - 只负责管理任务配置信息
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class JobConfigManager:
    """纯配置管理器 - 只负责存储和管理任务配置"""
    
    def __init__(self):
        self._configs: Dict[str, Dict[str, Any]] = {}
    
    def register_config(self, job_id: str, config: Dict[str, Any]) -> bool:
        """
        注册任务配置
        
        Args:
            job_id: 任务ID
            config: 配置信息字典
            
        Returns:
            bool: 注册是否成功
        """
        try:
            # 添加元数据
            config_with_meta = {
                **config,
                'job_id': job_id,
                'registered_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            self._configs[job_id] = config_with_meta
            logger.debug(f"已注册任务配置: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"注册任务配置失败 {job_id}: {e}")
            return False
    
    def get_config(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务配置
        
        Args:
            job_id: 任务ID
            
        Returns:
            Optional[Dict]: 配置信息，不存在时返回None
        """
        return self._configs.get(job_id)
    
    def update_config(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新任务配置
        
        Args:
            job_id: 任务ID
            updates: 要更新的配置项
            
        Returns:
            bool: 更新是否成功
        """
        if job_id not in self._configs:
            logger.warning(f"尝试更新不存在的任务配置: {job_id}")
            return False
        
        try:
            # 更新配置
            self._configs[job_id].update(updates)
            self._configs[job_id]['updated_at'] = datetime.utcnow().isoformat()
            logger.debug(f"已更新任务配置: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新任务配置失败 {job_id}: {e}")
            return False
    
    def remove_config(self, job_id: str) -> bool:
        """
        移除任务配置
        
        Args:
            job_id: 任务ID
            
        Returns:
            bool: 移除是否成功
        """
        if job_id not in self._configs:
            logger.warning(f"尝试移除不存在的任务配置: {job_id}")
            return False
        
        try:
            del self._configs[job_id]
            logger.debug(f"已移除任务配置: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"移除任务配置失败 {job_id}: {e}")
            return False
    
    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务配置"""
        return self._configs.copy()
    
    def get_configs_by_type(self, config_type: str) -> Dict[str, Dict[str, Any]]:
        """
        根据类型获取任务配置
        
        Args:
            config_type: 配置类型 ('bot_scraping', 'cleanup', 'email', etc.)
            
        Returns:
            Dict: 匹配类型的配置字典
        """
        return {
            job_id: config for job_id, config in self._configs.items()
            if config.get('type') == config_type
        }
    
    def list_job_ids(self) -> List[str]:
        """获取所有任务ID列表"""
        return list(self._configs.keys())
    
    def has_config(self, job_id: str) -> bool:
        """检查是否存在指定配置"""
        return job_id in self._configs
    
    def clear_all_configs(self):
        """清空所有配置（调试用）"""
        self._configs.clear()
        logger.warning("已清空所有任务配置")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取配置统计信息"""
        config_types = {}
        for config in self._configs.values():
            config_type = config.get('type', 'unknown')
            config_types[config_type] = config_types.get(config_type, 0) + 1
        
        return {
            'total_configs': len(self._configs),
            'config_types': config_types,
            'last_updated': max(
                [config.get('updated_at', '') for config in self._configs.values()] + ['']
            ) or None
        }


# 全局配置管理器实例
job_config_manager = JobConfigManager()