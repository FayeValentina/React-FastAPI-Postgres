from fastapi import APIRouter
from .user_routes import router as user_router
from .auth_routes import router as auth_router

# 创建主路由
router = APIRouter()

# 包含子路由
router.include_router(user_router, prefix="/users", tags=["users"])
router.include_router(auth_router, prefix="/auth", tags=["auth"]) 