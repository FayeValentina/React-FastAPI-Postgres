from fastapi import APIRouter, Depends, Request
from typing import Annotated, Dict, Literal

from app.schemas.dependency_demo import RequestInfo, AuditLog, DemoResponse
from app.api.v1.dependencies.audit import (
    app_level_dependency,
    router_level_dependency,
    endpoint_level_dependency,
    get_audit_context,
    AuditContext
)

# 创建路由器，添加路由级别依赖项
router = APIRouter(
    prefix="/dependency-demo",
    tags=["dependency-demo"],
    dependencies=[Depends(router_level_dependency)]  # 2️⃣ 路由级别依赖项
)

async def get_endpoint_audit(
    operation: Literal["get_items", "get_users"],
    request: Request,
    audit_ctx: AuditContext = Depends(get_audit_context)
) -> Dict:
    """
    获取端点的审计日志
    
    Args:
        operation: 操作名称，限定为 "get_items" 或 "get_users"
        request: FastAPI 请求对象
        audit_ctx: 审计上下文对象

    Returns:
        包含审计信息的字典
    """
    return await endpoint_level_dependency(
        operation=operation,
        request=request,
        audit_ctx=audit_ctx
    )

def create_demo_response(
    *,
    message: str,
    request_info: Dict,
    audit_log: Dict,
    data: Dict
) -> DemoResponse:
    """
    创建演示响应

    Args:
        message: 响应消息
        request_info: 请求信息字典
        audit_log: 审计日志字典
        data: 响应数据字典

    Returns:
        DemoResponse 对象
    """
    return DemoResponse(
        message=message,
        request_info=RequestInfo(**request_info),
        audit_log=AuditLog(**audit_log),
        data=data
    )

@router.get(
    "/items",
    response_model=DemoResponse,
    dependencies=[Depends(endpoint_level_dependency)],   # 3️⃣ 端点装饰器级别依赖项
    description="依赖注入示例端点 - 获取商品列表",
    summary="获取商品列表（依赖注入演示）"
)
async def get_items(
    request: Request,
    request_info: Annotated[Dict, Depends(app_level_dependency)],      # 1️⃣ 全局依赖项（在main.py中设置）
    audit_log: Annotated[Dict, Depends(endpoint_level_dependency)]     # 4️⃣ 端点参数级别依赖项
) -> DemoResponse:
    """
    依赖注入示例端点 - 获取商品列表
    
    展示不同级别依赖项的执行顺序：
    1. 全局依赖项（在FastAPI应用实例中设置）
    2. 路由级别依赖项（在路由器创建时添加）
    3. 端点装饰器级别依赖项（通过路径装饰器的dependencies参数添加）
    4. 端点参数级别依赖项（在路径操作函数参数中添加）

    Returns:
        包含请求信息、审计日志和商品数据的响应对象
    """
    print("5️⃣ 执行路径操作函数 - get_items")
    
    return create_demo_response(
        message="Dependency injection demo",
        request_info=request_info,
        audit_log=audit_log,
        data={"items": ["item1", "item2"]}
    )

@router.get(
    "/users",
    response_model=DemoResponse,
    dependencies=[Depends(endpoint_level_dependency)],   # 3️⃣ 端点装饰器级别依赖项
    description="依赖注入示例端点 - 获取用户列表",
    summary="获取用户列表（依赖注入演示）"
)
async def get_users(
    request: Request,
    request_info: Annotated[Dict, Depends(app_level_dependency)],      # 1️⃣ 全局依赖项（在main.py中设置）
    audit_log: Annotated[Dict, Depends(endpoint_level_dependency)]     # 4️⃣ 端点参数级别依赖项
) -> DemoResponse:
    """
    依赖注入示例端点 - 获取用户列表
    
    与 get_items 端点类似，展示相同的依赖注入执行顺序：
    1. 全局依赖项（在FastAPI应用实例中设置）
    2. 路由级别依赖项（在路由器创建时添加）
    3. 端点装饰器级别依赖项（通过路径装饰器的dependencies参数添加）
    4. 端点参数级别依赖项（在路径操作函数参数中添加）

    Returns:
        包含请求信息、审计日志和用户数据的响应对象
    """
    print("5️⃣ 执行路径操作函数 - get_users")
    
    return create_demo_response(
        message="Dependency injection demo - users",
        request_info=request_info,
        audit_log=audit_log,
        data={"users": ["user1", "user2"]}
    ) 