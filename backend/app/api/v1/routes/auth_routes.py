from fastapi import APIRouter, HTTPException, Query, Cookie, status, Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Annotated
from datetime import datetime, timedelta
import uuid
from datetime import timezone
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import (
    LoginRequest,
    LoginResponse,
    SessionResponse,
    UserCreate
)
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.crud.user import user as crud_user
from app.db.base import get_async_session
from app.schemas.token import Token
from app.schemas.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login-simulation", response_model=LoginResponse)
async def simulate_login(
    user_id: Annotated[int, Query(ge=1)],
    remember: Annotated[bool, Query()] = False
) -> JSONResponse:
    """模拟登录过程"""
    session_id = str(uuid.uuid4())
    utc_now = datetime.now(timezone.utc)
    
    response_data = {
        "message": "Login successful",
        "user_id": user_id,
        "session_id": session_id,
        "login_time": utc_now,
        "expires_at": utc_now + (timedelta(days=30) if remember else timedelta(hours=2)),
        "metadata": {
            "ip": "127.0.0.1",
            "user_agent": "Mozilla/5.0",
            "login_type": "simulation"
        }
    }
    
    json_compatible_data = jsonable_encoder(
        response_data,
        exclude_none=True,
        custom_encoder={
            datetime: lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        }
    )
    
    response = JSONResponse(content=json_compatible_data)
    
    expires = utc_now + (
        timedelta(days=30) if remember else timedelta(hours=2)
    )
    
    response.set_cookie(
        key="session_id",
        value=session_id,
        expires=expires,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=2592000 if remember else 7200,
        domain="localhost",
        path="/"
    )
    
    return response

@router.post("/logout")
async def logout() -> JSONResponse:
    """退出登录"""
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(
        key="session_id",
        httponly=True,
        samesite="lax",
        secure=False
    )
    return response

@router.get("/session", response_model=SessionResponse)
async def check_session(
    session_id: Annotated[str | None, Cookie()] = None
) -> SessionResponse:
    """检查会话状态"""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    return {
        "message": "Session is valid",
        "session_id": session_id
    }

@router.post("/login/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> Token:
    """
    使用表单数据登录获取访问令牌（用于 Swagger UI 测试）
    
    - **username**: 用户名或邮箱
    - **password**: 密码
    """
    # 先尝试通过用户名查找
    user = await crud_user.get_by_username(db, username=form_data.username)
    if not user:
        # 如果用户名未找到，尝试通过邮箱查找
        user = await crud_user.get_by_email(db, email=form_data.username)
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email, expires_delta=access_token_expires
    )
    
    return Token(access_token=access_token, token_type="bearer")

@router.post("/login", response_model=Token)
async def login_json(
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> Token:
    """
    使用 JSON 数据登录获取访问令牌
    
    - **username**: 用户名或邮箱
    - **password**: 密码
    - **remember_me**: 是否记住登录状态
    """
    # 先尝试通过用户名查找
    user = await crud_user.get_by_username(db, username=login_data.username)
    if not user:
        # 如果用户名未找到，尝试通过邮箱查找
        user = await crud_user.get_by_email(db, email=login_data.username)
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email, expires_delta=access_token_expires
    )
    
    return Token(access_token=access_token, token_type="bearer")

@router.post("/register", response_model=User)
async def register(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    """
    注册新用户
    
    - **email**: 电子邮件地址
    - **username**: 用户名（3-50个字符，只能包含字母、数字、下划线和连字符）
    - **password**: 密码
    - **full_name**: 全名（可选）
    """
    # 检查邮箱是否已被注册
    user = await crud_user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # 检查用户名是否已被使用
    user = await crud_user.get_by_username(db, username=user_in.username)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )
    
    # 创建新用户
    user = await crud_user.create(db, obj_in=user_in)
    return user 