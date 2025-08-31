# 导入必要的模块
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from app.utils.cache_serializer import register_pydantic_model


# 用户基础模型
class UserBase(BaseModel):
    """用户基础信息"""
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True
    is_superuser: bool = False
    full_name: Optional[str] = None
    username: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=150)


# 用户创建模型
class UserCreate(UserBase):
    """创建用户时的模型"""
    email: EmailStr
    password: str
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    age: Optional[int] = Field(None, ge=0, le=150)


# 用户更新模型（统一的更新模型，支持部分更新）
class UserUpdate(BaseModel):
    """更新用户时的模型"""
    username: Optional[str] = Field(None, min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None


# 用户响应模型
@register_pydantic_model
class UserResponse(UserBase):
    """用户信息响应模型"""
    id: int                # 用户ID
    created_at: datetime   # 创建时间
    updated_at: datetime   # 更新时间

    # 配置模型，允许从ORM模型创建
    model_config = {"from_attributes": True}


# 简化的用户模型（用于认证返回）
@register_pydantic_model
class User(BaseModel):
    """简化的用户模型"""
    id: int
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    age: Optional[int] = None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}