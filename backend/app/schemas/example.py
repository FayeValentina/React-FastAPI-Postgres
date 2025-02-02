from pydantic import BaseModel, Field, EmailStr, constr, conint, field_validator
from typing import List, Optional, Set, Dict
from datetime import datetime
from enum import Enum


# 用户等级枚举类型
class UserLevel(str, Enum):
    BEGINNER = "beginner"      # 初级用户
    INTERMEDIATE = "intermediate"  # 中级用户
    EXPERT = "expert"          # 专家用户


# 地址模型
class Address(BaseModel):
    street: str = Field(..., min_length=5, max_length=100)  # 街道地址，长度5-100
    city: str = Field(..., example="Beijing")               # 城市
    country: str = Field(..., example="China")              # 国家
    postal_code: str = Field(..., pattern="^[0-9]{6}$")     # 邮政编码，6位数字


# 商品基础模型
class ItemBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, description="Item name")  # 商品名称，长度3-50
    description: Optional[str] = Field(None, max_length=1000)  # 商品描述，可选，最大长度1000
    price: float = Field(..., gt=0, description="Item price must be greater than zero")  # 价格，必须大于0
    tax: Optional[float] = Field(None, ge=0, le=0.4)  # 税率，可选，0-0.4之间
    tags: List[str] = Field(default_factory=list, max_items=5)  # 标签列表，最多5个

    @field_validator("price")
    def validate_price(cls, v):
        # 验证价格不能超过100万
        if v > 1000000:
            raise ValueError("Price cannot be greater than 1,000,000")
        return round(v, 2)  # 保留两位小数


# 创建商品模型，继承自ItemBase
class ItemCreate(ItemBase):
    category: str = Field(..., min_length=3)  # 商品类别，最小长度3


# 商品响应模型，继承自ItemBase
class ItemResponse(ItemBase):
    id: int                # 商品ID
    created_at: datetime   # 创建时间
    updated_at: datetime   # 更新时间

    model_config = {"from_attributes": True}  # 允许从ORM模型创建


# 用户基础模型
class UserBase(BaseModel):
    email: EmailStr           # 电子邮件
    username: str            # 用户名
    full_name: Optional[str] = None  # 全名，可选
    is_active: bool = True    # 是否激活
    is_superuser: bool = False  # 是否超级用户


# 创建用户模型
class UserCreate(UserBase):
    password: str  # 密码


# 用户资料模型
class UserProfile(BaseModel):
    username: str            # 用户名
    email: EmailStr          # 电子邮件
    full_name: Optional[str] = None  # 全名，可选
    interests: Set[str] = Field(default_factory=set)  # 兴趣爱好集合

    # 模型配置，包含示例数据
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
    id: int                # 用户ID
    created_at: datetime   # 创建时间
    updated_at: datetime   # 更新时间

    model_config = {"from_attributes": True}


# 会话响应模型
class SessionResponse(BaseModel):
    message: str      # 消息
    session_id: str   # 会话ID


# 偏好设置响应模型
class PreferencesResponse(BaseModel):
    preferences: Dict[str, str | bool]  # 偏好设置字典
    message: str                        # 消息


# 主题偏好响应模型
class ThemePreferenceResponse(BaseModel):
    theme: str    # 主题
    message: str  # 消息


# 登录响应模型
class LoginResponse(BaseModel):
    message: str     # 消息
    user_id: int     # 用户ID
    session_id: str  # 会话ID


# 用户等级响应模型
class UserLevelResponse(BaseModel):
    level: UserLevel  # 用户等级
    limit: int       # 限制数量
    offset: int      # 偏移量


# 登录请求模型
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)  # 用户名，长度3-50
    password: str = Field(..., min_length=6)                 # 密码，最小长度6
    remember_me: bool = False                                # 记住我选项


# 登录表单响应模型
class LoginFormResponse(BaseModel):
    username: str                           # 用户名
    remember_me: bool                       # 记住我选项
    message: str = "Login successful"       # 登录成功消息

    model_config = {"from_attributes": True}


# 文件上传响应模型
class FileUploadResponse(BaseModel):
    filename: str                           # 文件名
    content_type: str                       # 文件类型
    file_size: int                          # 文件大小
    description: Optional[str] = None       # 文件描述，可选
    tags: List[str] = Field(default_factory=list)  # 标签列表
    
    # 模型配置，包含示例数据
    model_config = {
        "json_schema_extra": {
            "example": {
                "filename": "test.pdf",
                "content_type": "application/pdf",
                "file_size": 1024,
                "description": "Test document",
                "tags": ["document", "test"]
            }
        }
    }


# 多文件上传响应模型
class MultipleFilesResponse(BaseModel):
    file_sizes: List[int]  # 文件大小列表
    fileb_size: int        # 单个文件大小
    message: str           # 消息
    total_size: int        # 总大小


# 带元数据的文件上传响应模型
class FileWithMetadataResponse(BaseModel):
    filename: str                     # 文件名
    content_type: str                 # 文件类型
    description: Optional[str] = None  # 文件描述，可选
    file_size: int                    # 文件大小
    first_bytes: str                  # 文件前几个字节的十六进制表示
    message: str                      # 消息 