from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

import aiosmtplib

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
            
            # 使用异步 SMTP 客户端发送邮件，避免阻塞事件循环
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_server,
                port=self.smtp_port,
                start_tls=self.use_tls,
                username=self.username or None,
                password=self.password or None,
            )
            
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
