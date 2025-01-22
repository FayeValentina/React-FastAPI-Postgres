from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.schemas.user import UserCreate, UserResponse
from app.crud import user as user_crud
from app.dependencies.db import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/users", response_model=UserResponse)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        user = await user_crud.create_user(db, user_data)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while creating user"
        ) 