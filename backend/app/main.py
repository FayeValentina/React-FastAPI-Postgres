from fastapi import FastAPI, Depends
from app.api import router
from app.core.config import settings
from app.api.v1.dependencies.audit import app_level_dependency
from app.middleware.cors import setup_cors_middleware
from app.middleware.logging import setup_logging_middleware
from app.middleware.timing import TimingMiddleware  # 直接导入中间件类

app = FastAPI(
    title="FastAPI Demo",
    description="A demo FastAPI application with restructured routes",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    dependencies=[Depends(app_level_dependency)]  # 添加全局依赖项
)

# 设置中间件（注意顺序：先timing，再logging，最后cors）
app.add_middleware(TimingMiddleware)  # 直接添加计时中间件
setup_logging_middleware(app)
setup_cors_middleware(app)

# 包含API路由
app.include_router(router, prefix="/api")