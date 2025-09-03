import os
from typing import Any, List, Optional, Union
from dataclasses import dataclass
from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_env_file() -> str:
    """动态选择环境文件"""
    environment = os.getenv("ENVIRONMENT", "dev")
    if environment == "prod":
        return ".env.prod"
    else:
        return ".env.dev"


ENV_FILE = get_env_file()


class PostgresSettings(BaseSettings):
    """PostgreSQL 数据库配置"""
    HOST: str
    USER: str
    PASSWORD: str
    DB: str
    PORT: str = "5432"
    DATABASE_URL: Optional[PostgresDsn] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: Any) -> Any:
        if isinstance(v, str):
            return v
        
        fields = info.data
        if not all(fields.get(key) for key in ["USER", "PASSWORD", "HOST", "DB"]):
            raise ValueError("Database configuration is incomplete.")
            
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=fields.get("USER"),
            password=fields.get("PASSWORD"),
            host=fields.get("HOST"),
            port=int(fields.get("PORT", "5432")),
            path=fields.get("DB", "")
        )

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        """获取 SQLAlchemy 数据库 URI"""
        if not self.DATABASE_URL:
            raise ValueError("Database URI is not set")
        return str(self.DATABASE_URL)
    
    @property
    def SYNC_DATABASE_URL(self) -> str:
        """获取同步数据库 URI（用于 Alembic）"""
        return self.SQLALCHEMY_DATABASE_URL.replace("+asyncpg", "+psycopg2")
    

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )


class PgAdminSettings(BaseSettings):
    """PgAdmin 配置"""
    PORT: int = 5050
    DEFAULT_EMAIL: EmailStr
    DEFAULT_PASSWORD: str
    CONFIG_SERVER_MODE: bool = False
    CONFIG_ENHANCED_COOKIE_PROTECTION: bool = False
    CONFIG_WTF_CSRF_ENABLED: bool = False
    CONFIG_WTF_CSRF_HEADERS: List[str] = ["Referer", "Origin"]

    model_config = SettingsConfigDict(
        env_prefix="PGADMIN_",
        env_nested_delimiter="__",
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )


class SecuritySettings(BaseSettings):
    """安全相关配置"""
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )


class CORSSettings(BaseSettings):
    """CORS 配置"""
    ORIGINS: List[AnyHttpUrl] = []

    @field_validator("ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    model_config = SettingsConfigDict(
        env_prefix="BACKEND_CORS_",
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )


class LoggingSettings(BaseSettings):
    """日志配置"""
    LEVEL: str = "INFO"
    JSON: bool = False
    FILE: Optional[str] = None

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )


class RedditSettings(BaseSettings):
    """Reddit API 配置"""
    CLIENT_ID: str = ""
    CLIENT_SECRET: str = ""
    USER_AGENT: str = "Reddit-Scraper/1.0"
    USERNAME: str = ""
    PASSWORD: str = ""

    model_config = SettingsConfigDict(
        env_prefix="REDDIT_",
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )


class TwitterSettings(BaseSettings):
    """Twitter API 配置"""
    API_KEY: str = ""
    API_SECRET: str = ""
    ACCESS_TOKEN: str = ""
    ACCESS_TOKEN_SECRET: str = ""
    BEARER_TOKEN: str = ""

    model_config = SettingsConfigDict(
        env_prefix="TWITTER_",
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )


class AISettings(BaseSettings):
    """AI 服务配置"""
    GEMINI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_prefix="AI_",
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )


class EmailSettings(BaseSettings):
    """邮件服务配置"""
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    USERNAME: str = ""
    PASSWORD: str = ""
    FROM_EMAIL: str = ""
    USE_TLS: bool = True

    model_config = SettingsConfigDict(
        env_prefix="EMAIL_",
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )


class RabbitMQSettings(BaseSettings):
    """RabbitMQ 配置"""
    HOST: str = "rabbitmq"
    PORT: int = 5672
    USER: str = "guest"
    PASSWORD: str = "guest"
    VHOST: str = "/"
    
    @property
    def URL(self) -> str:
        """获取 RabbitMQ 连接 URL"""
        return f"amqp://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.VHOST}"
    
    model_config = SettingsConfigDict(
        env_prefix="RABBITMQ_",
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )


class RedisSettings(BaseSettings):
    """Redis 配置"""
    HOST: str = "redis"
    PORT: int = 6379
    PASSWORD: Optional[str] = None
    DB: int = 0
    URL: Optional[str] = None
    
    @property
    def CONNECTION_URL(self) -> str:
        """获取 Redis 连接 URL"""
        if self.URL:
            return self.URL
        
        if self.PASSWORD:
            return f"redis://:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DB}"
        else:
            return f"redis://{self.HOST}:{self.PORT}/{self.DB}"
    
    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )


# Redis 连接池配置（从 app.core.redis.config 合并）
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
                OSError,
            ]

        if self.socket_keepalive_options is None:
            # TCP keepalive配置
            self.socket_keepalive_options = {
                'TCP_KEEPIDLE': 600,     # 开始发送keepalive探测前的空闲时间
                'TCP_KEEPINTVL': 60,     # keepalive探测间隔
                'TCP_KEEPCNT': 3         # 失败探测次数
            }




class TaskIQSettings(BaseSettings):
    """TaskIQ 配置"""
    # TaskIQ 基本配置
    TIMEZONE: str = "UTC"
    TASK_DEFAULT_RETRY_DELAY: int = 60
    TASK_MAX_RETRIES: int = 3
    TASK_TIME_LIMIT: int = 30 * 60  # 30分钟
    
    # Worker设置
    WORKER_CONCURRENCY: int = 2
    
    # 结果存储设置
    RESULT_EX_TIME: int = 3600  # 结果过期时间（秒）
    
    model_config = SettingsConfigDict(
        env_prefix="TASKIQ_",
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )

class Settings(BaseSettings):
    """主配置类"""
    # 基本配置
    PROJECT_NAME: str = "FastAPI Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/v1"
    ENVIRONMENT: str = "development"
    
    # 服务配置
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_PORT: int = 8000
    
    # 子配置
    postgres: PostgresSettings = PostgresSettings()
    pgadmin: PgAdminSettings = PgAdminSettings()
    security: SecuritySettings = SecuritySettings()
    cors: CORSSettings = CORSSettings()
    logging: LoggingSettings = LoggingSettings()
    reddit: RedditSettings = RedditSettings()
    twitter: TwitterSettings = TwitterSettings()
    ai: AISettings = AISettings()
    email: EmailSettings = EmailSettings()
    rabbitmq: RabbitMQSettings = RabbitMQSettings()
    redis: RedisSettings = RedisSettings()
    # Redis 连接池子配置（新增）
    redis_pool: RedisPoolConfig = RedisPoolConfig()
    taskiq: TaskIQSettings = TaskIQSettings()

    # 数据库日志
    DB_ECHO_LOG: bool = True

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

settings = Settings()
