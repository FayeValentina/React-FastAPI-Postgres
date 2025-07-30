from fastapi import APIRouter
from .user_routes import router as user_router
from .auth_routes import router as auth_router
from .bot_config_routes import router as bot_config_router
from .scraping_routes import router as scraping_router
from .reddit_content_routes import router as reddit_content_router

# 创建主路由
router = APIRouter()

# 包含子路由
router.include_router(user_router, prefix="/users", tags=["users"])
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(bot_config_router)
router.include_router(scraping_router)
router.include_router(reddit_content_router) 