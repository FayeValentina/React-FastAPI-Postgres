from fastapi import APIRouter, Path, Query, Body, Cookie, Header, HTTPException, Depends, Form, File, UploadFile
from fastapi.responses import JSONResponse
from typing import Annotated, List, Optional, Dict
from datetime import datetime, timedelta
import pytz  # 用于处理时区
import uuid  # 用于生成唯一的会话ID
from datetime import timezone

from app.schemas.example import (
    ItemCreate,
    ItemResponse,
    UserProfile,
    UserLevel,
    Address,
    SessionResponse,
    PreferencesResponse,
    ThemePreferenceResponse,
    LoginResponse,
    UserLevelResponse,
    LoginRequest,
    LoginFormResponse,
    FileUploadResponse,
    MultipleFilesResponse,
    FileWithMetadataResponse
)

router = APIRouter()

@router.get("/items/{item_id}")
async def get_item(
    # 路径参数：商品ID
    item_id: Annotated[int, Path(title="Item ID", ge=1)],
    # 查询参数：可选的搜索词
    q: Annotated[Optional[str], Query(min_length=3, max_length=50)] = None,
    # 以下是各种HTTP头部参数
    user_agent: Annotated[str | None, Header()] = None,
    accept: Annotated[str | None, Header()] = None,
    accept_language: Annotated[str | None, Header()] = None,
    accept_encoding: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    cache_control: Annotated[str | None, Header()] = None,
    connection: Annotated[str | None, Header()] = None,
    cookie: Annotated[str | None, Header()] = None,
    referer: Annotated[str | None, Header()] = None,
    origin: Annotated[str | None, Header()] = None
):
    """
    获取商品详情，演示各种HTTP头部的使用
    """
    # 打印所有接收到的参数，用于调试
    print("item_id:", item_id)
    print("q:", q)
    print("user_agent:", user_agent)
    print("accept:", accept)
    print("accept_language:", accept_language)
    print("accept_encoding:", accept_encoding)
    print("authorization:", authorization)
    print("cache_control:", cache_control)
    print("connection:", connection)
    print("cookie:", cookie)
    print("referer:", referer)
    print("origin:", origin)

    return {
        "item_id": item_id,
        "q": q,
        "user_agent": user_agent,
        "accept": accept,
        "accept_language": accept_language,
        "accept_encoding": accept_encoding,
        "authorization": authorization,
        "cache_control": cache_control,
        "connection": connection,
        "cookie": cookie,
        "referer": referer,
        "origin": origin
    }


@router.post("/items/", response_model=ItemResponse)
async def create_item(
    # 使用Body和示例数据验证请求体
    item: Annotated[ItemCreate, Body(
        examples={
            "normal": {
                "summary": "A normal example",
                "value": {
                    "name": "Foo",
                    "description": "A very nice Item",
                    "price": 35.4,
                    "tax": 0.2,
                    "tags": ["tag1", "tag2"],
                    "category": "category1"
                }
            }
        }
    )],
    x_token: Annotated[str | None, Header()] = None
) -> ItemResponse:
    """
    创建新商品，需要在header中提供x-token
    """
    # 验证token
    if not x_token:
        raise HTTPException(status_code=400, detail="X-Token header is required")
    
    # 模拟数据库响应
    return {
        **item.model_dump(),
        "id": 1,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }


@router.post("/login/", response_model=LoginFormResponse)
async def login(
    login_data: LoginRequest
) -> LoginFormResponse:
    """
    登录接口，演示响应模型过滤
    """
    # 这里可以添加实际的密码验证逻辑
    # 即使我们在函数内部访问了password，它也不会出现在响应中
    print(f"Password received: {login_data.password}")  # 仅用于演示
    
    return {
        "username": login_data.username,
        "remember_me": login_data.remember_me,
        "message": "Login successful"
    }


@router.post("/users/profile")
async def create_profile(
    profile: UserProfile,
    address: Annotated[Address, Body()],
    priority: Annotated[int, Query(gt=0, le=5)] = 1,
    api_key: Annotated[str | None, Header()] = None
) -> UserProfile:
    """
    创建用户资料，包含嵌套模型和多个参数
    """
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")
    
    return {
        "profile": profile,
        "address": address,
        "priority": priority
    }


@router.get("/users/levels/{level}", response_model=UserLevelResponse)
async def get_users_by_level(
    level: UserLevel,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0
) -> UserLevelResponse:
    """
    根据用户等级获取用户列表，使用枚举类型
    """
    return {
        "level": level,
        "limit": limit,
        "offset": offset
    }


# Custom response with headers
@router.get("/custom-header")
async def get_custom_header() -> JSONResponse:
    """
    返回自定义响应头的示例
    """
    content = {"message": "Hello World"}
    headers = {"X-Custom-Header": "custom_value", "X-Another-Header": "another_value"}
    return JSONResponse(content=content, headers=headers)


# Multiple body parameters
@router.put("/items/{item_id}")
async def update_item(
    item_id: int,
    item: Annotated[ItemCreate, Body(embed=True)],
    user: Annotated[UserProfile, Body(embed=True)],
    importance: Annotated[int, Body(gt=0, lt=10)]
):
    """
    更新商品信息，演示多个请求体参数的使用
    """
    return {
        "item_id": item_id,
        "item": item,
        "user": user,
        "importance": importance
    }


@router.post("/preferences/theme")
async def set_theme_preference(
    theme: Annotated[str, Query(pattern="^(light|dark|system)$")],
    remember: Annotated[bool, Query()] = False
) -> JSONResponse:
    """
    设置用户主题偏好，存储在cookie中
    """
    content = {"message": f"Theme preference set to {theme}"}
    response = JSONResponse(content=content)
    
    # 设置cookie过期时间
    expires = datetime.now(timezone.utc) + timedelta(days=30) if remember else None
    
    response.set_cookie(
        key="theme",
        value=theme,
        expires=expires,
        httponly=True,
        samesite="lax",
        secure=False  # 开发环境使用False
    )
    
    return response


# 读取主题偏好
@router.get("/preferences/theme", response_model=ThemePreferenceResponse)
async def get_theme_preference(
    theme: Annotated[str | None, Cookie()] = None
) -> ThemePreferenceResponse:
    """
    从cookie中获取用户主题偏好
    """
    if not theme:
        return {"theme": "default", "message": "No theme preference set"}
    return {"theme": theme, "message": "Theme preference found"}


@router.post("/preferences/language")
async def set_language_preference(
    language: Annotated[str, Query(pattern="^(en|zh|es|fr|jp)$")],
    remember: Annotated[bool, Query()] = False
) -> JSONResponse:
    """
    设置用户语言偏好，存储在cookie中
    """
    content = {"message": f"Language preference set to {language}"}
    response = JSONResponse(content=content)
    
    expires = datetime.now(timezone.utc) + timedelta(days=30) if remember else None
    
    response.set_cookie(
        key="language",
        value=language,
        expires=expires,
        httponly=True,
        samesite="lax",
        secure=False
    )
    
    return response


# 使用多个Cookie进行验证
@router.get("/preferences", response_model=PreferencesResponse)
async def get_user_preferences(
    theme: Annotated[str | None, Cookie()] = None,
    language: Annotated[str | None, Cookie()] = None,
    session_id: Annotated[str | None, Cookie()] = None
) -> PreferencesResponse:
    """
    获取所有用户偏好设置，从cookie中读取
    """
    preferences = {
        "theme": theme or "default",
        "language": language or "en",
        "is_authenticated": bool(session_id)
    }
    
    if not session_id:
        return {
            "preferences": preferences,
            "message": "Some preferences might not be available without authentication"
        }
    else:
        return {
            "preferences": preferences,
            "message": "All preferences retrieved successfully"
        }


@router.post("/auth/login-simulation", response_model=LoginResponse)
async def simulate_login(
    user_id: Annotated[int, Query(ge=1)],
    remember: Annotated[bool, Query()] = False
) -> LoginResponse:
    """
    模拟登录过程，设置session ID cookie
    注意：这只是演示用途，实际应用中应该使用proper authentication
    """
    session_id = str(uuid.uuid4())
    
    print("session_id: ", session_id)
    content = {
        "message": "Login successful",
        "user_id": user_id,
        "session_id": session_id
    }
    
    utc_now = datetime.now(timezone.utc)
    expires = utc_now + (
        timedelta(days=30) if remember else timedelta(hours=2)
    )
    
    response = JSONResponse(content=content)
    response.set_cookie(
        key="session_id",
        value=session_id,
        expires=expires,
        httponly=True,
        samesite="lax",
        secure=False,  # 开发环境使用False
        max_age=2592000 if remember else 7200,
        domain="localhost",
        path="/"
    )
    
    return response


# 登出路由
@router.post("/auth/logout")
async def logout() -> JSONResponse:
    """
    退出登录，清除session cookie
    """
    response = JSONResponse(content={"message": "Logged out successfully"})
    
    response.delete_cookie(
        key="session_id",
        httponly=True,
        samesite="lax",
        secure=False
    )
    
    return response


# 检查会话状态
@router.get("/auth/session", response_model=SessionResponse)
async def check_session(
    session_id: Annotated[str | None, Cookie()] = None
) -> SessionResponse:
    """
    检查用户会话状态
    """
    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    
    return {
        "message": "Session is valid",
        "session_id": session_id
    }


@router.post("/upload/", response_model=FileUploadResponse)
async def upload_file(
    file: Annotated[UploadFile, File(description="A file read as UploadFile")],
    description: Annotated[Optional[str], Form(description="File description")] = None,
    tags: Annotated[str, Form(description="Comma separated tags")] = "",
) -> FileUploadResponse:
    """
    使用multipart/form-data上传单个文件
    
    参数说明：
    - file: 要上传的文件
    - description: 可选的文件描述
    - tags: 逗号分隔的标签列表
    """
    # 读取文件内容以获取大小
    contents = await file.read()
    file_size = len(contents)
    
    # 重置文件指针，以便后续操作
    await file.seek(0)
    
    # 处理标签
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "file_size": file_size,
        "description": description,
        "tags": tag_list
    }


@router.post("/upload-files/", response_model=MultipleFilesResponse)
async def upload_files(
    files: Annotated[List[bytes], File(description="Multiple files as bytes")],
    fileb: Annotated[bytes, File(description="Single file as bytes")],
) -> MultipleFilesResponse:
    """
    使用bytes模式上传多个文件
    
    参数说明：
    - files: 多个文件的列表，每个文件都会被完整加载到内存中
    - fileb: 单个额外的文件
    
    注意：此方法仅适用于小文件，因为会将整个文件加载到内存中
    """
    return {
        "file_sizes": [len(file) for file in files],
        "fileb_size": len(fileb),
        "message": f"Successfully uploaded {len(files) + 1} files",
        "total_size": sum(len(file) for file in files) + len(fileb)
    }


@router.post("/upload-file-with-metadata/", response_model=FileWithMetadataResponse)
async def upload_file_with_metadata(
    file: Annotated[bytes, File()],
    filename: Annotated[str, Form()],
    content_type: Annotated[str, Form()] = "application/octet-stream",
    description: Annotated[Optional[str], Form()] = None
) -> FileWithMetadataResponse:
    """
    上传带元数据的单个文件
    
    参数说明：
    - file: 文件内容（二进制）
    - filename: 文件名
    - content_type: 文件类型
    - description: 可选的文件描述
    
    注意：此方法将整个文件加载到内存中，仅适用于小文件
    """
    file_content = file  # 在实际应用中，你可能想要保存到磁盘或进行处理
    
    return {
        "filename": filename,
        "content_type": content_type,
        "description": description,
        "file_size": len(file_content),
        "first_bytes": file_content[:10].hex(),  # 显示前10个字节的十六进制表示
        "message": "File successfully processed"
    } 