from fastapi import APIRouter
from app.api.v1.routes import (
    user_routes,
    product_routes,
    auth_routes,
    file_routes,
    basic_routes,
    validator_routes,
    dependency_demo_routes
)

# 创建主路由
router = APIRouter()

# 包含所有子路由
router.include_router(user_routes.router)
router.include_router(product_routes.router)
router.include_router(auth_routes.router)
router.include_router(file_routes.router)
router.include_router(basic_routes.router)
router.include_router(validator_routes.router)
router.include_router(dependency_demo_routes.router)