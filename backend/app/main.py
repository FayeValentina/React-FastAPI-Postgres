from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import router
from app.core.config import settings
from app.dependencies.request_context import request_context_dependency
from app.middleware.logging import RequestResponseLoggingMiddleware
from app.middleware.auth import AuthMiddleware, DEFAULT_EXCLUDE_PATHS
from app.core.logging import setup_logging
from app.core.exceptions import ApiError, AuthenticationError
from app.utils.common import create_exception_handlers
from app.tasks.schedulers import scheduler

# 配置日志系统
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # 启动时
        await scheduler.start()
        logger.info("调度器启动成功")
    except Exception as e:
        logger.error(f"调度器启动失败: {e}")
    
    yield
    
    # 关闭时
    try:
        scheduler.shutdown()
        logger.info("调度器关闭成功")
    except Exception as e:
        logger.error(f"调度器关闭失败: {e}")


app = FastAPI(
    title="FastAPI Demo",
    description="A demo FastAPI application with restructured routes",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    dependencies=[Depends(request_context_dependency)],
    exception_handlers=create_exception_handlers(),  # 使用工厂函数创建异常处理器
    lifespan=lifespan  # 添加生命周期管理
)

# 设置中间件（注意顺序很重要）
# 中间件的执行顺序与添加顺序相反

# 1. 请求/响应日志记录中间件 (最后执行，最先完成)
# 这允许记录所有请求和响应，包括其他中间件添加的信息
app.add_middleware(
    RequestResponseLoggingMiddleware,
    log_request_body=True,
    log_response_body=True,
    max_body_length=4096,
    exclude_paths=[
        "/docs", 
        "/redoc", 
        "/openapi.json",
        "/static/*"
    ],
    exclude_extensions=[
        ".css", ".js", ".ico", ".png", ".jpg", ".svg", ".woff", ".woff2"
    ]
)

# 2. CORS中间件 (倒数第二执行)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. JWT认证中间件 (倒数第三执行，但实际是第一个处理请求的中间件)
# 这样可以确保在进行其他操作前验证用户身份
app.add_middleware(
    AuthMiddleware,
    exclude_paths=DEFAULT_EXCLUDE_PATHS,  # 使用集中定义的排除路径列表
    exclude_path_regexes=[
        "^/api/v1/public/.*$",  # 所有公共API不需要认证
        "^/static/.*$"          # 静态文件不需要认证
    ]
)

# 包含API路由
app.include_router(router, prefix="/api")