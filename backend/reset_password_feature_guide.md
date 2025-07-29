# FastAPI 添加找回密码功能 - 开发任务清单

## 任务概述
为现有的FastAPI后端添加完整的密码重置功能，包括发送重置邮件、验证令牌、重置密码等功能。

## 📁 需要新建的文件

### 1. 创建密码重置模型
**文件路径：** `backend/app/models/password_reset.py`

```python
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4

from app.db.base_class import Base
from app.utils.common import get_current_time

if TYPE_CHECKING:
    from .user import User


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=get_current_time)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 关联关系
    user: Mapped["User"] = relationship("User", back_populates="password_resets")

    @property
    def is_expired(self) -> bool:
        """检查令牌是否已过期"""
        return get_current_time() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """检查令牌是否有效（未使用且未过期）"""
        return not self.is_used and not self.is_expired

    @classmethod
    def create(cls, user_id: int, token: str, expires_in_hours: int = 1) -> "PasswordReset":
        """创建新的密码重置令牌"""
        return cls(
            user_id=user_id,
            token=token,
            expires_at=get_current_time() + timedelta(hours=expires_in_hours)
        )
```

### 2. 创建密码重置Schema
**文件路径：** `backend/app/schemas/password_reset.py`

```python
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
```

### 3. 创建密码重置CRUD操作
**文件路径：** `backend/app/crud/password_reset.py`

```python
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import timedelta
from uuid import uuid4

from app.models.password_reset import PasswordReset
from app.utils.common import get_current_time


class CRUDPasswordReset:
    async def create(
        self, 
        db: AsyncSession, 
        user_id: int,
        expires_in_hours: int = 1
    ) -> PasswordReset:
        """创建新的密码重置令牌"""
        # 先将该用户的所有未使用令牌标记为已使用（确保一次只有一个有效令牌）
        await self.invalidate_user_tokens(db, user_id)
        
        # 生成新令牌
        token = str(uuid4())
        reset_token = PasswordReset.create(
            user_id=user_id,
            token=token,
            expires_in_hours=expires_in_hours
        )
        
        db.add(reset_token)
        await db.commit()
        await db.refresh(reset_token)
        return reset_token
    
    async def get_by_token(
        self, 
        db: AsyncSession, 
        token: str
    ) -> Optional[PasswordReset]:
        """通过令牌获取密码重置记录"""
        result = await db.execute(
            select(PasswordReset).where(PasswordReset.token == token)
        )
        return result.scalar_one_or_none()
    
    async def use_token(
        self, 
        db: AsyncSession, 
        token: str
    ) -> bool:
        """使用密码重置令牌"""
        result = await db.execute(
            update(PasswordReset)
            .where(PasswordReset.token == token)
            .values(
                is_used=True,
                used_at=get_current_time()
            )
        )
        await db.commit()
        return result.rowcount > 0
    
    async def invalidate_user_tokens(
        self, 
        db: AsyncSession, 
        user_id: int
    ) -> int:
        """使用户的所有未使用令牌失效"""
        result = await db.execute(
            update(PasswordReset)
            .where(
                PasswordReset.user_id == user_id,
                PasswordReset.is_used == False
            )
            .values(
                is_used=True,
                used_at=get_current_time()
            )
        )
        await db.commit()
        return result.rowcount
    
    async def cleanup_expired(
        self, 
        db: AsyncSession
    ) -> int:
        """清理过期的密码重置令牌"""
        current_time = get_current_time()
        result = await db.execute(
            update(PasswordReset)
            .where(
                PasswordReset.expires_at < current_time,
                PasswordReset.is_used == False
            )
            .values(
                is_used=True,
                used_at=current_time
            )
        )
        await db.commit()
        return result.rowcount


password_reset = CRUDPasswordReset()
```

### 4. 创建邮件服务
**文件路径：** `backend/app/services/email_service.py`

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """邮件发送服务"""
    
    def __init__(self):
        self.smtp_server = settings.email.SMTP_SERVER
        self.smtp_port = settings.email.SMTP_PORT
        self.username = settings.email.USERNAME
        self.password = settings.email.PASSWORD
        self.from_email = settings.email.FROM_EMAIL
        self.use_tls = settings.email.USE_TLS
    
    async def send_password_reset_email(
        self, 
        to_email: str, 
        reset_token: str,
        user_name: Optional[str] = None
    ) -> bool:
        """发送密码重置邮件"""
        try:
            # 构造重置链接
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
            
            # 邮件主题和内容
            subject = "密码重置请求"
            html_content = self._generate_reset_email_html(
                user_name or to_email, 
                reset_url
            )
            
            return await self._send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content
            )
            
        except Exception as e:
            logger.error(f"发送密码重置邮件失败: {e}")
            return False
    
    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """发送邮件的通用方法"""
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # 添加文本内容
            if text_content:
                text_part = MIMEText(text_content, 'plain', 'utf-8')
                msg.attach(text_part)
            
            # 添加HTML内容
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 发送邮件
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.username and self.password:
                    server.login(self.username, self.password)
                
                server.send_message(msg)
            
            logger.info(f"邮件已发送到: {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败 {to_email}: {e}")
            return False
    
    def _generate_reset_email_html(self, user_name: str, reset_url: str) -> str:
        """生成密码重置邮件的HTML内容"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>密码重置</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px;">
                <h2 style="color: #333; text-align: center;">密码重置请求</h2>
                
                <p>尊敬的 {user_name}，</p>
                
                <p>我们收到了您的密码重置请求。如果这是您本人的操作，请点击下面的按钮重置您的密码：</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" 
                       style="background-color: #007bff; color: white; padding: 12px 30px; 
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        重置密码
                    </a>
                </div>
                
                <p>如果按钮无法点击，请复制以下链接到浏览器地址栏：</p>
                <p style="word-break: break-all; background-color: #f1f1f1; padding: 10px; border-radius: 5px;">
                    {reset_url}
                </p>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 14px;">
                    <p><strong>重要提醒：</strong></p>
                    <ul>
                        <li>此链接将在1小时后失效</li>
                        <li>如果您没有请求重置密码，请忽略此邮件</li>
                        <li>为了账户安全，请不要将此链接分享给他人</li>
                    </ul>
                </div>
                
                <p style="color: #666; font-size: 12px; text-align: center; margin-top: 30px;">
                    此邮件由系统自动发送，请勿回复
                </p>
            </div>
        </body>
        </html>
        """


email_service = EmailService()
```

## 📝 需要修改的现有文件

### 1. 修改用户模型
**文件路径：** `backend/app/models/user.py`

**在User类中添加以下关联关系：**
```python
# 在类的末尾添加这一行
password_resets: Mapped[List["PasswordReset"]] = relationship(
    "PasswordReset", back_populates="user", cascade="all, delete-orphan"
)
```

### 2. 修改配置文件
**文件路径：** `backend/app/core/config.py`

**在Settings类之前添加邮件配置类：**
```python
class EmailSettings(BaseSettings):
    """邮件服务配置"""
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    USERNAME: str = ""
    PASSWORD: str = ""
    FROM_EMAIL: str = ""
    USE_TLS: bool = True

    model_config = SettingsConfigDict(
        env_prefix="EMAIL_",
        env_file=[".env.local", ".env"],
        env_file_encoding="utf-8",
        extra="allow"
    )
```

**在Settings主类中添加邮件配置：**
```python
# 在子配置部分添加
email: EmailSettings = EmailSettings()
```

### 3. 修改认证路由
**文件路径：** `backend/app/api/v1/routes/auth_routes.py`

**在文件顶部添加导入：**
```python
from app.schemas.password_reset import (
    PasswordResetRequest, 
    PasswordResetConfirm, 
    PasswordResetResponse
)
from app.crud.password_reset import password_reset as crud_password_reset
from app.services.email_service import email_service
from app.core.security import get_password_hash
```

**在文件末尾添加新的路由端点：**
```python
@router.post("/forgot-password", response_model=PasswordResetResponse)
async def forgot_password(
    request_data: PasswordResetRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> PasswordResetResponse:
    """
    发送密码重置邮件
    
    - **email**: 用户邮箱地址
    """
    try:
        # 查找用户
        user = await crud_user.get_by_email(db, email=request_data.email)
        
        # 即使用户不存在，也返回成功消息（安全考虑，不暴露用户是否存在）
        if not user:
            return PasswordResetResponse(
                message="如果该邮箱地址存在于我们的系统中，您将收到密码重置邮件"
            )
        
        # 创建密码重置令牌
        reset_token = await crud_password_reset.create(db, user_id=user.id)
        
        # 发送邮件
        email_sent = await email_service.send_password_reset_email(
            to_email=user.email,
            reset_token=reset_token.token,
            user_name=user.full_name or user.username
        )
        
        if not email_sent:
            raise ValueError("邮件发送失败，请稍后重试")
        
        return PasswordResetResponse(
            message="如果该邮箱地址存在于我们的系统中，您将收到密码重置邮件"
        )
        
    except Exception as e:
        raise handle_error(e)


@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password(
    reset_data: PasswordResetConfirm,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> PasswordResetResponse:
    """
    重置密码
    
    - **token**: 密码重置令牌
    - **new_password**: 新密码
    """
    try:
        # 验证令牌
        reset_token = await crud_password_reset.get_by_token(db, token=reset_data.token)
        
        if not reset_token or not reset_token.is_valid:
            raise ValueError("无效或已过期的重置令牌")
        
        # 获取用户
        user = await crud_user.get(db, id=reset_token.user_id)
        if not user:
            raise ValueError("用户不存在")
        
        # 更新密码
        hashed_password = get_password_hash(reset_data.new_password)
        user.hashed_password = hashed_password
        
        # 标记令牌为已使用
        await crud_password_reset.use_token(db, token=reset_data.token)
        
        # 吊销用户的所有刷新令牌（强制重新登录）
        await crud_refresh_token.revoke_all_for_user(db, user_id=user.id)
        
        await db.commit()
        
        return PasswordResetResponse(
            message="密码重置成功，请使用新密码登录"
        )
        
    except Exception as e:
        raise handle_error(e)


@router.post("/verify-reset-token", response_model=PasswordResetResponse)
async def verify_reset_token(
    token: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> PasswordResetResponse:
    """
    验证密码重置令牌是否有效
    
    - **token**: 密码重置令牌
    """
    try:
        reset_token = await crud_password_reset.get_by_token(db, token=token)
        
        if not reset_token or not reset_token.is_valid:
            return PasswordResetResponse(
                message="令牌无效或已过期",
                success=False
            )
        
        return PasswordResetResponse(
            message="令牌有效"
        )
        
    except Exception as e:
        raise handle_error(e)
```

### 4. 修改模型导入文件
**文件路径：** `backend/app/models/__init__.py`

**修改导入和__all__列表：**
```python
from .user import User
from .token import RefreshToken
from .password_reset import PasswordReset
from .bot_config import BotConfig
from .scrape_session import ScrapeSession
from .reddit_content import RedditPost, RedditComment

__all__ = [
    "User",
    "RefreshToken", 
    "PasswordReset",
    "BotConfig",
    "ScrapeSession", 
    "RedditPost",
    "RedditComment",
]
```

### 5. 修改Schema导入文件
**文件路径：** `backend/app/schemas/__init__.py`

**修改导入和__all__列表：**
```python
from .user import (
    UserBase, UserCreate, UserResponse, UserUpdate, User
)
from .auth import LoginRequest
from .token import Token
from .password_reset import (
    PasswordResetRequest, PasswordResetConfirm, PasswordResetResponse
)

__all__ = [
    # User models
    "UserBase", "UserCreate", "UserResponse", "UserUpdate", "User",
    
    # Auth models
    "LoginRequest", "Token",
    
    # Password reset models
    "PasswordResetRequest", "PasswordResetConfirm", "PasswordResetResponse"
]
```

### 6. 修改数据库基础文件
**文件路径：** `backend/app/db/base.py`

**修改模型导入：**
```python
# Import all models here for Alembic
from app.models.user import User
from app.models.token import RefreshToken
from app.models.password_reset import PasswordReset

# Re-export Base and all models for Alembic
__all__ = ["Base", "User", "RefreshToken", "PasswordReset"]
```

## 🔧 环境变量配置

**在项目根目录的 `.env` 文件中添加：**
```env
# 邮件服务配置（Gmail）
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=你的gmail邮箱@gmail.com
EMAIL_PASSWORD=你的16位应用专用密码
EMAIL_FROM_EMAIL=你的gmail邮箱@gmail.com
EMAIL_USE_TLS=true
```

## 🧪 API端点说明

完成后将新增以下API端点：

1. **发送重置邮件**: `POST /api/v1/auth/forgot-password`
2. **验证重置令牌**: `POST /api/v1/auth/verify-reset-token` 
3. **重置密码**: `POST /api/v1/auth/reset-password`

## ✅ 完成检查清单

- [ ] 创建所有新文件
- [ ] 修改所有指定的现有文件
- [ ] 配置环境变量
- [ ] 运行数据库迁移
- [ ] 测试API端点功能

完成以上所有步骤后，找回密码功能就可以正常使用了。