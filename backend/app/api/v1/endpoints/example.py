from fastapi import APIRouter, Path, Query, Body, Cookie, Header, HTTPException, Depends, Form, File, UploadFile
from fastapi.responses import JSONResponse
from typing import Annotated, List, Optional, Dict
from datetime import datetime, timedelta
import pytz  # 添加 pytz 用于处理时区
import uuid  # 添加 uuid 用于生成唯一的会话ID
from datetime import timezone  # 添加这一行

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
    FileUploadResponse
)

router = APIRouter()

@router.get("/items/{item_id}")
async def get_item(
    item_id: Annotated[int, Path(title="Item ID", ge=1)],
    q: Annotated[Optional[str], Query(min_length=3, max_length=50)] = None,
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
    Get item by ID with optional query parameter and header
    """
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
    Create a new item with body validation
    """
    if not x_token:
        raise HTTPException(status_code=400, detail="X-Token header is required")
    
    # Simulate database response
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
    Login endpoint demonstrating response model filtering
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
    Create user profile with nested models and multiple parameters
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
    Get users by level using enum
    """
    return {
        "level": level,
        "limit": limit,
        "offset": offset
    }


# Custom response with headers
@router.get("/custom-header")
async def get_custom_header() -> JSONResponse:
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
    Update item with multiple body parameters
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
    Set user's theme preference in cookie
    """
    content = {"message": f"Theme preference set to {theme}"}
    response = JSONResponse(content=content)
    
    # 使用 datetime.now(timezone.utc) 替代 pytz
    expires = datetime.now(timezone.utc) + timedelta(days=30) if remember else None
    
    response.set_cookie(
        key="theme",
        value=theme,
        expires=expires,
        httponly=True,
        samesite="lax",
        secure=False
    )
    
    return response


# 读取主题偏好
@router.get("/preferences/theme", response_model=ThemePreferenceResponse)
async def get_theme_preference(
    theme: Annotated[str | None, Cookie()] = None
) -> ThemePreferenceResponse:
    """
    Get user's theme preference from cookie
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
    Set user's language preference in cookie
    """
    content = {"message": f"Language preference set to {language}"}
    response = JSONResponse(content=content)
    
    # 使用 datetime.now(timezone.utc) 替代 pytz
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
    Get all user preferences from cookies
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
    Simulate a login by setting a session ID cookie
    This is just for demonstration, in real applications you should use proper authentication
    """
    session_id = str(uuid.uuid4())
    
    print("session_id: ", session_id)
    content = {
        "message": "Login successful",
        "user_id": user_id,
        "session_id": session_id
    }
    
    # 使用 datetime.now(timezone.utc) 来创建纯 UTC 时间
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
        secure=False,  # 开发环境设为False，生产环境应该设为True
        max_age=2592000 if remember else 7200,
        domain="localhost",  # 添加domain
        path="/"  # 添加path
    )
    
    return response  # 返回response而不是content


# 登出路由
@router.post("/auth/logout")
async def logout() -> JSONResponse:
    """
    Logout by clearing the session cookie
    """
    response = JSONResponse(content={"message": "Logged out successfully"})
    
    # 通过设置空值和过期时间为0来删除cookie
    response.delete_cookie(
        key="session_id",
        httponly=True,
        samesite="lax",
        secure=False  # 开发环境设为False，生产环境应该设为True
    )
    
    return response


# 检查会话状态
@router.get("/auth/session", response_model=SessionResponse)
async def check_session(
    session_id: Annotated[str | None, Cookie()] = None
) -> SessionResponse:
    """
    Check if user has a valid session
    """
    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    
    # 在实际应用中，你应该在这里验证session_id的有效性
    # 比如检查数据库中是否存在这个session_id，是否过期等
    else:
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
    Upload a file using multipart/form-data
    
    This endpoint demonstrates how to use Form and File together:
    - file: The actual file to upload
    - description: Optional text description
    - tags: Comma separated list of tags
    """
    # 读取文件内容（这里只是为了获取大小）
    contents = await file.read()
    file_size = len(contents)
    
    # 重置文件指针，以便后续可能的操作
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