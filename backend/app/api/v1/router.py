from fastapi import APIRouter
from app.api.v1.endpoints import auth, content, tasks, users

# 创建主路由
router = APIRouter()

# 包含核心路由
router.include_router(users.router)
router.include_router(auth.router)
router.include_router(content.router)
router.include_router(tasks.router)