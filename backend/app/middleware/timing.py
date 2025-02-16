from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
from typing import Callable
from loguru import logger

class TimingMiddleware(BaseHTTPMiddleware):
    """响应时间统计中间件"""
    async def dispatch(
        self, 
        request: Request, 
        call_next: Callable
    ):
        # 记录开始时间
        start_time = time.time()
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算响应时间
            duration = round(time.time() - start_time, 3)
            
            # 记录响应时间
            logger.info(
                f"🕒 响应时间统计:\n"
                f"├── 路径: {request.url.path}\n"
                f"├── 方法: {request.method}\n"
                f"├── 状态: {response.status_code}\n"
                f"└── 耗时: {duration}秒"
            )
            
            # 添加响应时间到响应头
            response.headers["X-Process-Time"] = str(duration)
            return response
            
        except Exception as e:
            # 即使发生错误也记录执行时间
            duration = round(time.time() - start_time, 3)
            logger.error(
                f"⚠️ 请求处理异常:\n"
                f"├── 路径: {request.url.path}\n"
                f"├── 方法: {request.method}\n"
                f"├── 错误: {str(e)}\n"
                f"└── 耗时: {duration}秒"
            )
            raise 