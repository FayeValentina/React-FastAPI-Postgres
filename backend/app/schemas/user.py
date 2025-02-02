# 导入必要的模块
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# 用户基础模型
class UserBase(BaseModel):
    email: EmailStr           # 电子邮件地址，会自动验证格式
    username: str            # 用户名
    full_name: Optional[str] = None  # 全名，可选字段
    is_active: bool = True    # 用户是否激活，默认为True
    is_superuser: bool = False  # 是否为超级用户，默认为False


# 用户创建请求模型
class UserCreate(UserBase):
    password: str  # 用户密码，创建时必需


# 用户响应模型
class UserResponse(UserBase):
    id: int                # 用户ID
    created_at: datetime   # 创建时间
    updated_at: datetime   # 更新时间

    # 配置模型，允许从ORM模型创建
    model_config = {"from_attributes": True} 