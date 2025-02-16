from fastapi import APIRouter, HTTPException, Path, Query, Body, status
from fastapi.responses import JSONResponse
from typing import Annotated, List
import uuid

from app.schemas import (
    AdvancedProduct,
    PaymentInfo,
    AdvancedUser,
    ComplexAddress,
    ProductCategory
)

router = APIRouter(prefix="/validators", tags=["validators"])

@router.post(
    "/products",
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
async def create_product(product: AdvancedProduct):
    """创建新产品（高级验证示例）"""
    return product

@router.post("/payments/validate", status_code=status.HTTP_202_ACCEPTED)
async def validate_payment(payment: PaymentInfo):
    """验证支付信息"""
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "valid", "payment": payment.model_dump()}
    )

@router.post("/users/advanced", status_code=status.HTTP_201_CREATED)
async def create_advanced_user(
    user: AdvancedUser,
    referral_code: Annotated[str | None, Query(
        pattern="^[A-Z]{3}[0-9]{3}$",
        description="推荐码格式：ABC123"
    )] = None
):
    """创建高级用户（带复杂验证）"""
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

@router.put("/users/{user_id}/address/{address_type}")
async def update_user_address(
    user_id: uuid.UUID,
    address_type: Annotated[str, Path(pattern="^(home|work|other)$")],
    address: ComplexAddress
):
    """更新用户地址信息"""
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
    """按类别获取产品列表"""
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