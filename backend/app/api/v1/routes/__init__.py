from fastapi import APIRouter
from .auth_routes import router as auth_router
from .user_routes import router as user_router
from .product_routes import router as product_router
from .file_routes import router as file_router
from .basic_routes import router as basic_router
from .validator_routes import router as validator_router
from .dependency_demo_routes import router as dependency_demo_router

# 创建主路由器
router = APIRouter()

# 按功能模块注册子路由器
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(user_router, prefix="/users", tags=["users"])
router.include_router(product_router, prefix="/products", tags=["products"])
router.include_router(file_router, prefix="/files", tags=["files"])
router.include_router(basic_router, tags=["basic"])
router.include_router(validator_router, prefix="/validators", tags=["validators"])
router.include_router(dependency_demo_router, prefix="/dependency-demo", tags=["dependency-demo"]) 