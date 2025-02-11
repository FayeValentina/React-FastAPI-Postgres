from fastapi import APIRouter
from .endpoints import hello, users, example, validators

api_router = APIRouter()

# 注册路由并添加更多信息
api_router.include_router(
    hello.router,
    prefix="/hello",  # 添加前缀使路由更有层次
    tags=["hello"],
    responses={404: {"description": "Not found"}}
)

api_router.include_router(
    users.router,
    tags=["users"],
    responses={404: {"description": "Not found"}}
)

api_router.include_router(
    example.router,
    prefix="/examples",
    tags=["examples"],
    responses={404: {"description": "Not found"}}
)

api_router.include_router(
    validators.router,
    prefix="/validators",
    tags=["validators"],
    responses={404: {"description": "Not found"}}
)