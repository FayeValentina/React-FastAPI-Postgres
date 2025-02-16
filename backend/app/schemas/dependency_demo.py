from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime

class RequestInfo(BaseModel):
    """请求信息模型"""
    client_host: str
    user_agent: str
    request_id: str
    timestamp: datetime

class AuditLog(BaseModel):
    """审计日志模型"""
    operation: str
    path: str
    method: str
    request_id: str
    execution_order: List[str]
    execution_time: float
    user_id: Optional[int] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "operation": "get_items",
                "path": "/api/v1/dependency-demo/items",
                "method": "GET",
                "request_id": "123e4567-e89b-12d3-a456-426614174000",
                "execution_order": [
                    "app_level_dependency",
                    "router_level_dependency",
                    "endpoint_level_dependency"
                ],
                "execution_time": 0.123,
                "user_id": 1
            }
        }
    }

class DemoResponse(BaseModel):
    """示例响应模型"""
    message: str
    request_info: RequestInfo
    audit_log: AuditLog
    data: Dict = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Dependency injection demo",
                "request_info": {
                    "client_host": "127.0.0.1",
                    "user_agent": "Mozilla/5.0",
                    "request_id": "123e4567-e89b-12d3-a456-426614174000",
                    "timestamp": "2024-02-16T12:00:00"
                },
                "audit_log": {
                    "operation": "get_items",
                    "path": "/api/v1/dependency-demo/items",
                    "method": "GET",
                    "request_id": "123e4567-e89b-12d3-a456-426614174000",
                    "execution_order": [
                        "app_level_dependency",
                        "router_level_dependency",
                        "endpoint_level_dependency"
                    ],
                    "execution_time": 0.123,
                    "user_id": 1
                },
                "data": {
                    "items": ["item1", "item2"]
                }
            }
        }
    } 