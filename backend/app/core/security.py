from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from jose import jwt, JWTError # type: ignore
from jose.exceptions import ExpiredSignatureError  # type: ignore
from passlib.context import CryptContext # type: ignore
from app.core.config import settings
from app.infrastructure.utils.common import get_current_time   

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """
    创建访问令牌
    
    Args:
        subject: 令牌主题（通常是用户标识）
        expires_delta: 过期时间增量，如果未提供则使用默认配置
        
    Returns:
        生成的JWT令牌
        
    Raises:
        ValueError: 如果令牌创建失败
    """
    try:
        if expires_delta:
            expire = get_current_time() + expires_delta
        else:
            expire = get_current_time() + timedelta(
                minutes=settings.security.ACCESS_TOKEN_EXPIRE_MINUTES
            )
            
        to_encode: Dict[str, Any] = {
            "exp": expire,
            "sub": str(subject),
            "iat": get_current_time(),
            "type": "access_token",
            "jti": str(uuid4())  # 添加唯一ID用于令牌吊销
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.security.SECRET_KEY,
            algorithm=settings.security.ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        raise ValueError(f"Error creating access token: {str(e)}")


def create_refresh_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """
    创建刷新令牌
    
    Args:
        subject: 令牌主题（通常是用户标识）
        expires_delta: 过期时间增量，如果未提供则使用环境变量中配置的天数
        
    Returns:
        生成的JWT刷新令牌
        
    Raises:
        ValueError: 如果令牌创建失败
    """
    try:
        if expires_delta:
            expire = get_current_time() + expires_delta
        else:
            expire = get_current_time() + timedelta(days=settings.security.REFRESH_TOKEN_EXPIRE_DAYS)
            
        to_encode: Dict[str, Any] = {
            "exp": expire,
            "sub": str(subject),
            "iat": get_current_time(),
            "type": "refresh_token",
            "jti": str(uuid4())  # 添加唯一ID用于令牌吊销
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.security.SECRET_KEY,
            algorithm=settings.security.ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        raise ValueError(f"Error creating refresh token: {str(e)}")


def verify_token(token: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    验证JWT令牌
    
    Args:
        token: JWT令牌
        
    Returns:
        (是否有效, 解码后的payload或None, 错误类型或None)
    """
    try:
        payload = jwt.decode(
            token,
            settings.security.SECRET_KEY,
            algorithms=[settings.security.ALGORITHM],
          #  options={"verify_exp": True}  # 确保验证过期时间
        )
        return True, payload, None
    except ExpiredSignatureError:
        # 特别处理过期情况
        return False, None, "expired"
    except JWTError:
        return False, None, "invalid"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码
        
    Returns:
        密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    获取密码哈希值
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码
    """
    return pwd_context.hash(password)


def create_token_pair(subject: str | Any, remember_me: bool = False) -> Tuple[str, str, datetime]:
    """
    创建访问令牌和刷新令牌对
    
    Args:
        subject: 令牌主题（通常是用户标识）
        remember_me: 是否记住登录状态
        
    Returns:
        (访问令牌, 刷新令牌, 访问令牌过期时间)
    """
    # 设置访问令牌过期时间
    if remember_me:
        access_token_expires = timedelta(days=1)  # 记住登录状态则访问令牌延长到1天
    else:
        access_token_expires = timedelta(minutes=settings.security.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 获取过期时间
    expires_at = get_current_time() + access_token_expires
    
    # 创建令牌
    access_token = create_access_token(subject=subject, expires_delta=access_token_expires)
    refresh_token = create_refresh_token(subject=subject)  # 刷新令牌使用默认过期时间
    
    return access_token, refresh_token, expires_at 
