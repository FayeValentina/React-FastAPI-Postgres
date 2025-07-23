from pydantic import BaseModel, Field

# 登录请求模型
class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., min_length=6, description="密码")
    remember_me: bool = Field(default=False, description="记住我")