from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, List, Callable
import re

from app.core.security import verify_token
from app.core.config import settings

class AuthMiddleware(BaseHTTPMiddleware):
    """JWT认证中间件"""
    
    def __init__(
        self, 
        app, 
        exclude_paths: Optional[List[str]] = None,
        exclude_path_regexes: Optional[List[str]] = None
    ):
        super().__init__(app)
        # 默认排除认证的路径
        self.exclude_paths = exclude_paths or [
            "/api/v1/auth/login",
            "/api/v1/auth/login/token",
            "/api/v1/auth/register",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]
        # 编译正则表达式用于排除路径
        self.exclude_path_regexes = []
        if exclude_path_regexes:
            for pattern in exclude_path_regexes:
                self.exclude_path_regexes.append(re.compile(pattern))
    
    async def dispatch(self, request: Request, call_next: Callable):
        # 检查请求路径是否需要验证
        if self._should_exclude(request.url.path):
            return await call_next(request)
        
        # 获取Authorization头
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "未提供认证凭据"},
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 验证Bearer令牌
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "认证方案必须是Bearer"},
                    headers={"WWW-Authenticate": "Bearer"}
                )
                
            is_valid, payload = verify_token(token)
            if not is_valid or not payload:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "无效的认证凭据"},
                    headers={"WWW-Authenticate": "Bearer"}
                )
                
            # 将用户信息添加到请求状态
            request.state.user_payload = payload
            
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": f"认证错误: {str(e)}"},
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 继续处理请求
        return await call_next(request)
    
    def _should_exclude(self, path: str) -> bool:
        """检查路径是否应该被排除认证"""
        # 检查确切路径匹配
        if path in self.exclude_paths:
            return True
            
        # 检查前缀匹配
        for exclude_path in self.exclude_paths:
            if exclude_path.endswith("*") and path.startswith(exclude_path[:-1]):
                return True
        
        # 检查正则表达式匹配
        for pattern in self.exclude_path_regexes:
            if pattern.match(path):
                return True
                
        return False 