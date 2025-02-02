from pydantic import (
    BaseModel,
    Field,
    EmailStr,
    HttpUrl,
    field_validator,
    model_validator,
    AnyUrl,
    Json,
    SecretStr,
    IPvAnyAddress,
    NegativeFloat,
    PositiveInt,
    StrictBool,
    UUID4
)
from pydantic_extra_types.payment import PaymentCardNumber
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, date
from enum import Enum
import re


# 产品类别枚举
class ProductCategory(str, Enum):
    ELECTRONICS = "electronics"  # 电子产品
    CLOTHING = "clothing"      # 服装
    BOOKS = "books"           # 图书


# 高级产品模型，包含多种验证
class AdvancedProduct(BaseModel):
    id: UUID4                # 产品唯一标识符，UUID格式
    name: str = Field(..., pattern="^[a-zA-Z0-9\s-]+$")  # 产品名称，只允许字母、数字、空格和连字符
    description: str = Field(..., min_length=10, max_length=1000)  # 产品描述，10-1000字符
    price: float = Field(..., gt=0, lt=1000000)  # 价格，必须大于0小于100万
    quantity: PositiveInt    # 数量，必须为正整数
    category: ProductCategory  # 产品类别，使用枚举类型
    tags: Set[str] = Field(default_factory=set)  # 标签集合，自动去重
    website: Optional[HttpUrl] = None  # 产品网站URL，可选
    secure_code: SecretStr   # 安全码，在响应中会被隐藏
    meta_data: Json         # 元数据，必须是有效的JSON字符串
    ip_address: Optional[IPvAnyAddress] = None  # IP地址，可选
    rating: float = Field(..., ge=0, le=5)  # 评分，0-5之间
    discount: Optional[NegativeFloat] = None  # 折扣金额，必须为负数
    is_active: StrictBool   # 是否激活，严格布尔值验证

    @field_validator('name')
    def name_must_not_contain_special_chars(cls, v):
        """验证产品名称不包含特殊字符"""
        if not re.match("^[a-zA-Z0-9\s-]+$", v):
            raise ValueError('Name must not contain special characters')
        return v.title()

    @model_validator(mode='before')
    def check_card_credentials(cls, values):
        """验证折扣不能大于价格"""
        if 'price' in values and 'discount' in values and values['discount']:
            if abs(values['discount']) >= values['price']:
                raise ValueError('Discount cannot be greater than price')
        return values


# 支付信息模型
class PaymentInfo(BaseModel):
    card_number: PaymentCardNumber  # 支付卡号，自动验证格式
    expiry_date: date              # 过期日期
    cvv: str = Field(..., min_length=3, max_length=4)  # 安全码，3-4位
    amount: float = Field(..., gt=0)  # 支付金额，必须大于0


# 复杂地址模型
class ComplexAddress(BaseModel):
    street: str = Field(..., min_length=5)  # 街道地址，最少5个字符
    city: str                              # 城市
    country: str                           # 国家
    postal_code: str = Field(..., pattern="^[0-9]{5,6}$")  # 邮政编码，5-6位数字
    coordinates: tuple[float, float] = Field(..., description="经纬度坐标")  # 地理坐标

    @field_validator('coordinates')
    def validate_coordinates(cls, v):
        """验证经纬度坐标是否有效"""
        lat, lon = v
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            raise ValueError('Invalid coordinates')
        return v


# 高级用户模型
class AdvancedUser(BaseModel):
    username: str = Field(..., pattern="^[a-zA-Z0-9_-]+$")  # 用户名，只允许字母、数字、下划线和连字符
    email: EmailStr          # 电子邮件地址
    password: str = Field(   # 密码，带有复杂的验证规则
        ...,
        min_length=8,
        description="Must contain at least one uppercase letter, one lowercase letter, one number and one special character"
    )
    birth_date: date        # 出生日期
    addresses: Dict[str, ComplexAddress]  # 地址字典，键为地址类型，值为地址对象
    social_media: Dict[str, AnyUrl]  # 社交媒体链接字典
    preferences: Dict[str, Any] = Field(default_factory=dict)  # 用户偏好设置
    interests: Set[str] = Field(default_factory=set)  # 兴趣爱好集合

    @field_validator('password')
    def validate_password(cls, v):
        """验证密码复杂度"""
        if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$", v):
            raise ValueError(
                'Password must contain at least one uppercase letter, '
                'one lowercase letter, one number and one special character'
            )
        return v

    @field_validator('birth_date')
    def validate_birth_date(cls, v):
        """验证出生日期不能在未来"""
        if v > date.today():
            raise ValueError('Birth date cannot be in the future')
        return v

    # 模型配置，包含示例数据
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
        }} 