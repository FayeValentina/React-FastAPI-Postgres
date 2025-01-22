from fastapi import APIRouter
from .v1.router import api_router as v1_router

# 创建主路由并注册 v1 版本的路由
router = APIRouter()
router.include_router(v1_router)  # 如果不需要版本控制，不加 prefix