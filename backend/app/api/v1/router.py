from fastapi import APIRouter
from app.api.v1.routes import (
    user_routes,
    auth_routes,
    # reddit_content_routes,  # 暂时注释，等模型恢复后再启用
    # task_routes  # 暂时注释，等相关服务恢复后再启用
)

# 创建主路由
router = APIRouter()

# 包含核心路由
router.include_router(user_routes.router)
router.include_router(auth_routes.router)
# router.include_router(reddit_content_routes.router)  # 暂时注释，等模型恢复后再启用
# router.include_router(task_routes.router)  # 暂时注释，等相关服务恢复后再启用