import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from dotenv import load_dotenv

# 导入枚举自动生成支持
import alembic_autogenerate_enums

# 加载环境特定的 .env 文件（如果存在）
# 在 Docker 环境中，环境变量已通过 docker-compose 传递，不需要加载 .env 文件
def get_env_file() -> str:
    """动态选择环境文件"""
    environment = os.getenv("ENVIRONMENT", "dev")
    if environment == "prod":
        return ".env.prod"
    else:
        return ".env.dev"

env_file = get_env_file()
if os.path.exists(env_file):
    load_dotenv(env_file)

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(current_dir)

# 导入你的 SQLAlchemy 模型
from app.infrastructure.database.postgres_base import Base
from app.modules.auth.models import User
from app.modules.auth.models import PasswordReset
from app.modules.content.models import RedditComment,RedditPost
from app.modules.tasks.models import TaskConfig, TaskExecution
from app.core.config import settings

# this is the Alembic Config object
config = context.config

# 设置数据库 URL（使用 psycopg2 替代 asyncpg 用于同步迁移）
db_url = settings.postgres.SQLALCHEMY_DATABASE_URL.replace("+asyncpg", "+psycopg2")
config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置 metadata
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()