from fastapi import Request, Depends
from typing import List, Optional, Dict
import time
import uuid
from datetime import datetime
import logging

# 设置日志记录器
logger = logging.getLogger(__name__)

class AuditContext:
    """
    审计上下文，用于在依赖项之间共享数据
    
    Attributes:
        start_time: 请求开始时间戳
        request_id: 唯一请求标识符
        execution_order: 依赖项执行顺序列表
        user_id: 可选的用户ID
    """
    def __init__(self):
        self.start_time: float = time.time()
        self.request_id: str = str(uuid.uuid4())
        self.execution_order: List[str] = []
        self.user_id: Optional[int] = None
        print(f"\n[初始化] 创建新的审计上下文 (request_id: {self.request_id})")

    def add_execution_step(self, step: str) -> None:
        """
        添加执行步骤到执行顺序列表
        
        Args:
            step: 执行步骤名称
        """
        if step not in self.execution_order:  # 防止重复添加
            self.execution_order.append(step)
            print(f"[执行步骤 {len(self.execution_order)}] {step}")

    def get_execution_time(self) -> float:
        """
        计算执行时间
        
        Returns:
            从请求开始到现在的执行时间（秒）
        """
        execution_time = round(time.time() - self.start_time, 3)
        print(f"[执行时间] {execution_time}秒")
        return execution_time


def get_audit_context(request: Request) -> AuditContext:
    """
    获取或创建请求级别的审计上下文
    
    Args:
        request: FastAPI 请求对象
        
    Returns:
        AuditContext: 当前请求的审计上下文
    """
    # 使用请求状态存储上下文
    context_key = "audit_context"
    if context_key not in request.state.__dict__:
        print("\n1️⃣ 创建审计上下文")
        request.state.__dict__[context_key] = AuditContext()
    return request.state.__dict__[context_key]

async def app_level_dependency(
    request: Request,
    audit_ctx: AuditContext = Depends(get_audit_context)
) -> Dict:
    """
    应用级别的依赖项，最先执行
    包含响应时间追踪功能
    
    Args:
        request: FastAPI 请求对象
        audit_ctx: 审计上下文实例

    Returns:
        包含请求基本信息的字典
    """
    print("\n2️⃣ 执行应用级别依赖项")
    audit_ctx.add_execution_step("app_level_dependency")
    
    return {
        "client_host": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "request_id": audit_ctx.request_id,
        "timestamp": datetime.now()
    }

async def router_level_dependency(
    request: Request,
    audit_ctx: AuditContext = Depends(get_audit_context)
) -> str:
    """
    路由级别的依赖项，在应用级别之后执行
    
    Args:
        request: FastAPI 请求对象
        audit_ctx: 审计上下文实例

    Returns:
        包含执行时间的字符串
    """
    print("\n3️⃣ 执行路由级别依赖项")
    audit_ctx.add_execution_step("router_level_dependency")
    return f"Router dependency executed at {time.time()}"

async def endpoint_level_dependency(
    request: Request,
    audit_ctx: AuditContext = Depends(get_audit_context)
) -> Dict:
    """
    端点级别的依赖项，最后执行
    
    Args:
        request: FastAPI 请求对象
        audit_ctx: 审计上下文实例

    Returns:
        包含完整审计信息的字典
    """
    print("\n4️⃣ 执行端点级别依赖项")
    audit_ctx.add_execution_step("endpoint_level_dependency")
    
    result = {
        "operation": request.url.path.split("/")[-1],
        "path": request.url.path,
        "method": request.method,
        "request_id": audit_ctx.request_id,
        "execution_order": audit_ctx.execution_order,
        "execution_time": audit_ctx.get_execution_time(),
        "user_id": audit_ctx.user_id
    }
    
    print(f"[完成] 依赖项执行顺序: {' -> '.join(audit_ctx.execution_order)}")
    return result 