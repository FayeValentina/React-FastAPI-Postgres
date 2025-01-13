from fastapi import APIRouter # type: ignore
from app.api.endpoints import hello

api_router = APIRouter()
api_router.include_router(hello.router, tags=["hello"]) 