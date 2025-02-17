# 导入必要的模块
from pydantic import BaseModel, EmailStr, Field
from typing import Dict, Optional, List
from datetime import datetime

from .common import ComplexAddress

# 用户基础模型
class UserBase(BaseModel):
    """用户基础信息"""
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True
    is_superuser: bool = False
    full_name: Optional[str] = None
    username: Optional[str] = None


# 用户创建模型
class UserCreate(UserBase):
    """创建用户时的模型"""
    email: EmailStr
    password: str
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")


# 用户更新模型
class UserUpdate(BaseModel):
    """更新用户时的模型"""
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None


# 用户更新基础模型
class UserUpdateBase(BaseModel):
    """用户更新的基础字段"""
    username: str
    email: EmailStr
    full_name: str
    age: int
    is_active: bool
    preferences: Dict[str, str]

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "full_name": "John Doe",
                "age": 30,
                "is_active": True,
                "preferences": {
                    "theme": "dark",
                    "language": "en"
                }
            }
        }
    }


# 用户更新完整信息模型
class UserUpdateFull(UserUpdateBase):
    """完整更新用户信息的模型"""
    pass


# 用户部分更新模型
class UserUpdatePartial(BaseModel):
    """部分更新用户信息的模型"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    age: Optional[int] = None
    is_active: Optional[bool] = None
    preferences: Optional[Dict[str, str]] = None

    model_config = UserUpdateBase.model_config


# 用户资料模型
class UserProfile(BaseModel):
    """用户资料模型"""
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    interests: List[str] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "full_name": "John Doe",
                "interests": ["coding", "reading"]
            }
        }
    }


# 用户响应模型
class UserResponse(UserBase):
    """用户信息响应模型"""
    id: int                # 用户ID
    created_at: datetime   # 创建时间
    updated_at: datetime   # 更新时间

    # 配置模型，允许从ORM模型创建
    model_config = {"from_attributes": True}


# 高级用户模型
class AdvancedUser(BaseModel):
    """高级用户模型，包含更多验证规则"""
    username: str = Field(..., pattern="^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        description="Must contain at least one uppercase letter, one lowercase letter, one number and one special character"
    )
    birth_date: datetime
    addresses: Dict[str, ComplexAddress]
    social_media: Dict[str, str]
    preferences: Dict[str, str] = Field(default_factory=dict)
    interests: List[str] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "password": "StrongP@ss1",
                "birth_date": "1990-01-01",
                "addresses": {
                    "home": {
                        "street": "123 Main St",
                        "city": "New York",
                        "country": "USA",
                        "postal_code": "10001",
                        "coordinates": [40.7128, -74.0060]
                    }
                },
                "social_media": {
                    "twitter": "https://twitter.com/johndoe",
                    "linkedin": "https://linkedin.com/in/johndoe"
                },
                "interests": ["coding", "reading"]
            }
        }
    }


class UserInDBBase(UserBase):
    id: Optional[int] = None

    class Config:
        from_attributes = True


class User(UserInDBBase):
    pass


class UserInDB(UserInDBBase):
    hashed_password: str 