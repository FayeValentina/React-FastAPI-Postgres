from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.api import router
from app.core.config import settings
from app.api.v1.dependencies.audit import app_level_dependency
from app.middleware.timing import TimingMiddleware
from app.core.logging_config import configure_logging

# 配置日志系统
configure_logging()

app = FastAPI(
    title="FastAPI Demo",
    description="A demo FastAPI application with restructured routes",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    dependencies=[Depends(app_level_dependency)]  # 添加全局依赖项
)

# 设置中间件（注意顺序很重要）
app.add_middleware(TimingMiddleware)  # 计时中间件应该最后添加，这样它会最先执行
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含API路由
app.include_router(router, prefix="/api")