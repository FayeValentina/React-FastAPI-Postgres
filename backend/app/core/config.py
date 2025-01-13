from typing import Any, Dict, Optional, List
from pydantic import PostgresDsn, validator # type: ignore
from pydantic_settings import BaseSettings # type: ignore


class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str
    
    # CORS配置
    FRONTEND_URL: str  # 从环境变量读取前端URL
    BACKEND_CORS_ORIGINS: List[str] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | List[str], values: Dict[str, Any]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v if v is not None else []
    
    # PostgreSQL配置
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return f"postgresql://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}@{values.get('POSTGRES_HOST')}:{values.get('POSTGRES_PORT')}/{values.get('POSTGRES_DB')}"

    # JWT配置
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    
    # 服务器配置
    BACKEND_PORT: int
    
    # PgAdmin配置
    PGADMIN_EMAIL: str
    PGADMIN_PASSWORD: str
    PGADMIN_PORT: int

    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings() 