from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Annotated, Dict, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import (
    UserCreate, UserResponse, UserUpdateFull, UserUpdatePartial
)
from app.crud import user as user_crud
from app.dependencies.db import get_db

router = APIRouter(prefix="/users", tags=["users"])

# 模拟数据库中的用户数据
MOCK_USER = {
    "username": "john_doe",
    "email": "john@example.com",
    "full_name": "John Doe",
    "age": 30,
    "is_active": True,
    "preferences": {
        "theme": "dark",
        "language": "en"
    }
}

@router.post("", response_model=UserResponse)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """创建新用户"""
    try:
        user = await user_crud.create_user(db, user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{user_id}")
async def update_user_full(user_id: int, user_update: UserUpdateFull) -> Dict:
    """完整更新用户信息"""
    if user_id != 1:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = jsonable_encoder(user_update)
    updated_user = {
        "id": user_id,
        **update_data,
        "updated_at": datetime.now()
    }
    
    return JSONResponse(
        content=jsonable_encoder(updated_user),
        status_code=status.HTTP_200_OK
    )

@router.patch("/{user_id}")
async def update_user_partial(user_id: int, user_update: UserUpdatePartial) -> Dict:
    """部分更新用户信息"""
    if user_id != 1:
        raise HTTPException(status_code=404, detail="User not found")
    
    current_user = MOCK_USER.copy()
    update_data = jsonable_encoder(user_update, exclude_unset=True)
    
    for field, value in update_data.items():
        if value is not None:
            current_user[field] = value
    
    updated_user = {
        "id": user_id,
        **current_user,
        "updated_at": datetime.now()
    }
    
    return JSONResponse(
        content=jsonable_encoder(updated_user),
        status_code=status.HTTP_200_OK
    )

@router.get("")
async def get_users(
    name: Annotated[str | None, Query(min_length=2, description="用户名")] = None,
    age: Annotated[int | None, Query(ge=0, le=150, description="年龄")] = None,
    sort_by: Annotated[List[str], Query(description="排序字段")] = ["created_at"]
) -> Dict:
    """获取用户列表"""
    return {
        "name": name,
        "age": age,
        "sort_by": sort_by
    } 