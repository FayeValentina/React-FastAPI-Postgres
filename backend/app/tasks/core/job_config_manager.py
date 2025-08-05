"""
任务配置管理器 - 统一管理任务配置信息
从HybridScheduler中提取出来，专注于配置管理功能  
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class JobConfigManager:
    """任务配置管理器，负责存储和管理所有任务的配置信息"""
    
    def __init__(self):
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._config_history: List[Dict[str, Any]] = []
    
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
            
            # 保存历史记录
            if job_id in self._configs:
                old_config = self._configs[job_id].copy()
                old_config['action'] = 'updated'
                old_config['timestamp'] = datetime.utcnow().isoformat()
                self._config_history.append(old_config)
            
            self._configs[job_id] = config_with_meta
            
            logger.info(f"配置管理器已注册任务配置: {job_id}")
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
            # 保存更新前的配置到历史
            old_config = self._configs[job_id].copy()
            old_config['action'] = 'before_update'
            old_config['timestamp'] = datetime.utcnow().isoformat()
            self._config_history.append(old_config)
            
            # 更新配置
            self._configs[job_id].update(updates)
            self._configs[job_id]['updated_at'] = datetime.utcnow().isoformat()
            
            logger.info(f"配置管理器已更新任务配置: {job_id}")
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
            # 保存到历史记录
            removed_config = self._configs[job_id].copy()
            removed_config['action'] = 'removed'
            removed_config['timestamp'] = datetime.utcnow().isoformat()
            self._config_history.append(removed_config)
            
            # 删除配置
            del self._configs[job_id]
            
            logger.info(f"配置管理器已移除任务配置: {job_id}")
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
            config_type: 配置类型 ('bot_scraping', 'cleanup', 'custom')
            
        Returns:
            Dict: 匹配类型的配置字典
        """
        return {
            job_id: config for job_id, config in self._configs.items()
            if config.get('type') == config_type
        }
    
    def get_config_history(self, job_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取配置历史记录
        
        Args:
            job_id: 任务ID，为None时返回所有历史记录
            
        Returns:
            List: 历史记录列表
        """
        if job_id is None:
            return self._config_history.copy()
        
        return [
            record for record in self._config_history
            if record.get('job_id') == job_id
        ]
    
    def clear_history(self, older_than_days: int = 30) -> int:
        """
        清理历史记录
        
        Args:
            older_than_days: 清理多少天前的记录
            
        Returns:
            int: 清理的记录数量
        """
        try:
            from datetime import datetime, timedelta
            
            cutoff_time = datetime.utcnow() - timedelta(days=older_than_days)
            initial_count = len(self._config_history)
            
            self._config_history = [
                record for record in self._config_history
                if datetime.fromisoformat(record.get('timestamp', '')) > cutoff_time
            ]
            
            cleared_count = initial_count - len(self._config_history)
            
            if cleared_count > 0:
                logger.info(f"配置管理器已清理 {cleared_count} 条历史记录")
            
            return cleared_count
            
        except Exception as e:
            logger.error(f"清理配置历史记录失败: {e}")
            return 0
    
    def export_configs(self) -> Dict[str, Any]:
        """
        导出所有配置和历史记录
        
        Returns:
            Dict: 包含配置和历史的完整数据
        """
        return {
            'configs': self._configs.copy(),
            'history': self._config_history.copy(),
            'exported_at': datetime.utcnow().isoformat(),
            'total_configs': len(self._configs),
            'total_history_records': len(self._config_history)
        }
    
    def import_configs(self, data: Dict[str, Any]) -> bool:
        """
        导入配置数据
        
        Args:
            data: 包含配置和历史的数据字典
            
        Returns:
            bool: 导入是否成功
        """
        try:
            if 'configs' in data:
                self._configs.update(data['configs'])
            
            if 'history' in data:
                self._config_history.extend(data['history'])
            
            logger.info(f"配置管理器已导入配置数据")
            return True
            
        except Exception as e:
            logger.error(f"导入配置数据失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取配置管理器统计信息"""
        config_types = {}
        for config in self._configs.values():
            config_type = config.get('type', 'unknown')
            config_types[config_type] = config_types.get(config_type, 0) + 1
        
        return {
            'total_configs': len(self._configs),
            'config_types': config_types,
            'history_records': len(self._config_history),
            'last_updated': max(
                [config.get('updated_at', '') for config in self._configs.values()] + ['']
            ) or None
        }