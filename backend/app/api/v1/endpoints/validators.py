from fastapi import APIRouter, Path, Query, Body, HTTPException, Depends
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


@router.post("/products/", response_model=AdvancedProduct)
async def create_product(
    product: Annotated[AdvancedProduct, Body(
        examples={
            "normal": {
                "summary": "A normal product example",
                "value": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
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
    )]
):
    """
    Create a new product with advanced validation
    """
    return product


@router.post("/payments/validate")
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
    Validate payment information
    """
    return {"status": "valid", "payment": payment}


@router.post("/users/advanced")
async def create_advanced_user(
    user: AdvancedUser,
    referral_code: Annotated[Optional[str], Query(
        pattern="^[A-Z]{3}[0-9]{3}$",
        description="Referral code in format ABC123"
    )] = None
):
    """
    Create a new user with advanced validation and complex nested objects
    """
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
    """
    Update user address with coordinate validation
    """
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
    Get products by category with price range and tags validation
    """
    if min_price >= max_price:
        raise HTTPException(
            status_code=400,
            detail="min_price must be less than max_price"
        )
    
    return {
        "category": category,
        "price_range": {"min": min_price, "max": max_price},
        "tags": tags
    } 