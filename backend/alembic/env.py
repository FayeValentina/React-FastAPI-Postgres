import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 导入你的 SQLAlchemy 模型
from app.db.base import Base
from app.models import User

# this is the Alembic Config object
config = context.config

# 从环境变量获取数据库连接信息
section = config.config_ini_section
config.set_section_option(section, "POSTGRES_USER", os.getenv("POSTGRES_USER"))
config.set_section_option(section, "POSTGRES_PASSWORD", os.getenv("POSTGRES_PASSWORD"))
config.set_section_option(section, "POSTGRES_HOST", os.getenv("POSTGRES_HOST"))
config.set_section_option(section, "POSTGRES_PORT", os.getenv("POSTGRES_PORT"))
config.set_section_option(section, "POSTGRES_DB", os.getenv("POSTGRES_DB"))

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
        target_metadata=target_metadata,  # 使用正确的 metadata
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata  # 使用正确的 metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()