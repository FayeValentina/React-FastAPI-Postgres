"""
异常处理模块

定义应用中所有自定义异常类
"""

from fastapi import HTTPException
from typing import Any, Dict, Optional

from app.constant.constants import ErrorMessages, StatusCode


class ApiError(Exception):
    """API错误的基类，包含标准化格式"""
    def __init__(
        self, 
        status_code: int, 
        detail: str, 
        headers: Optional[Dict[str, Any]] = None
    ):
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)
        
    def to_http_exception(self) -> HTTPException:
        """转换为FastAPI的HTTPException"""
        return HTTPException(
            status_code=self.status_code,
            detail=self.detail,
            headers=self.headers
        )


# 认证错误
class AuthenticationError(ApiError):
    """认证错误的基类"""
    def __init__(
        self, 
        detail: str = "认证错误", 
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=StatusCode.UNAUTHORIZED,
            detail=detail,
            headers=headers or {"WWW-Authenticate": "Bearer"}
        )


class InvalidCredentialsError(AuthenticationError):
    """当登录凭据无效时抛出"""
    def __init__(self):
        super().__init__(detail=ErrorMessages.INVALID_CREDENTIALS)


# 注册和用户管理错误
class UserError(ApiError):
    """用户相关错误的基类"""
    def __init__(
        self, 
        detail: str = "用户错误", 
        status_code: int = StatusCode.BAD_REQUEST
    ):
        super().__init__(status_code=status_code, detail=detail)


class UserNotFoundError(UserError):
    """未找到用户时抛出"""
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.USER_NOT_FOUND,
            status_code=StatusCode.NOT_FOUND
        )


class EmailAlreadyRegisteredError(UserError):
    """尝试使用已存在的电子邮件注册时抛出"""
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.EMAIL_ALREADY_REGISTERED,
            status_code=StatusCode.CONFLICT
        )


class UsernameTakenError(UserError):
    """尝试使用已存在的用户名注册时抛出"""
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.USERNAME_TAKEN,
            status_code=StatusCode.CONFLICT
        )


class InactiveUserError(UserError):
    """尝试使用未激活的用户账户时抛出"""
    def __init__(self):
        super().__init__(
            detail=ErrorMessages.USER_INACTIVE,
            status_code=StatusCode.FORBIDDEN
        )


class InsufficientPermissionsError(ApiError):
    """用户没有所需权限时抛出"""
    def __init__(self, detail: str = "权限不足"):
        super().__init__(
            status_code=StatusCode.FORBIDDEN,
            detail=detail
        )


class DatabaseError(ApiError):
    """数据库操作错误的基类"""
    def __init__(self, detail: str = "数据库操作失败"):
        super().__init__(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=detail
        )


class ResourceAlreadyExistsError(ApiError):
    """资源已存在时抛出"""
    def __init__(self, detail: str = "资源已存在"):
        super().__init__(
            status_code=StatusCode.CONFLICT,
            detail=detail
        )


class ResourceNotFoundError(ApiError):
    """资源不存在时抛出"""
    def __init__(self, detail: str = "资源不存在"):
        super().__init__(
            status_code=StatusCode.NOT_FOUND,
            detail=detail
        )


class ValidationError(ApiError):
    """数据验证错误"""
    def __init__(self, detail: str = "数据验证失败"):
        super().__init__(
            status_code=StatusCode.BAD_REQUEST,
            detail=detail
        )


class InvalidRefreshTokenError(ApiError):
    """
    无效的刷新令牌错误
    
    当提供的刷新令牌无效、已过期或已被吊销时抛出
    """
    def __init__(self, detail: str = ErrorMessages.INVALID_REFRESH_TOKEN):
        super().__init__(
            status_code=StatusCode.UNAUTHORIZED, 
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        ) 