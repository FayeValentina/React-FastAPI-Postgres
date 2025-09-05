from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import json
from typing import Callable, Dict, Any
from loguru import logger
import uuid

class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    """
    增强版请求响应记录中间件
    记录详细的请求和响应信息以及处理时间
    """
    def __init__(
        self, 
        app: ASGIApp, 
        log_request_body: bool = True,
        log_response_body: bool = True,
        max_body_length: int = 1024,
        exclude_paths: list[str] = None,
        exclude_extensions: list[str] = None
    ):
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_length = max_body_length
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json"]
        self.exclude_extensions = exclude_extensions or [".css", ".js", ".ico", ".png", ".jpg", ".svg"]
        
    async def dispatch(
        self, 
        request: Request, 
        call_next: Callable
    ) -> Response:
        # 生成请求ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 标记请求已被记录，避免其他组件重复记录
        request.state._request_logged = True
        
        # 检查是否应该跳过日志记录
        if self._should_skip_logging(request):
            return await call_next(request)
            
        # 记录开始时间
        start_time = time.time()
        
        # 收集请求信息
        try:
            request_info = await self._collect_request_info(request)
        except Exception as e:
            logger.error(f"Error collecting request info: {str(e)}")
            request_info = {
                "method": request.method,
                "url": str(request.url),
                "error": f"Error collecting request info: {str(e)}"
            }
        
        response = None
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算请求处理时间
            duration = round(time.time() - start_time, 3)
            
            # 收集响应信息，但不尝试读取流式响应的响应体
            try:
                response_info = self._collect_response_info(response, duration)
            except Exception as e:
                logger.error(f"Error collecting response info: {str(e)}")
                response_info = {
                    "status_code": response.status_code if hasattr(response, "status_code") else 500,
                    "duration": duration,
                    "error": f"Error collecting response info: {str(e)}"
                }
            
            # 记录完整请求/响应信息
            self._log_request_response(request_id, request_info, response_info)
            
            # 添加响应时间到响应头
            if hasattr(response, "headers"):
                response.headers["X-Process-Time"] = str(duration)
                response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # 即使发生错误也记录请求信息和错误详情
            duration = round(time.time() - start_time, 3)
            
            error_info = {
                "status_code": 500,
                "duration": duration,
                "headers": {},
                "body": str(e),
                "error": f"{type(e).__name__}: {str(e)}"
            }
            
            self._log_request_response(request_id, request_info, error_info, is_error=True)
            
            # 重新抛出异常
            raise
    
    def _should_skip_logging(self, request: Request) -> bool:
        """判断是否应该跳过日志记录"""
        path = request.url.path
        
        # 检查排除路径
        for excluded_path in self.exclude_paths:
            if excluded_path.endswith('*'):
                if path.startswith(excluded_path[:-1]):
                    return True
            elif path == excluded_path:
                return True
        
        # 检查排除扩展名
        for ext in self.exclude_extensions:
            if path.endswith(ext):
                return True
                
        return False
    
    async def _collect_request_info(self, request: Request) -> Dict[str, Any]:
        """收集请求详细信息"""
        headers = dict(request.headers)
        # 移除敏感信息
        if "authorization" in headers:
            headers["authorization"] = "Bearer [FILTERED]"
        if "cookie" in headers:
            headers["cookie"] = "[FILTERED]"
        
        info = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "path_params": dict(request.path_params),
            "query_params": dict(request.query_params),
            "headers": headers,
            "client": {
                "host": request.client.host if request.client else None,
                "port": request.client.port if request.client else None
            }
        }
        
        # 获取并解析请求体（如果存在且需要记录）
        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await self._get_request_body(request)
                info["body"] = self._truncate_body(body)
            except Exception as e:
                info["body"] = f"[Error reading body: {str(e)}]"
        
        return info
    
    async def _get_request_body(self, request: Request) -> str:
        """获取请求体内容"""
        try:
            # 读取但不消费请求体
            body = await request.body()
            
            # 不再修改request._receive，这可能导致ASGI协议问题
            # 因为FastAPI/Starlette已经有自己的请求体缓存机制
            
            if not body:
                return ""
                
            # 尝试作为JSON解析
            if request.headers.get("content-type", "").startswith("application/json"):
                try:
                    json_body = json.loads(body)
                    # 过滤敏感字段
                    self._filter_sensitive_data(json_body)
                    return json.dumps(json_body, ensure_ascii=False)
                except json.JSONDecodeError:
                    return f"[Invalid JSON data, length: {len(body)} bytes]"
            # 表单数据
            elif request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
                return f"[Form data, length: {len(body)} bytes]"
            # 文件上传
            elif request.headers.get("content-type", "").startswith("multipart/form-data"):
                return f"[Multipart form data, length: {len(body)} bytes]"
            # 其他格式
            else:
                try:
                    return body.decode('utf-8')
                except UnicodeDecodeError:
                    return f"[Binary data, length: {len(body)} bytes]"
        except Exception as e:
            logger.error(f"Error reading request body: {str(e)}")
            return f"[Error reading body: {str(e)}]"
    
    def _collect_response_info(self, response: Response, duration: float) -> Dict[str, Any]:
        """收集响应详细信息"""
        # 确保我们可以安全地访问响应属性
        if not hasattr(response, "status_code"):
            return {
                "status_code": 500,
                "duration": duration,
                "headers": {},
                "body": "[Unable to capture response body]"
            }
            
        info = {
            "status_code": response.status_code,
            "duration": duration,
            "headers": dict(response.headers) if hasattr(response, "headers") else {}
        }
        
        # 获取并解析响应体（仅当我们确定响应体可用且不是流式响应）
        if self.log_response_body and hasattr(response, 'body') and response.body is not None:
            try:
                body = response.body
                if body:
                    if response.headers.get("content-type", "").startswith("application/json"):
                        try:
                            # 尝试解析JSON并过滤敏感数据
                            json_body = json.loads(body)
                            self._filter_sensitive_data(json_body)
                            info["body"] = self._truncate_body(json.dumps(json_body, ensure_ascii=False))
                        except Exception:
                            info["body"] = self._truncate_body(body.decode('utf-8', errors='replace'))
                    else:
                        content_type = response.headers.get("content-type", "")
                        if content_type.startswith("text/"):
                            info["body"] = self._truncate_body(body.decode('utf-8', errors='replace'))
                        else:
                            info["body"] = f"[Binary data, length: {len(body)} bytes]"
            except Exception as e:
                info["body"] = f"[Error reading response body: {str(e)}]"
        else:
            # 处理流式响应的情况
            info["body"] = "[Streaming response - body not captured]"
        
        return info
    
    def _truncate_body(self, body: str) -> str:
        """截断过长的请求/响应体"""
        if isinstance(body, bytes):
            try:
                body = body.decode('utf-8', errors='replace')
            except Exception:
                return f"[Binary data, length: {len(body)} bytes]"
                
        if isinstance(body, str) and len(body) > self.max_body_length:
            return body[:self.max_body_length] + f"... [truncated, total length: {len(body)} chars]"
        return body
    
    def _filter_sensitive_data(self, data: Any) -> None:
        """过滤敏感数据"""
        if isinstance(data, dict):
            sensitive_fields = [
                "password", "token", "secret", "credential", "pwd", "auth",
                "credit_card", "card_number", "cvv", "ssn", "key"
            ]
            
            for key in list(data.keys()):
                if any(sensitive in key.lower() for sensitive in sensitive_fields):
                    data[key] = "[FILTERED]"
                elif isinstance(data[key], (dict, list)):
                    self._filter_sensitive_data(data[key])
        elif isinstance(data, list):
            for item in data:
                self._filter_sensitive_data(item)
    
    def _log_request_response(
        self, 
        request_id: str, 
        request_info: Dict[str, Any], 
        response_info: Dict[str, Any],
        is_error: bool = False
    ) -> None:
        """记录请求和响应信息"""
        log_message = [
            f"🔍 请求/响应详情 [ID: {request_id}]:",
            "╭─ 请求信息 ────────────────────────────────────",
            f"│ 方法: {request_info['method']}",
            f"│ URL: {request_info['url']}",
            f"│ 路径参数: {json.dumps(request_info['path_params'], ensure_ascii=False)}",
            f"│ 查询参数: {json.dumps(request_info['query_params'], ensure_ascii=False)}",
            f"│ 客户端: {request_info['client']['host']}:{request_info['client']['port']}"
        ]
        
        # 添加请求头信息
        log_message.append("│ 请求头:")
        for name, value in request_info.get('headers', {}).items():
            log_message.append(f"│   {name}: {value}")
        
        # 添加请求体（如果存在）
        if 'body' in request_info:
            log_message.append("│ 请求体:")
            body_lines = str(request_info['body']).split('\n')
            for line in body_lines:
                log_message.append(f"│   {line}")
        
        # 添加响应信息
        log_message.append("├─ 响应信息 ────────────────────────────────────")
        log_message.append(f"│ 状态码: {response_info['status_code']}")
        log_message.append(f"│ 处理时间: {response_info['duration']}秒")
        
        # 添加错误信息（如果有）
        if is_error or 'error' in response_info:
            log_message.append(f"│ 错误: {response_info.get('error', 'Unknown error')}")
        
        # 添加响应头信息
        log_message.append("│ 响应头:")
        for name, value in response_info.get('headers', {}).items():
            log_message.append(f"│   {name}: {value}")
        
        # 添加响应体（如果存在）
        if 'body' in response_info:
            log_message.append("│ 响应体:")
            body_lines = str(response_info['body']).split('\n')
            for line in body_lines:
                log_message.append(f"│   {line}")
        
        log_message.append("╰───────────────────────────────────────────────")
        
        # 根据响应状态选择日志级别
        if is_error or response_info.get('status_code', 500) >= 500:
            logger.error("\n".join(log_message))
        elif response_info.get('status_code', 400) >= 400:
            logger.warning("\n".join(log_message))
        else:
            logger.info("\n".join(log_message))
