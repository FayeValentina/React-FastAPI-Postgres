from contextlib import asynccontextmanager
import datetime
from fastapi import FastAPI, Depends, Request
# 删除 CORS 导入
# from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import router
from app.core.config import settings
from app.api.middleware.logging import RequestResponseLoggingMiddleware
from app.api.middleware.auth import AuthMiddleware, DEFAULT_EXCLUDE_PATHS
from app.core.logging import setup_logging
from app.core.exceptions import ApiError, AuthenticationError
from app.infrastructure.utils.common import create_exception_handlers
# from app.core.task_manager import task_manager  # 已删除，使用新架构
from app.broker import broker
from app.infrastructure.redis.redis_pool import redis_connection_manager
from app.infrastructure.scheduler.scheduler import scheduler_service

# 配置日志系统
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # 自动发现并注册所有任务
        from app.infrastructure.tasks.task_registry_decorators import auto_discover_tasks
        auto_discover_tasks()
        logger.info("任务自动注册完成")
        
        # 启动时
        await broker.startup()
        
        # 初始化Redis连接池和调度器
        await redis_connection_manager.initialize()
        await scheduler_service.initialize()
        logger.info("Redis连接池和调度器初始化成功")

        try:
            from app.infrastructure.dynamic_settings import get_dynamic_settings_service

            dynamic_settings_service = get_dynamic_settings_service()
            await dynamic_settings_service.refresh()
            logger.info("动态配置缓存预热成功")
        except Exception as exc:
            logger.warning(f"动态配置缓存预热失败: {exc}")

        # 运行启动时维护流程：清理遗留、清理孤儿、确保默认实例
        try:
            legacy = await scheduler_service.cleanup_legacy_artifacts()
            logger.info(f"遗留清理完成: {legacy}")
        except Exception as e:
            logger.warning(f"遗留清理出错: {e}")

        try:
            orphans = await scheduler_service.cleanup_orphan_schedules()
            logger.info(f"孤儿调度实例清理: {orphans}")
        except Exception as e:
            logger.warning(f"孤儿清理出错: {e}")

        try:
            ensured = await scheduler_service.ensure_default_instances()
            logger.info(f"默认实例保证: {ensured}")
        except Exception as e:
            logger.warning(f"默认实例保证出错: {e}")
        
        logger.info("应用启动成功")
        
    except Exception as e:
        logger.error(f"启动失败: {e}")
    
    yield
    
    # 关闭时
    try:
        await broker.shutdown()
        # await task_manager.shutdown()  # 已删除，调度器通过 scheduler_service 管理
        
        # 关闭调度器和Redis连接
        await scheduler_service.shutdown()
        await redis_connection_manager.close()
        
        logger.info("应用关闭成功")
    except Exception as e:
        logger.error(f"关闭失败: {e}")


app = FastAPI(
    title="FastAPI Demo",
    description="A demo FastAPI application with restructured routes",
    version="1.0.0",
    root_path="/api",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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

# 2. 删除整个 CORS 中间件配置
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.cors.ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# 3. JWT认证中间件
app.add_middleware(
    AuthMiddleware,
    exclude_paths=DEFAULT_EXCLUDE_PATHS  # 使用集中定义的排除路径列表
)

# 添加简单的健康检查端点（无需认证）
@app.get("/health")
async def health_check():
    """
    简单的健康检查端点
    - 无需认证
    - 无需数据库连接
    - 只检查应用是否能响应HTTP请求
    """
    return {
        "status": "ok", 
        "service": "backend",
        "timestamp": datetime.datetime.now().isoformat()
    }

# 包含API路由
app.include_router(router)
