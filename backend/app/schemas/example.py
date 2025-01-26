from pydantic import BaseModel, Field, EmailStr, constr, conint, validator
from typing import List, Optional, Set
from datetime import datetime
from enum import Enum


class UserLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class Address(BaseModel):
    street: str = Field(..., min_length=5, max_length=100)
    city: str = Field(..., example="Beijing")
    country: str = Field(..., example="China")
    postal_code: str = Field(..., pattern="^[0-9]{6}$")


class ItemBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, description="Item name")
    description: Optional[str] = Field(None, max_length=1000)
    price: float = Field(..., gt=0, description="Item price must be greater than zero")
    tax: Optional[float] = Field(None, ge=0, le=0.4)
    tags: List[str] = Field(default_factory=list, max_items=5)

    @validator("price")
    def validate_price(cls, v):
        if v > 1000000:
            raise ValueError("Price cannot be greater than 1,000,000")
        return round(v, 2)


class ItemCreate(ItemBase):
    category: str = Field(..., min_length=3)


class ItemResponse(ItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    password: str


class UserProfile(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    interests: Set[str] = Field(default_factory=set)

    class Config:
        json_schema_extra = {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "full_name": "John Doe",
                "interests": ["coding", "reading"]
            }
        }


class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 