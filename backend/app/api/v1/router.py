from fastapi import APIRouter
from app.api.v1.routes import (
    user_routes,
    auth_routes
)

# 创建主路由
router = APIRouter()

# 包含核心路由
router.include_router(user_routes.router)
router.include_router(auth_routes.router)