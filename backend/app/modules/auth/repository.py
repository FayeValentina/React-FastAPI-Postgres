from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.exc import IntegrityError
from typing import Optional
import re

from app.modules.auth.models import User, PasswordReset
from app.modules.auth.schemas import UserCreate, UserUpdate
from app.core.security import get_password_hash
from app.core.exceptions import (
    EmailAlreadyRegisteredError, 
    UsernameTakenError,
    DatabaseError,
    ResourceNotFoundError,
    ValidationError
)

from datetime import timedelta
from uuid import uuid4
from app.infrastructure.utils.common import get_current_time



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

class CRUDPasswordReset:
    async def create(
        self, 
        db: AsyncSession, 
        user_id: int,
        expires_in_hours: int = 1
    ) -> PasswordReset:
        """创建新的密码重置令牌"""
        # 先将该用户的所有未使用令牌标记为已使用（确保一次只有一个有效令牌）
        await self.invalidate_user_tokens(db, user_id)
        
        # 生成新令牌
        token = str(uuid4())
        reset_token = PasswordReset.create(
            user_id=user_id,
            token=token,
            expires_in_hours=expires_in_hours
        )
        
        db.add(reset_token)
        await db.commit()
        await db.refresh(reset_token)
        return reset_token
    
    async def get_by_token(
        self, 
        db: AsyncSession, 
        token: str
    ) -> Optional[PasswordReset]:
        """通过令牌获取密码重置记录"""
        result = await db.execute(
            select(PasswordReset).where(PasswordReset.token == token)
        )
        return result.scalar_one_or_none()
    
    async def use_token(
        self, 
        db: AsyncSession, 
        token: str
    ) -> bool:
        """使用密码重置令牌"""
        result = await db.execute(
            update(PasswordReset)
            .where(PasswordReset.token == token)
            .values(
                is_used=True,
                used_at=get_current_time()
            )
        )
        await db.commit()
        return result.rowcount > 0
    
    async def invalidate_user_tokens(
        self, 
        db: AsyncSession, 
        user_id: int
    ) -> int:
        """使用户的所有未使用令牌失效"""
        result = await db.execute(
            update(PasswordReset)
            .where(
                PasswordReset.user_id == user_id,
                PasswordReset.is_used.is_(False)
            )
            .values(
                is_used=True,
                used_at=get_current_time()
            )
        )
        await db.commit()
        return result.rowcount
    
    async def cleanup_expired(self, db: AsyncSession, days_old: int = 7) -> int:
        """
        删除创建时间早于指定天数且已失效的密码重置令牌。
        
        删除条件：
        1. 创建时间早于 days_old 天前
        2. is_valid 为 False (已使用或已过期)
        """
        # 计算时间阈值
        creation_date_threshold = get_current_time() - timedelta(days=days_old)
        current_time = get_current_time()
        
        # 定义失效条件 (is_valid == False)
        # 条件1: 令牌已使用 (is_used == True)
        # 条件2: 令牌已过期 (expires_at < 当前时间)
        is_invalid_condition = (
            (PasswordReset.is_used.is_(True)) |
            (PasswordReset.expires_at < current_time)
        )

        # 定义旧记录条件
        is_old_condition = PasswordReset.created_at < creation_date_threshold

        # 执行删除：删除既旧又失效的令牌
        statement = delete(PasswordReset).where(
            and_(
                is_old_condition,
                is_invalid_condition
            )
        )
        
        result = await db.execute(statement)
        return result.rowcount
    
# 创建CRUDUser的单例实例
crud_user = CRUDUser() 
crud_password_reset = CRUDPasswordReset()
