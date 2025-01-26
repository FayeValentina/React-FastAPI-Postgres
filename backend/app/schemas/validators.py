from pydantic import (
    BaseModel,
    Field,
    EmailStr,
    HttpUrl,
    constr,
    conint,
    confloat,
    conlist,
    validator,
    field_validator,
    model_validator,
    AnyUrl,
    PaymentCardNumber,
    StringConstraints,
    Json,
    SecretStr,
    IPvAnyAddress,
    NegativeFloat,
    PositiveInt,
    StrictBool,
    UUID4
)
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, date
from enum import Enum
import re


class ProductCategory(str, Enum):
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    BOOKS = "books"


class AdvancedProduct(BaseModel):
    id: UUID4  # UUID4 格式验证
    name: str = Field(..., pattern="^[a-zA-Z0-9\s-]+$")  # 正则表达式验证
    description: str = Field(..., min_length=10, max_length=1000)
    price: confloat(gt=0, lt=1000000)  # type: ignore # 浮点数范围验证
    quantity: PositiveInt  # 正整数验证
    category: ProductCategory
    tags: Set[str] = Field(default_factory=set)  # 使用 Set 来确保唯一性
    website: Optional[HttpUrl] = None  # URL 格式验证
    secure_code: SecretStr  # 敏感数据处理
    meta_data: Json  # JSON 字符串验证
    ip_address: Optional[IPvAnyAddress] = None  # IP 地址验证
    rating: confloat(ge=0, le=5)  # type: ignore # 评分范围验证
    discount: Optional[NegativeFloat] = None  # 负数验证
    is_active: StrictBool  # 严格布尔值验证

    @field_validator('name')
    def name_must_not_contain_special_chars(cls, v):
        if not re.match("^[a-zA-Z0-9\s-]+$", v):
            raise ValueError('Name must not contain special characters')
        return v.title()

    @model_validator(mode='before')
    def check_card_credentials(cls, values):
        """验证整个模型的数据"""
        if 'price' in values and 'discount' in values and values['discount']:
            if abs(values['discount']) >= values['price']:
                raise ValueError('Discount cannot be greater than price')
        return values


class PaymentInfo(BaseModel):
    card_number: PaymentCardNumber  # 信用卡号验证
    expiry_date: date
    cvv: constr(min_length=3, max_length=4)  # type: ignore
    amount: confloat(gt=0)  # type: ignore


class ComplexAddress(BaseModel):
    street: str = Field(..., min_length=5)
    city: str
    country: str
    postal_code: str = Field(..., pattern="^[0-9]{5,6}$")
    coordinates: tuple[float, float] = Field(..., description="经纬度坐标")

    @field_validator('coordinates')
    def validate_coordinates(cls, v):
        lat, lon = v
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            raise ValueError('Invalid coordinates')
        return v


class AdvancedUser(BaseModel):
    username: str = Field(..., pattern="^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        description="Must contain at least one uppercase letter, one lowercase letter, one number and one special character"
    )
    birth_date: date
    addresses: Dict[str, ComplexAddress]  # 复杂嵌套验证
    social_media: Dict[str, AnyUrl]  # 字典值URL验证
    preferences: Dict[str, Any] = Field(default_factory=dict)
    interests: Set[str] = Field(default_factory=set)  # 使用 Set 替代 List + unique_items

    @field_validator('password')
    def validate_password(cls, v):
        if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$", v):
            raise ValueError(
                'Password must contain at least one uppercase letter, '
                'one lowercase letter, one number and one special character'
            )
        return v

    @field_validator('birth_date')
    def validate_birth_date(cls, v):
        if v > date.today():
            raise ValueError('Birth date cannot be in the future')
        return v

    class Config:
        json_schema_extra = {
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