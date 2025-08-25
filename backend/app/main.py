from contextlib import asynccontextmanager
import datetime
from fastapi import FastAPI, Depends, Request
# 删除 CORS 导入
# from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import router
from app.core.config import settings
from app.dependencies.request_context import request_context_dependency
from app.middleware.logging import RequestResponseLoggingMiddleware
from app.middleware.auth import AuthMiddleware, DEFAULT_EXCLUDE_PATHS
from app.core.logging import setup_logging
from app.core.exceptions import ApiError, AuthenticationError
from app.utils.common import create_exception_handlers
# from app.core.task_manager import task_manager  # 已删除，使用新架构
from app.broker import broker
from app.core.redis_manager import redis_services

# 配置日志系统
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # 自动发现并注册所有任务
        from app.core.tasks.registry import auto_discover_tasks
        auto_discover_tasks()
        logger.info("任务自动注册完成")
        
        # 启动时
        await broker.startup()
        
        # 初始化Redis服务管理器（包含所有Redis服务）
        await redis_services.initialize()
        logger.info("Redis服务管理器初始化成功")
        
        # 初始化调度器（已包含在redis_services中）
        logger.info("调度器服务已通过Redis服务管理器初始化")
        
        # 从数据库加载调度任务到Redis
        from app.db.base import AsyncSessionLocal
        from app.crud.task_config import crud_task_config
        from app.core.tasks.registry import SchedulerType
        
        async with AsyncSessionLocal() as db:
            # 获取所有任务配置（不再筛选status）
            configs = await crud_task_config.get_by_type(db, None)  # 获取所有配置
            
            loaded_count = 0
            failed_count = 0
            
            for config in configs:
                # 只加载需要调度的任务
                if config.scheduler_type != SchedulerType.MANUAL:
                    try:
                        success, message = await redis_services.scheduler.register_task(config)
                        if success:
                            loaded_count += 1
                            logger.debug(f"成功加载调度任务: {config.name} (ID: {config.id})")
                        else:
                            failed_count += 1
                            logger.warning(f"加载任务失败: {config.name} - {message}")
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"加载任务 {config.name} 失败: {e}")
            
            logger.info(f"从数据库加载调度任务完成: 成功 {loaded_count} 个, 失败 {failed_count} 个")
        
        logger.info("应用启动成功")
        
    except Exception as e:
        logger.error(f"启动失败: {e}")
    
    yield
    
    # 关闭时
    try:
        await broker.shutdown()
        # await task_manager.shutdown()  # 已删除，调度器通过redis_services管理
        
        # 关闭所有Redis服务
        await redis_services.close_all()
        
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