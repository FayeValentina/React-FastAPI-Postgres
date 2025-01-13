from sqlalchemy import create_engine # type: ignore
from sqlalchemy.orm import sessionmaker, declarative_base # type: ignore

from app.core.config import settings

# 创建数据库引擎
engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基本模型类
Base = declarative_base()

from app.models.user import User