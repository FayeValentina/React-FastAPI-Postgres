import os
from typing import Any, List, Optional, Union
from dataclasses import dataclass
from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, field_validator, computed_field, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_env_file() -> str:
    """动态选择环境文件"""
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment == "production":
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
    ENVIRONMENT: str = "development"
    
    # 服务配置
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_PORT: int = 8000

    # Internal API
    INTERNAL_API_SECRET: str = Field(default="")
    
    # 子配置
    postgres: PostgresSettings = PostgresSettings()
    pgadmin: PgAdminSettings = PgAdminSettings()
    security: SecuritySettings = SecuritySettings()
    logging: LoggingSettings = LoggingSettings()
    reddit: RedditSettings = RedditSettings()
    twitter: TwitterSettings = TwitterSettings()
    email: EmailSettings = EmailSettings()
    rabbitmq: RabbitMQSettings = RabbitMQSettings()
    redis: RedisSettings = RedisSettings()
    # Redis 连接池子配置（新增）
    redis_pool: RedisPoolConfig = RedisPoolConfig()
    taskiq: TaskIQSettings = TaskIQSettings()

    # 数据库日志
    DB_ECHO_LOG: bool = True

    # LLM / RAG 配置（简单直挂根 Settings，便于直接引用）
    CHAT_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    CHAT_API_KEY: str = "sk-local"
    CLASSIFIER_BASE_URL: str = "http://clf_server:8080/v1"
    CLASSIFIER_API_KEY: str = "sk-classifier"
    # 默认从 FILENAME 读取，避免变量不同步
    CHAT_MODEL: str = Field(default="gemini-2.5-flash-lite")
    CLASSIFIER_MODEL: str = Field(default_factory=lambda: os.getenv("CLASSIFIER_FILENAME", "gemma-3-4b-it-q4_0.gguf"))
    EMBEDDING_MODEL: str = Field(default="intfloat/multilingual-e5-base")
    RERANKER_MODEL: str = Field(default="BAAI/bge-reranker-base")
    RAG_STRATEGY_ENABLED: bool = Field(default=False)
    RAG_RERANK_ENABLED: bool = Field(default=False)
    RAG_USE_LINGUA: bool = Field(default=False)
    RAG_RERANK_CANDIDATES: int = Field(default=100)
    RAG_RERANK_SCORE_THRESHOLD: float = Field(default=0.48)
    RAG_TOP_K: int = Field(default=12)
    RAG_MIN_SIM: float = Field(default=0.35)
    RAG_MMR_LAMBDA: float = Field(default=0.55)
    RAG_PER_DOC_LIMIT: int = Field(default=6)
    RAG_OVERSAMPLE: int = Field(default=5)
    RAG_MAX_CANDIDATES: int = Field(default=240)
    RAG_CONTEXT_TOKEN_BUDGET: int = Field(default=4000)
    RAG_CONTEXT_MAX_EVIDENCE: int = Field(default=28)
    RAG_CHUNK_TARGET_TOKENS_EN: int = Field(default=260)
    RAG_CHUNK_TARGET_TOKENS_CJK: int = Field(default=420)
    RAG_CHUNK_TARGET_TOKENS_DEFAULT: int = Field(default=320)
    RAG_CHUNK_OVERLAP_RATIO: float = Field(default=0.15)
    RAG_CODE_CHUNK_MAX_LINES: int = Field(default=40)
    RAG_CODE_CHUNK_OVERLAP_LINES: int = Field(default=6)
    RAG_IVFFLAT_PROBES: int = Field(default=10)
    RAG_STRATEGY_LLM_CLASSIFIER_CONFIDENCE_THRESHOLD: float = Field(default=0.6)
    BM25_TOP_K: int = Field(default=8)
    BM25_WEIGHT: float = Field(default=0.35)
    BM25_MIN_SCORE: float = Field(default=0.0)
    SPACY_MODEL_NAME: str = Field(default="zh_core_web_sm")

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=[ENV_FILE],
        env_file_encoding="utf-8",
        extra="allow"
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def dynamic_settings_defaults(self) -> dict[str, Any]:
        """Return the default dynamic settings that can be overridden via Redis."""
        return {
            "RAG_STRATEGY_ENABLED": self.RAG_STRATEGY_ENABLED,
            "RAG_RERANK_ENABLED": self.RAG_RERANK_ENABLED,
            "RAG_RERANK_CANDIDATES": self.RAG_RERANK_CANDIDATES,
            "RAG_RERANK_SCORE_THRESHOLD": self.RAG_RERANK_SCORE_THRESHOLD,
            "RAG_TOP_K": self.RAG_TOP_K,
            "RAG_MIN_SIM": self.RAG_MIN_SIM,
            "RAG_MMR_LAMBDA": self.RAG_MMR_LAMBDA,
            "RAG_PER_DOC_LIMIT": self.RAG_PER_DOC_LIMIT,
            "RAG_OVERSAMPLE": self.RAG_OVERSAMPLE,
            "RAG_MAX_CANDIDATES": self.RAG_MAX_CANDIDATES,
            "RAG_CONTEXT_TOKEN_BUDGET": self.RAG_CONTEXT_TOKEN_BUDGET,
            "RAG_CONTEXT_MAX_EVIDENCE": self.RAG_CONTEXT_MAX_EVIDENCE,
            "RAG_IVFFLAT_PROBES": self.RAG_IVFFLAT_PROBES,
            "RAG_USE_LINGUA": self.RAG_USE_LINGUA,
            "RAG_STRATEGY_LLM_CLASSIFIER_CONFIDENCE_THRESHOLD": self.RAG_STRATEGY_LLM_CLASSIFIER_CONFIDENCE_THRESHOLD,
            "BM25_TOP_K": self.BM25_TOP_K,
            "BM25_WEIGHT": self.BM25_WEIGHT,
            "BM25_MIN_SCORE": self.BM25_MIN_SCORE,
        }

settings = Settings()
