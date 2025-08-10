from typing import Any, List, Optional, Union
from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    
    @property
    def CELERY_RESULT_BACKEND_URL(self) -> str:
        """获取 Celery Result Backend URI (不包含驱动程序)"""
        return f"postgresql://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DB}"

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=[".env"],
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
        env_file=[ ".env"],
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
        env_file=[ ".env"],
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
        env_file=[".env"],
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
        env_file=[".env"],
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
        env_file=[".env"],
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
        env_file=[".env"],
        env_file_encoding="utf-8",
        extra="allow"
    )


class AISettings(BaseSettings):
    """AI 服务配置"""
    GEMINI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_prefix="AI_",
        env_file=[".env"],
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
        env_file=[".env"],
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
        env_file=[".env"],
        env_file_encoding="utf-8",
        extra="allow"
    )


class CelerySettings(BaseSettings):
    """Celery 配置"""
    BROKER_URL: Optional[str] = None
    RESULT_BACKEND: Optional[str] = None
    
    # 任务配置
    TASK_SERIALIZER: str = "json"
    ACCEPT_CONTENT: List[str] = ["json"]
    RESULT_SERIALIZER: str = "json"
    
    # 时区设置
    TIMEZONE: str = "UTC"
    ENABLE_UTC: bool = True
    
    # 任务重试设置
    TASK_ACKS_LATE: bool = True
    TASK_REJECT_ON_WORKER_LOST: bool = True
    
    # 结果存储设置
    RESULT_EXPIRES: int = 3600 * 24  # 24小时
    RESULT_PERSISTENT: bool = True
    
    # Worker设置
    WORKER_PREFETCH_MULTIPLIER: int = 1
    WORKER_MAX_TASKS_PER_CHILD: int = 1000
    WORKER_POOL: str = "prefork"
    WORKER_CONCURRENCY: int = 2
    
    # 监控设置
    WORKER_SEND_TASK_EVENTS: bool = True
    TASK_SEND_SENT_EVENT: bool = True
    
    # 任务超时设置
    TASK_TIME_LIMIT: int = 30 * 60  # 30分钟
    TASK_SOFT_TIME_LIMIT: int = 25 * 60  # 25分钟
    
    # 任务重试设置
    TASK_DEFAULT_RETRY_DELAY: int = 60
    TASK_MAX_RETRIES: int = 3
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rabbitmq_settings = None
        self._postgres_settings = None
    
    def _set_dependencies(self, rabbitmq_settings: 'RabbitMQSettings', postgres_settings: 'PostgresSettings'):
        """设置依赖的配置对象"""
        self._rabbitmq_settings = rabbitmq_settings
        self._postgres_settings = postgres_settings
    
    @computed_field
    @property
    def broker_url(self) -> str:
        """获取 Broker URL"""
        if self.BROKER_URL:
            return self.BROKER_URL
        
        else:
            return self._rabbitmq_settings.URL
    
    @computed_field
    @property  
    def result_backend_url(self) -> str:
        """获取 Result Backend URL"""
        if self.RESULT_BACKEND:
            return self.RESULT_BACKEND
            
        else:
            return f"db+{self._postgres_settings.CELERY_RESULT_BACKEND_URL}"

    model_config = SettingsConfigDict(
        env_prefix="CELERY_",
        env_file=[".env"],
        env_file_encoding="utf-8",
        extra="allow"
    )

class Settings(BaseSettings):
    """主配置类"""
    # 基本配置
    PROJECT_NAME: str = "FastAPI Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
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
    celery: CelerySettings = CelerySettings()

    # 数据库日志
    DB_ECHO_LOG: bool = True

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=[ ".env"],
        env_file_encoding="utf-8",
        extra="allow"
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 在初始化完成后设置Celery的依赖关系
        self.celery._set_dependencies(self.rabbitmq, self.postgres)

settings = Settings() 


