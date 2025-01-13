import logging
import sys
from typing import List

from loguru import logger # type: ignore


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


def setup_logging(log_level: str = "INFO", json_logs: bool = False):
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
    ]
    for logger_name in loggers:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]

    # 配置 loguru
    logger.configure(
        handlers=[
            {
                "sink": sys.stdout,
                "serialize": json_logs,
                "level": log_level,
            }
        ]
    ) 