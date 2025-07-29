from pydantic import BaseModel, EmailStr, Field


class PasswordResetRequest(BaseModel):
    """密码重置请求模型"""
    email: EmailStr = Field(..., description="用户邮箱地址")


class PasswordResetConfirm(BaseModel):
    """密码重置确认模型"""
    token: str = Field(..., description="密码重置令牌")
    new_password: str = Field(..., min_length=8, description="新密码")


class PasswordResetResponse(BaseModel):
    """密码重置响应模型"""
    message: str
    success: bool = True