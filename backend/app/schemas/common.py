from pydantic import BaseModel, Field
from typing import Tuple

# 地址模型
class Address(BaseModel):
    """基础地址模型"""
    street: str = Field(..., min_length=5, max_length=100)
    city: str = Field(..., example="Beijing")
    country: str = Field(..., example="China")
    postal_code: str = Field(..., pattern="^[0-9]{6}$")

# 复杂地址模型（从validators.py移动）
class ComplexAddress(BaseModel):
    """复杂地址模型，包含更多验证规则"""
    street: str = Field(..., min_length=5)
    city: str
    country: str
    postal_code: str = Field(..., pattern="^[0-9]{5,6}$")
    coordinates: Tuple[float, float] = Field(..., description="经纬度坐标")

    model_config = {
        "json_schema_extra": {
            "example": {
                "street": "123 Main St",
                "city": "New York",
                "country": "USA",
                "postal_code": "10001",
                "coordinates": [40.7128, -74.0060]
            }
        }
    } 