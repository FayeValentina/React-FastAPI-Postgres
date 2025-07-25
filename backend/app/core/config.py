from typing import Any, List, Optional, Union
from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, field_validator
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
            raise ValueError("Database configuration is incomplete. Please check your environment variables.")
            
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

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=".env",
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
        env_file=".env",
        env_file_encoding="utf-8"
    )


class SecuritySettings(BaseSettings):
    """安全相关配置"""
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8"
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
        env_file=".env",
        env_file_encoding="utf-8"
    )


class LoggingSettings(BaseSettings):
    """日志配置"""
    LEVEL: str = "INFO"
    JSON: bool = False
    FILE: Optional[str] = None

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=".env",
        env_file_encoding="utf-8"
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

    # 数据库日志
    DB_ECHO_LOG: bool = True

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8"
    )


settings = Settings() 