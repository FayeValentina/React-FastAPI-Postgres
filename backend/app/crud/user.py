from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import Optional

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash


# Error messages
ERROR_EMAIL_REGISTERED = "Email already registered"
ERROR_USERNAME_TAKEN = "Username already taken"
ERROR_CREATE_USER = "Error creating user"
ERROR_UPDATE_USER = "Error updating user"
ERROR_DELETE_USER = "Error deleting user"


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
        """创建新用户"""
        # Check if email or username already exists
        if await self.get_by_email(db, obj_in.email):
            raise ValueError(ERROR_EMAIL_REGISTERED)
        if await self.get_by_username(db, obj_in.username):
            raise ValueError(ERROR_USERNAME_TAKEN)

        try:
            db_obj = User(
                email=obj_in.email,
                username=obj_in.username,
                hashed_password=get_password_hash(obj_in.password),
                full_name=obj_in.full_name,
                is_active=True,
                is_superuser=obj_in.is_superuser,
            )
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            await db.rollback()
            raise ValueError(ERROR_CREATE_USER)

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
            raise ValueError(ERROR_UPDATE_USER)

    async def delete(self, db: AsyncSession, id: int) -> Optional[User]:
        """删除用户"""
        obj = await self.get(db, id)
        if obj:
            try:
                await db.delete(obj)
                await db.commit()
            except IntegrityError:
                await db.rollback()
                raise ValueError(ERROR_DELETE_USER)
        return obj


# Create a single instance of CRUDUser
user = CRUDUser() 