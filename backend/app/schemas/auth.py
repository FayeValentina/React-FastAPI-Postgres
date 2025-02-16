from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime

# 登录请求模型
class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    remember_me: bool = False

# 登录表单响应模型
class LoginFormResponse(BaseModel):
    """登录表单响应模型"""
    username: str
    remember_me: bool
    message: str = "Login successful"

    model_config = {"from_attributes": True}

# 登录响应模型
class LoginResponse(BaseModel):
    """登录响应模型"""
    message: str
    user_id: int
    session_id: str

# 会话响应模型
class SessionResponse(BaseModel):
    """会话响应模型"""
    message: str
    session_id: str

# 偏好设置响应模型
class PreferencesResponse(BaseModel):
    """偏好设置响应模型"""
    preferences: Dict[str, str | bool]
    message: str

# 主题偏好响应模型
class ThemePreferenceResponse(BaseModel):
    """主题偏好响应模型"""
    theme: str
    message: str

# 支付信息模型（从validators.py移动）
class PaymentInfo(BaseModel):
    """支付信息验证模型"""
    card_number: str = Field(..., min_length=16, max_length=16)
    expiry_date: datetime
    cvv: str = Field(..., min_length=3, max_length=4)
    amount: float = Field(..., gt=0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "card_number": "4532756279624064",
                "expiry_date": "2025-12-31",
                "cvv": "123",
                "amount": 99.99
            }
        }
    } 