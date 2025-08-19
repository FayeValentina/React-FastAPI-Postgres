"""
Redis配置模块
提供Redis连接配置和参数管理
"""
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class RedisPoolConfig:
    """Redis连接池配置"""
    
    # 连接池基础配置
    max_connections: int = 50
    min_connections: int = 5
    
    # 连接超时配置  
    socket_connect_timeout: int = 5
    socket_timeout: int = 5
    socket_keepalive: bool = True
    socket_keepalive_options: Optional[dict] = None
    
    # 重试配置
    retry_on_timeout: bool = True
    retry_on_error: List[type] = None
    max_retries: int = 3
    
    # 健康检查配置
    health_check_interval: int = 30
    health_check_timeout: int = 3
    
    # 编码配置
    decode_responses: bool = True
    encoding: str = "utf-8"
    
    def __post_init__(self):
        """初始化后处理"""
        if self.retry_on_error is None:
            # 默认重试的错误类型
            import redis
            self.retry_on_error = [
                redis.ConnectionError,
                redis.TimeoutError,
                ConnectionRefusedError,
                OSError
            ]
        
        if self.socket_keepalive_options is None:
            # TCP keepalive配置
            self.socket_keepalive_options = {
                'TCP_KEEPIDLE': 600,     # 开始发送keepalive探测前的空闲时间
                'TCP_KEEPINTVL': 60,     # keepalive探测间隔
                'TCP_KEEPCNT': 3         # 失败探测次数
            }


# 默认配置实例
default_pool_config = RedisPoolConfig()