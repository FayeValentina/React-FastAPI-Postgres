import logging
import sys
from typing import List
from pathlib import Path
from loguru import logger

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

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logging(
    log_level: str = "INFO", 
    json_logs: bool = False,
    log_file: str | None = None
):
    """
    设置日志系统
    
    Args:
        log_level: 日志级别，默认为 "INFO"
        json_logs: 是否使用 JSON 格式输出，默认为 False
        log_file: 日志文件路径，默认为 None（不写入文件）
    """
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
        "app.middleware.timing",  # 添加 timing 中间件的日志
    ]
    for logger_name in loggers:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]

    # 准备日志处理器配置
    handlers = [
        {
            "sink": sys.stdout,
            "serialize": json_logs,
            "level": log_level,
            "format": "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                     "<level>{level: <8}</level> | "
                     "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                     "{message}",
        }
    ]

    # 如果指定了日志文件，添加文件处理器
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append({
            "sink": str(log_path),
            "serialize": json_logs,
            "level": log_level,
            "rotation": "00:00",  # 每天轮换
            "retention": "30 days",  # 保留30天
            "compression": "zip",  # 压缩旧日志
        })

    # 配置 loguru
    logger.configure(handlers=handlers)

    # 添加一个特殊的格式化处理器用于 timing 中间件
    timing_handler = {
        "sink": sys.stdout,
        "level": "INFO",
        "format": "\n{message}",  # 简化格式，因为 timing 中间件有自己的格式
        "filter": lambda record: record["name"] == "app.middleware.timing"
    }
    logger.add(**timing_handler)

    logger.info("Logging system initialized") 