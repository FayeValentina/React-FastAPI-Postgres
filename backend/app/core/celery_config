import os
from typing import Optional
from pydantic import BaseModel

class CeleryConfig(BaseModel):
    """轻量级环境配置类，只读取环境变量，不依赖其他模块"""
    
    # 数据库配置
    postgres_host: str = "postgres"
    postgres_port: str = "5432"
    postgres_user: str = "postgres"
    postgres_password: str = ""
    postgres_db: str = "postgres"
    
    # RabbitMQ 配置
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: str = "5672"
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"
    
    def __init__(self, **kwargs):
        # 从环境变量读取配置
        data = {
            'postgres_host': os.getenv('POSTGRES_HOST', 'postgres'),
            'postgres_port': os.getenv('POSTGRES_PORT', '5432'),
            'postgres_user': os.getenv('POSTGRES_USER', 'postgres'),
            'postgres_password': os.getenv('POSTGRES_PASSWORD', ''),
            'postgres_db': os.getenv('POSTGRES_DB', 'postgres'),
            'rabbitmq_host': os.getenv('RABBITMQ_HOST', 'rabbitmq'),
            'rabbitmq_port': os.getenv('RABBITMQ_PORT', '5672'),
            'rabbitmq_user': os.getenv('RABBITMQ_USER', 'guest'),
            'rabbitmq_password': os.getenv('RABBITMQ_PASSWORD', 'guest'),
            'rabbitmq_vhost': os.getenv('RABBITMQ_VHOST', '/'),
        }
        data.update(kwargs)
        super().__init__(**data)
    
    @property
    def broker_url(self) -> str:
        """构建 Celery Broker URL"""
        
        return (f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
                f"@{self.rabbitmq_host}:{self.rabbitmq_port}/{self.rabbitmq_vhost}")
    
    @property
    def result_backend(self) -> str:
        """构建 Celery Result Backend URL"""
        
        return (f"db+postgresql://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}")


# 全局实例
celery_config = CeleryConfig()
