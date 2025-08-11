from fastapi import APIRouter
from .user_routes import router as user_router
from .auth_routes import router as auth_router
from .task_routes import router as task_router
# from .reddit_content_routes import router as reddit_content_router  # 暂时注释，等模型恢复后再启用

# 创建主路由
router = APIRouter()

# 包含子路由
router.include_router(user_router, prefix="/users", tags=["users"])
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(task_router, prefix="/tasks", tags=["tasks"])
# router.include_router(reddit_content_router)  # 暂时注释，等模型恢复后再启用 