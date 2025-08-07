from fastapi import APIRouter
from app.api.v1.routes import (
    user_routes,
    auth_routes,
    reddit_content_routes,
    task_routes
)

# 创建主路由
router = APIRouter()

# 包含核心路由
router.include_router(user_routes.router)
router.include_router(auth_routes.router)
router.include_router(reddit_content_routes.router)
router.include_router(task_routes.router)