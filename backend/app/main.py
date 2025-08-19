from contextlib import asynccontextmanager
import datetime
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
from app.core.task_manager import task_manager
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
        from app.constant.task_registry import auto_discover_tasks
        auto_discover_tasks()
        logger.info("任务自动注册完成")
        
        # 启动时
        await broker.startup()
        
        # 初始化Redis服务管理器（包含所有Redis服务）
        await redis_services.initialize()
        logger.info("Redis服务管理器初始化成功")
        
        # 初始化任务管理器
        await task_manager.initialize()
        logger.info("TaskIQ任务管理器启动成功")
        
        # 从数据库加载调度任务到Redis
        from app.db.base import AsyncSessionLocal
        from app.crud.task_config import crud_task_config
        
        async with AsyncSessionLocal() as db:
            # 获取所有需要调度的活跃任务配置
            configs = await crud_task_config.get_scheduled_configs(db)
            
            loaded_count = 0
            failed_count = 0
            
            for config in configs:
                try:
                    # 使用Redis调度器服务注册任务
                    success = await redis_services.scheduler.register_task(config)
                    if success:
                        loaded_count += 1
                        logger.debug(f"成功加载调度任务: {config.name} (ID: {config.id})")
                        
                        # 记录到调度历史
                        await redis_services.history.add_history_event(
                            config_id=config.id,
                            event_data={
                                "event": "task_loaded",
                                "task_name": config.name,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        )
                    else:
                        failed_count += 1
                        logger.warning(f"加载调度任务失败: {config.name} (ID: {config.id})")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"加载任务 {config.name} (ID: {config.id}) 时出错: {e}")
            
            logger.info(f"从数据库加载调度任务完成: 成功 {loaded_count} 个, 失败 {failed_count} 个")
        
        logger.info("应用启动成功")
        
    except Exception as e:
        logger.error(f"启动失败: {e}")
    
    yield
    
    # 关闭时
    try:
        await broker.shutdown()
        await task_manager.shutdown()
        
        # 关闭所有Redis服务
        await redis_services.close_all()
        
        logger.info("应用关闭成功")
    except Exception as e:
        logger.error(f"关闭失败: {e}")


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