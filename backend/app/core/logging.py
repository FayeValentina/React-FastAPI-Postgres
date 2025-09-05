import logging
import sys
from typing import List
from pathlib import Path
from loguru import logger

from app.core.config import settings

class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # 添加请求ID到日志记录（如果存在）
        extra = {}
        if hasattr(record, "request_id"):
            extra["request_id"] = record.request_id

        logger.opt(depth=depth, exception=record.exc_info, **extra).log(
            level, record.getMessage()
        )

def setup_logging(
    log_level: str = None, 
    json_logs: bool = None,
    log_file: str | None = None
):
    """
    设置日志系统，从配置中读取设置
    
    Args:
        log_level: 日志级别，默认从配置中读取，若未设置则为 "INFO"
        json_logs: 是否使用 JSON 格式输出，默认从配置中读取，若未设置则为 False
        log_file: 日志文件路径，默认从配置中读取，若未设置则为 None（不写入文件）
    """
    # 从配置或环境变量读取配置
    if log_level is None:
        log_level = settings.logging.LEVEL
    
    if json_logs is None:
        json_logs = settings.logging.JSON
    
    if log_file is None:
        log_file = settings.logging.FILE
    
    # 移除所有默认处理器
    logging.root.handlers = []
    logging.root.setLevel(log_level)

    # 添加拦截器
    logging.root.addHandler(InterceptHandler())

    # 设置要拦截的模块
    loggers: List[str] = [
        "uvicorn",
        "uvicorn.error",
        "fastapi",
        "sqlalchemy.engine",
        "app"  # 确保应用代码的日志也被捕获
    ]
    for logger_name in loggers:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False  # 防止日志重复

    # 配置 loguru
    # 主日志格式，包含请求ID
    log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | " \
                 "<level>{level: <8}</level> | " \
                 "{extra[request_id]: <36} | " \
                 "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | " \
                 "{message}"
    
    # 不包含请求ID的简单格式，当请求ID不存在时使用
    simple_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | " \
                    "<level>{level: <8}</level> | " \
                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | " \
                    "{message}"

    handlers = [
        {
            "sink": sys.stdout,
            "serialize": json_logs,
            "level": log_level,
            "format": simple_format,
            "filter": lambda record: "request_id" not in record["extra"] and record["name"] != "app.api.middleware.logging"
        },
        {
            "sink": sys.stdout,
            "level": log_level,
            "format": log_format,
            "filter": lambda record: "request_id" in record["extra"] and record["name"] != "app.api.middleware.logging"
        },
        {
            "sink": sys.stdout,
            "level": "INFO",
            "format": "\n{message}",  # logging 中间件使用简化格式
            "filter": lambda record: record["name"] == "app.api.middleware.logging"
        }
    ]

    # 如果指定了日志文件，添加文件处理器
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 根据是否使用 JSON 格式分别配置
        if json_logs:
            handlers.append({
                "sink": str(log_path),
                "serialize": True,
                "level": log_level,
                "rotation": "00:00",  # 每天轮换
                "retention": "30 days",  # 保留30天
                "compression": "zip"  # 压缩旧日志
            })
        else:
            handlers.append({
                "sink": str(log_path),
                "serialize": False,
                "level": log_level,
                "rotation": "00:00",  # 每天轮换
                "retention": "30 days",  # 保留30天
                "compression": "zip",  # 压缩旧日志
                "format": log_format
            })

    # 配置 loguru
    logger.configure(handlers=handlers)

    logger.info(f"Logging system initialized: level={log_level}, json={json_logs}, file={log_file or 'None'}") 