"""
应用常量定义

只定义真正需要复用的常量，避免过度设计
"""

from fastapi import status

# HTTP 状态码常量
class StatusCode:
    """HTTP状态码常量"""
    OK = status.HTTP_200_OK
    CREATED = status.HTTP_201_CREATED
    NO_CONTENT = status.HTTP_204_NO_CONTENT
    BAD_REQUEST = status.HTTP_400_BAD_REQUEST
    UNAUTHORIZED = status.HTTP_401_UNAUTHORIZED
    FORBIDDEN = status.HTTP_403_FORBIDDEN
    NOT_FOUND = status.HTTP_404_NOT_FOUND
    CONFLICT = status.HTTP_409_CONFLICT
    INTERNAL_SERVER_ERROR = status.HTTP_500_INTERNAL_SERVER_ERROR

# 错误消息常量
class ErrorMessages:
    """错误消息常量"""
    
    # 认证相关
    AUTHENTICATION_FAILED = "认证错误"
    INVALID_CREDENTIALS = "用户名或密码不正确"
    INVALID_REFRESH_TOKEN = "无效的刷新令牌"
    TOKEN_EXPIRED = "刷新令牌已过期"
    INSUFFICIENT_PERMISSIONS = "权限不足"
    
    # 用户相关
    USER_NOT_FOUND = "用户不存在"
    EMAIL_ALREADY_REGISTERED = "该邮箱已被注册"
    USERNAME_TAKEN = "该用户名已被使用"
    USER_INACTIVE = "用户未激活"
    
    # 资源相关
    RESOURCE_NOT_FOUND = "资源不存在"
    RESOURCE_ALREADY_EXISTS = "资源已存在"
    
    # 验证相关
    VALIDATION_ERROR = "数据验证失败"
    INVALID_USERNAME_FORMAT = "用户名必须为3-50个字符，只能包含字母、数字、下划线和连字符"
    INVALID_EMAIL_FORMAT = "邮箱格式无效"
    PASSWORD_TOO_SHORT = "密码长度必须至少为8个字符"
    INVALID_AGE_RANGE = "年龄必须在0-150之间"
    
    # 系统相关
    DATABASE_ERROR = "数据库操作失败"
    INTERNAL_ERROR = "服务器内部错误"

__all__ = [
    "ErrorMessages",
    "StatusCode",
]