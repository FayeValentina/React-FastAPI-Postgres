from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import Optional, Dict, Any
import re

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash
from app.core.exceptions import (
    EmailAlreadyRegisteredError, 
    UsernameTakenError,
    DatabaseError,
    ResourceNotFoundError,
    ValidationError
)


# 错误常量
ERROR_EMAIL_REGISTERED = "该邮箱已被注册"
ERROR_USERNAME_TAKEN = "该用户名已被使用"
ERROR_CREATE_USER = "创建用户时出错"
ERROR_UPDATE_USER = "更新用户时出错"
ERROR_DELETE_USER = "删除用户时出错"


class CRUDUser:
    async def get(self, db: AsyncSession, id: int) -> Optional[User]:
        """获取指定ID的用户"""
        result = await db.execute(select(User).filter(User.id == id))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        result = await db.execute(select(User).filter(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        result = await db.execute(select(User).filter(User.username == username))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, obj_in: UserCreate) -> User:
        """
        创建新用户
        
        参数:
            db: 数据库会话
            obj_in: 用户创建数据
            
        返回:
            创建的用户对象
            
        抛出:
            EmailAlreadyRegisteredError: 如果邮箱已存在
            UsernameTakenError: 如果用户名已存在
            DatabaseError: 如果数据库操作失败
        """
        # 检查邮箱是否已存在
        existing_email = await self.get_by_email(db, email=obj_in.email)
        if existing_email:
            raise EmailAlreadyRegisteredError()
        
        # 检查用户名是否已存在
        existing_username = await self.get_by_username(db, username=obj_in.username)
        if existing_username:
            raise UsernameTakenError()

        try:
            db_obj = User(
                email=obj_in.email,
                username=obj_in.username,
                hashed_password=get_password_hash(obj_in.password),
                full_name=obj_in.full_name,
                age=obj_in.age if hasattr(obj_in, "age") else None,
                is_active=True,
                is_superuser=obj_in.is_superuser,
            )
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            await db.rollback()
            raise DatabaseError(detail=ERROR_CREATE_USER)
            
    async def create_with_validation(self, db: AsyncSession, obj_in: UserCreate) -> User:
        """
        创建新用户，附带完整的输入验证
        
        参数:
            db: 数据库会话
            obj_in: 用户创建数据
            
        返回:
            创建的用户对象
            
        抛出:
            ValidationError: 如果输入数据验证失败
            EmailAlreadyRegisteredError: 如果邮箱已存在
            UsernameTakenError: 如果用户名已存在
            DatabaseError: 如果数据库操作失败
        """
        # 验证用户名格式 (3-50个字符，只能包含字母、数字、下划线和连字符)
        if not re.match(r'^[a-zA-Z0-9_-]{3,50}$', obj_in.username):
            raise ValidationError(detail="用户名必须为3-50个字符，只能包含字母、数字、下划线和连字符")
        
        # 验证邮箱格式
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', obj_in.email):
            raise ValidationError(detail="邮箱格式无效")
        
        # 验证密码强度 (至少8个字符)
        if len(obj_in.password) < 8:
            raise ValidationError(detail="密码长度必须至少为8个字符")
        
        # 验证年龄范围 (如果提供)
        if obj_in.age is not None and (obj_in.age < 0 or obj_in.age > 150):
            raise ValidationError(detail="年龄必须在0-150之间")
            
        # 使用基础创建方法完成用户创建
        return await self.create(db, obj_in=obj_in)

    async def update(self, db: AsyncSession, db_obj: User, obj_in: UserUpdate) -> User:
        """更新用户信息"""
        update_data = obj_in.model_dump(exclude_unset=True)
        if update_data.get("password"):
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password
            
        for field, value in update_data.items():
            setattr(db_obj, field, value)
            
        try:
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            await db.rollback()
            raise DatabaseError(detail=ERROR_UPDATE_USER)

    async def delete(self, db: AsyncSession, id: int) -> Optional[User]:
        """删除用户"""
        obj = await self.get(db, id)
        if not obj:
            raise ResourceNotFoundError(detail="用户不存在")
            
        try:
            await db.delete(obj)
            await db.commit()
            return obj
        except IntegrityError:
            await db.rollback()
            raise DatabaseError(detail=ERROR_DELETE_USER)


# 创建CRUDUser的单例实例
user = CRUDUser() 