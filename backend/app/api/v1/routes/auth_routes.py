from fastapi import APIRouter, HTTPException, Query, Cookie, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Annotated, Dict, Optional
from datetime import datetime, timedelta
import uuid
from datetime import timezone

from app.schemas import (
    LoginRequest,
    LoginFormResponse,
    LoginResponse,
    SessionResponse
)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginFormResponse)
async def login(login_data: LoginRequest) -> LoginFormResponse:
    """用户登录"""
    return {
        "username": login_data.username,
        "remember_me": login_data.remember_me,
        "message": "Login successful"
    }

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