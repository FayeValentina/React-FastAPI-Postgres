from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from jose import jwt, JWTError # type: ignore
from passlib.context import CryptContext # type: ignore
from app.core.config import settings
from app.utils.common import get_current_time   

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
            "type": "access_token"
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.security.SECRET_KEY,
            algorithm=settings.security.ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        raise ValueError(f"Error creating access token: {str(e)}")


def verify_token(token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    验证JWT令牌
    
    Args:
        token: JWT令牌
        
    Returns:
        (是否有效, 解码后的payload或None)
    """
    try:
        payload = jwt.decode(
            token,
            settings.security.SECRET_KEY,
            algorithms=[settings.security.ALGORITHM]
        )
        return True, payload
    except JWTError:
        return False, None


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