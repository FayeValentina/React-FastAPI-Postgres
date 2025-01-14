from fastapi import APIRouter # type: ignore
from app.api.endpoints import hello, users

api_router = APIRouter()
api_router.include_router(hello.router, tags=["hello"])
api_router.include_router(users.router, tags=["users"]) 