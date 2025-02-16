from fastapi import APIRouter, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Annotated, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.schemas import ItemCreate, ItemResponse, ProductUpdateFull, ProductUpdatePartial

router = APIRouter(prefix="/products", tags=["products"])

# 模拟商品数据
MOCK_PRODUCT = {
    "name": "Gaming Laptop",
    "description": "High performance gaming laptop",
    "price": 1299.99,
    "stock": 10,
    "category": "electronics",
    "tags": ["gaming", "laptop", "electronics"],
    "is_available": True
}

@router.get("/{product_id}")
async def get_product(
    product_id: Annotated[int, Path(title="Product ID", ge=1)],
    q: Annotated[Optional[str], Query(min_length=3, max_length=50)] = None,
):
    """获取商品详情"""
    return {
        "product_id": product_id,
        "query": q,
        **MOCK_PRODUCT
    }

@router.post("", response_model=ItemResponse)
async def create_product(item: ItemCreate):
    """创建新商品"""
    created_item = {
        "id": 1,
        **jsonable_encoder(item),
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    return JSONResponse(content=jsonable_encoder(created_item), status_code=status.HTTP_201_CREATED)

@router.put("/{product_id}")
async def update_product_full(product_id: int, product_update: ProductUpdateFull) -> Dict:
    """完整更新商品信息"""
    if product_id != 1:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = jsonable_encoder(product_update)
    updated_product = {
        "id": product_id,
        **update_data,
        "updated_at": datetime.now()
    }
    
    return JSONResponse(
        content=jsonable_encoder(updated_product),
        status_code=status.HTTP_200_OK
    )

@router.patch("/{product_id}")
async def update_product_partial(product_id: int, product_update: ProductUpdatePartial) -> Dict:
    """部分更新商品信息"""
    if product_id != 1:
        raise HTTPException(status_code=404, detail="Product not found")
    
    current_product = MOCK_PRODUCT.copy()
    update_data = jsonable_encoder(product_update, exclude_unset=True)
    
    for field, value in update_data.items():
        if value is not None:
            current_product[field] = value
    
    updated_product = {
        "id": product_id,
        **current_product,
        "updated_at": datetime.now()
    }
    
    return JSONResponse(
        content=jsonable_encoder(updated_product),
        status_code=status.HTTP_200_OK
    ) 