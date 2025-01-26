from fastapi import APIRouter, Path, Query, Body, Form, Cookie, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Annotated, List, Optional
from datetime import datetime

from app.schemas.example import (
    ItemCreate,
    ItemResponse,
    UserProfile,
    UserLevel,
    Address
)

router = APIRouter()


@router.get("/items/{item_id}")
async def get_item(
    item_id: Annotated[int, Path(title="Item ID", ge=1)],
    q: Annotated[Optional[str], Query(min_length=3, max_length=50)] = None,
    user_agent: Annotated[str | None, Header()] = None
):
    """
    Get item by ID with optional query parameter and header
    """
    return {
        "item_id": item_id,
        "q": q,
        "user_agent": user_agent
    }


@router.post("/items/", response_model=ItemResponse)
async def create_item(
    item: Annotated[ItemCreate, Body(
        examples={
            "normal": {
                "summary": "A normal example",
                "value": {
                    "name": "Foo",
                    "description": "A very nice Item",
                    "price": 35.4,
                    "tax": 0.2,
                    "tags": ["tag1", "tag2"],
                    "category": "category1"
                }
            }
        }
    )],
    x_token: Annotated[str | None, Header()] = None
):
    """
    Create a new item with body validation
    """
    if not x_token:
        raise HTTPException(status_code=400, detail="X-Token header is required")
    
    # Simulate database response
    return {
        **item.model_dump(),
        "id": 1,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }


@router.post("/login/")
async def login(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    remember_me: Annotated[bool, Cookie()] = False
):
    """
    Login endpoint demonstrating Form and Cookie parameters
    """
    return {
        "username": username,
        "remember_me": remember_me
    }


@router.post("/users/profile")
async def create_profile(
    profile: UserProfile,
    address: Annotated[Address, Body()],
    priority: Annotated[int, Query(gt=0, le=5)] = 1,
    api_key: Annotated[str | None, Header()] = None
):
    """
    Create user profile with nested models and multiple parameters
    """
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")
    
    return {
        "profile": profile,
        "address": address,
        "priority": priority
    }


@router.get("/users/levels/{level}")
async def get_users_by_level(
    level: UserLevel,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0
):
    """
    Get users by level using enum
    """
    return {
        "level": level,
        "limit": limit,
        "offset": offset
    }


# Custom response with headers
@router.get("/custom-header")
async def get_custom_header():
    content = {"message": "Hello World"}
    headers = {"X-Custom-Header": "custom_value", "X-Another-Header": "another_value"}
    return JSONResponse(content=content, headers=headers)


# Multiple body parameters
@router.put("/items/{item_id}")
async def update_item(
    item_id: int,
    item: Annotated[ItemCreate, Body(embed=True)],
    user: Annotated[UserProfile, Body(embed=True)],
    importance: Annotated[int, Body(gt=0, lt=10)]
):
    """
    Update item with multiple body parameters
    """
    return {
        "item_id": item_id,
        "item": item,
        "user": user,
        "importance": importance
    } 