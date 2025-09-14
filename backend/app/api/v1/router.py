from fastapi import APIRouter
from app.api.v1.endpoints import auth, content, tasks, users
from app.api.v1.endpoints import knowledge
from app.api.v1.endpoints import llm_ws

# 创建主路由
router = APIRouter()

# 包含核心路由
router.include_router(users.router)
router.include_router(auth.router)
router.include_router(content.router)
router.include_router(tasks.router)
router.include_router(knowledge.router)
router.include_router(llm_ws.router)
