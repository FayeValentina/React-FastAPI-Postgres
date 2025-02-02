from fastapi import APIRouter, Path, Query, Body, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Annotated, List, Optional, Dict
from datetime import date
import uuid

from app.schemas.validators import (
    AdvancedProduct,
    PaymentInfo,
    AdvancedUser,
    ComplexAddress,
    ProductCategory
)

router = APIRouter()


@router.post(
    "/products/",
    response_model=AdvancedProduct,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "normal": {
                            "summary": "A normal product example",
                            "value": {
                                "id": "550e8400-e29b-4d80-a567-426655440000",
                                "name": "Gaming Laptop",
                                "description": "High performance gaming laptop with RTX 3080",
                                "price": 1999.99,
                                "quantity": 10,
                                "category": "electronics",
                                "tags": ["gaming", "laptop", "rtx"],
                                "website": "https://example.com/product",
                                "secure_code": "secret123",
                                "meta_data": "{\"specs\": {\"cpu\": \"i9\", \"gpu\": \"rtx3080\"}}",
                                "ip_address": "192.168.1.1",
                                "rating": 4.5,
                                "discount": -100.0,
                                "is_active": True
                            }
                        }
                    }
                }
            }
        }
    }
)
async def create_product(
    product: Annotated[AdvancedProduct, Body()]
):
    """
    创建新产品（高级验证示例）

    此端点演示了多种验证方式：
    - UUID格式验证
    - 字符串模式验证
    - 数值范围验证
    - 枚举类型验证
    - URL、IP地址、JSON等特殊类型验证
    """
    return product


@router.post("/payments/validate", status_code=status.HTTP_202_ACCEPTED)
async def validate_payment(
    payment: Annotated[PaymentInfo, Body(
        examples={
            "normal": {
                "summary": "Valid payment info",
                "value": {
                    "card_number": "4532756279624064",
                    "expiry_date": "2025-12-31",
                    "cvv": "123",
                    "amount": 99.99
                }
            }
        }
    )]
):
    """
    验证支付信息
    
    参数说明：
    - payment: 支付信息，包含卡号、过期日期、CVV和金额
    """
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "valid", "payment": payment.model_dump()}
    )


@router.post("/users/advanced", status_code=status.HTTP_201_CREATED)
async def create_advanced_user(
    user: AdvancedUser,
    referral_code: Annotated[Optional[str], Query(
        pattern="^[A-Z]{3}[0-9]{3}$",
        description="推荐码格式：ABC123"
    )] = None
):
    """
    创建高级用户（带复杂验证）
    
    参数说明：
    - user: 用户信息，包含复杂的嵌套对象
    - referral_code: 推荐码，格式为3个大写字母+3个数字
    
    异常：
    - 400: 缺少推荐码
    """
    if not referral_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Referral code is required",
            headers={"X-Error-Code": "USER_NO_REFERRAL"}
        )
    return {
        "user": user,
        "referral_code": referral_code
    }


@router.put("/users/{user_id}/address/{address_type}", responses={
    status.HTTP_200_OK: {
        "description": "地址更新成功",
        "content": {
            "application/json": {
                "example": {"status": "success", "message": "Address updated"}
            }
        }
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "用户未找到",
        "content": {
            "application/json": {
                "example": {"detail": "User not found"}
            }
        }
    }
})
async def update_user_address(
    user_id: uuid.UUID,
    address_type: Annotated[str, Path(pattern="^(home|work|other)$")],
    address: ComplexAddress
):
    """
    更新用户地址信息
    
    参数说明：
    - user_id: 用户UUID
    - address_type: 地址类型（home/work/other）
    - address: 详细地址信息，包含坐标验证
    
    异常：
    - 404: 用户不存在
    """
    if str(user_id) == "00000000-0000-0000-0000-000000000000":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return {
        "user_id": user_id,
        "address_type": address_type,
        "address": address
    }


@router.get("/products/by-category/{category}")
async def get_products_by_category(
    category: ProductCategory,
    min_price: Annotated[float, Query(gt=0)] = 0.0,
    max_price: Annotated[float, Query(gt=0)] = 1000000.0,
    tags: Annotated[List[str], Query(min_length=1, max_length=5)] = []
):
    """
    按类别获取产品列表
    
    参数说明：
    - category: 产品类别（electronics/clothing/books）
    - min_price: 最低价格，必须大于0
    - max_price: 最高价格，必须大于0
    - tags: 标签列表，1-5个标签
    
    异常：
    - 400: 价格范围无效
    """
    if min_price >= max_price:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": "INVALID_PRICE_RANGE",
                "message": "min_price must be less than max_price",
                "details": {
                    "min_price": min_price,
                    "max_price": max_price
                }
            }
        )
    
    return {
        "category": category,
        "price_range": {"min": min_price, "max": max_price},
        "tags": tags
    } 