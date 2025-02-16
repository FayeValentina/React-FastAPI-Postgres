from pydantic import BaseModel, Field, UUID4, HttpUrl, Json, IPvAnyAddress, field_validator
from typing import List, Optional, Set
from enum import Enum
from datetime import datetime

# 产品类别枚举
class ProductCategory(str, Enum):
    ELECTRONICS = "electronics"  # 电子产品
    CLOTHING = "clothing"      # 服装
    BOOKS = "books"           # 图书

# 商品基础模型
class ItemBase(BaseModel):
    """商品基础信息"""
    name: str = Field(..., min_length=3, max_length=50, description="Item name")
    description: Optional[str] = Field(None, max_length=1000)
    price: float = Field(..., gt=0, description="Item price must be greater than zero")
    tax: Optional[float] = Field(None, ge=0, le=0.4)
    tags: List[str] = Field(default_factory=list, max_items=5)

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v > 1000000:
            raise ValueError("Price cannot be greater than 1,000,000")
        return round(v, 2)

# 创建商品模型
class ItemCreate(ItemBase):
    """创建商品时的模型"""
    category: str = Field(..., min_length=3)

# 商品响应模型
class ItemResponse(ItemBase):
    """商品信息响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

# 商品更新完整信息模型
class ProductUpdateFull(BaseModel):
    """完整更新商品信息的模型"""
    name: str
    description: str
    price: float
    stock: int
    category: str
    tags: List[str]
    is_available: bool

# 商品部分更新模型
class ProductUpdatePartial(BaseModel):
    """部分更新商品信息的模型"""
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_available: Optional[bool] = None

# 高级商品模型（从validators.py移动）
class AdvancedProduct(BaseModel):
    """高级商品模型，包含更多验证规则"""
    id: UUID4
    name: str = Field(..., pattern="^[a-zA-Z0-9\s-]+$")
    description: str = Field(..., min_length=10, max_length=1000)
    price: float = Field(..., gt=0, lt=1000000)
    quantity: int = Field(..., gt=0)
    category: ProductCategory
    tags: Set[str] = Field(default_factory=set)
    website: Optional[HttpUrl] = None
    meta_data: Json
    ip_address: Optional[IPvAnyAddress] = None
    rating: float = Field(..., ge=0, le=5)
    discount: Optional[float] = None
    is_active: bool

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-4d80-a567-426655440000",
                "name": "Gaming Laptop",
                "description": "High performance gaming laptop with RTX 3080",
                "price": 1999.99,
                "quantity": 10,
                "category": "electronics",
                "tags": ["gaming", "laptop", "rtx"],
                "website": "https://example.com/product",
                "meta_data": "{\"specs\": {\"cpu\": \"i9\", \"gpu\": \"rtx3080\"}}",
                "ip_address": "192.168.1.1",
                "rating": 4.5,
                "discount": -100.0,
                "is_active": True
            }
        }
    } 