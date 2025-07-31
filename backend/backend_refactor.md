# FastAPI 后端重构文档

## 概述

本文档详细说明了 FastAPI 后端代码需要进行的重构内容，主要包括：
1. 删除冗余的 toggle 端点，使用标准的 PATCH 方法替代
2. 统一权限检查逻辑，消除代码重复
3. 重新组织依赖项目录结构
4. 优化会话类型定义并添加类型约束
5. 清理CRUD文件中的重复方法，优化数据访问层

## 1. 删除 Toggle 端点相关代码

### 1.1 删除路由端点

**文件**: `backend/app/api/v1/routes/bot_config_routes.py`

**删除以下整个方法**:
```python
@router.post("/{config_id}/toggle", response_model=BotConfigToggleResponse)
async def toggle_bot_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> BotConfigToggleResponse:
    # 删除整个方法实现
```

### 1.2 删除响应模型

**文件**: `backend/app/schemas/bot_config.py`

**删除以下类**:
```python
class BotConfigToggleResponse(BaseModel):
    id: int
    is_active: bool
    message: str
```

### 1.3 删除 CRUD 方法

**文件**: `backend/app/crud/bot_config.py`

**删除以下方法**:
```python
@staticmethod
async def toggle_bot_config_status(
    db: AsyncSession, 
    config_id: int
) -> Optional[BotConfig]:
    # 删除整个方法实现
```

### 1.4 更新导入声明

**文件**: `backend/app/schemas/__init__.py`

**删除导入**:
```python
# 从这一行删除 BotConfigToggleResponse
from .bot_config import (
    BotConfigBase, BotConfigCreate, BotConfigUpdate, BotConfigResponse, BotConfigToggleResponse  # 删除这个
)

# 从 __all__ 列表中删除
__all__ = [
    # ...
    "BotConfigToggleResponse",  # 删除这一行
    # ...
]
```

## 2. 统一权限检查逻辑

### 2.1 重写权限工具文件

**文件**: `backend/app/utils/permissions.py`

**完全替换文件内容**:
```python
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.bot_config import BotConfig
from app.models.scrape_session import ScrapeSession
from app.crud.bot_config import CRUDBotConfig
from app.crud.scrape_session import CRUDScrapeSession


def _check_resource_ownership(owner_user_id: int, current_user: User) -> None:
    """内部方法：检查用户是否拥有资源的访问权限"""
    if owner_user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")


async def get_accessible_bot_config(
    db: AsyncSession,
    config_id: int,
    user: User
) -> BotConfig:
    """获取用户可访问的Bot配置
    
    - 超级用户可以访问所有配置
    - 普通用户只能访问自己的配置
    """
    bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)
    if not bot_config:
        raise HTTPException(status_code=404, detail="Bot配置不存在")
    
    _check_resource_ownership(bot_config.user_id, user)
    return bot_config


async def get_accessible_session(
    db: AsyncSession,
    session_id: int,
    user: User
) -> ScrapeSession:
    """获取用户可访问的爬取会话
    
    - 超级用户可以访问所有会话
    - 普通用户只能访问自己Bot配置关联的会话
    """
    session = await CRUDScrapeSession.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="爬取会话不存在")
    
    # 通过关联的Bot配置检查权限
    bot_config = await CRUDBotConfig.get_bot_config_by_id(db, session.bot_config_id)
    if not bot_config:
        raise HTTPException(status_code=404, detail="关联的Bot配置不存在")
    
    _check_resource_ownership(bot_config.user_id, user)
    return session
```

### 2.2 重构 Bot 配置路由

**文件**: `backend/app/api/v1/routes/bot_config_routes.py`

**添加导入**:
```python
from app.utils.permissions import get_accessible_bot_config
```

**替换以下方法中的权限检查逻辑**:

#### 2.2.1 get_bot_config 方法
**查找并替换**:
```python
# 替换这段代码
bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)

if not bot_config:
    raise HTTPException(status_code=404, detail="Bot配置不存在")

# 权限检查：只能查看自己的配置或超级用户可以查看所有配置
if bot_config.user_id != current_user.id and not current_user.is_superuser:
    raise InsufficientPermissionsError("没有权限查看此配置")

# 替换为
bot_config = await get_accessible_bot_config(db, config_id, current_user)
```

#### 2.2.2 update_bot_config 方法
**查找并替换**:
```python
# 替换这段代码
# 先获取配置检查权限
bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)

if not bot_config:
    raise HTTPException(status_code=404, detail="Bot配置不存在")

# 权限检查
if bot_config.user_id != current_user.id and not current_user.is_superuser:
    raise InsufficientPermissionsError("没有权限修改此配置")

# 替换为
await get_accessible_bot_config(db, config_id, current_user)
```

#### 2.2.3 delete_bot_config 方法
**查找并替换**:
```python
# 替换这段代码
# 先获取配置检查权限
bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)

if not bot_config:
    raise HTTPException(status_code=404, detail="Bot配置不存在")

# 权限检查
if bot_config.user_id != current_user.id and not current_user.is_superuser:
    raise InsufficientPermissionsError("没有权限删除此配置")

# 替换为
await get_accessible_bot_config(db, config_id, current_user)
```

### 2.3 重构爬取路由

**文件**: `backend/app/api/v1/routes/scraping_routes.py`

**添加导入**:
```python
from app.utils.permissions import get_accessible_bot_config, get_accessible_session
```

**删除导入**:
```python
from app.utils.permissions import check_bot_config_permission  # 删除此行
```

#### 2.3.1 batch_trigger_scraping 方法
**查找并替换**:
```python
# 在 for config_id in config_ids: 循环中
# 替换这行
bot_config = await check_bot_config_permission(db, config_id, current_user)

# 替换为
bot_config = await get_accessible_bot_config(db, config_id, current_user)
```

#### 2.3.2 get_scrape_session 方法
**查找并替换**:
```python
# 替换这段代码
session = await CRUDScrapeSession.get_session_by_id(db, session_id)

if not session:
    raise HTTPException(status_code=404, detail="爬取会话不存在")

# 通过关联的bot配置检查权限
await check_bot_config_permission(db, session.bot_config_id, current_user)

# 替换为
session = await get_accessible_session(db, session_id, current_user)
```

### 2.4 重构 Reddit 内容路由

**文件**: `backend/app/api/v1/routes/reddit_content_routes.py`

**添加导入**:
```python
from app.utils.permissions import get_accessible_session
```

#### 2.4.1 get_session_posts 方法
**查找并替换**:
```python
# 替换这段代码
# 检查会话权限
session = await CRUDScrapeSession.get_session_by_id(db, session_id)

if not session:
    raise HTTPException(status_code=404, detail="爬取会话不存在")

# 获取关联的bot配置检查权限
bot_config = await CRUDBotConfig.get_bot_config_by_id(db, session.bot_config_id)

if not bot_config:
    raise HTTPException(status_code=404, detail="关联的Bot配置不存在")

# 权限检查
if bot_config.user_id != current_user.id and not current_user.is_superuser:
    raise InsufficientPermissionsError("没有权限查看此会话数据")

# 替换为
await get_accessible_session(db, session_id, current_user)
```

#### 2.4.2 get_session_comments 方法
**应用与 get_session_posts 相同的替换**

#### 2.4.3 get_post_comments 方法
**查找并替换**:
```python
# 在权限检查部分
# 替换这段代码
if session:
    bot_config = await CRUDBotConfig.get_bot_config_by_id(db, session.bot_config_id)
    
    if bot_config and bot_config.user_id != current_user.id and not current_user.is_superuser:
        raise InsufficientPermissionsError("没有权限查看此帖子数据")

# 替换为
if session:
    try:
        await get_accessible_session(db, first_comment.scrape_session_id, current_user)
    except HTTPException:
        raise InsufficientPermissionsError("没有权限查看此帖子数据")
```

## 3. 重新组织依赖项目录结构

### 3.1 创建新的目录结构

**创建目录和文件**:
```bash
mkdir backend/app/dependencies
touch backend/app/dependencies/__init__.py
```

### 3.2 移动文件

**移动依赖项文件**:
```bash
mv backend/app/api/v1/dependencies/current_user.py backend/app/dependencies/
mv backend/app/api/v1/dependencies/request_context.py backend/app/dependencies/
```

### 3.3 更新新的依赖项模块

**文件**: `backend/app/dependencies/__init__.py`

**添加内容**:
```python
from .current_user import (
    get_current_user_from_request,
    get_current_active_user,
    get_optional_current_user,
    get_current_superuser
)
from .request_context import request_context_dependency

__all__ = [
    "get_current_user_from_request",
    "get_current_active_user", 
    "get_optional_current_user",
    "get_current_superuser",
    "request_context_dependency"
]
```

### 3.4 更新所有依赖项导入

**需要修改的文件**:
- `backend/app/main.py`
- `backend/app/api/v1/routes/auth_routes.py`
- `backend/app/api/v1/routes/bot_config_routes.py`
- `backend/app/api/v1/routes/reddit_content_routes.py`
- `backend/app/api/v1/routes/scraping_routes.py`
- `backend/app/api/v1/routes/user_routes.py`

**在所有这些文件中，查找并替换**:
```python
# 查找这些导入
from app.api.v1.dependencies.current_user import get_current_active_user
from app.api.v1.dependencies.current_user import get_current_superuser
from app.api.v1.dependencies.current_user import get_current_user_from_request
from app.api.v1.dependencies.current_user import get_optional_current_user
from app.api.v1.dependencies.request_context import request_context_dependency

# 替换为
from app.dependencies.current_user import get_current_active_user
from app.dependencies.current_user import get_current_superuser
from app.dependencies.current_user import get_current_user_from_request
from app.dependencies.current_user import get_optional_current_user
from app.dependencies.request_context import request_context_dependency
```

### 3.5 删除旧的目录结构

**删除空目录**:
```bash
# 检查 backend/app/api/v1/dependencies/ 目录是否为空
# 如果只剩下 __init__.py 文件，可以删除整个目录
rm -rf backend/app/api/v1/dependencies/
```

## 4. 优化会话类型定义并添加类型约束

### 4.1 更新会话模型

**文件**: `backend/app/models/scrape_session.py`

**添加导入**:
```python
from sqlalchemy import String, DateTime, func, Integer, Text, ForeignKey, Enum
from enum import Enum as PyEnum
```

**添加枚举类定义**:
```python
class SessionType(str, PyEnum):
    """会话类型枚举"""
    MANUAL = "manual"  # 手动触发
    AUTO = "auto"      # 定时任务自动触发
```

**修改 ScrapeSession 类**:
```python
# 查找这一行
session_type: Mapped[str] = mapped_column(String(20), default='manual')  # manual, scheduled, auto

# 替换为
session_type: Mapped[SessionType] = mapped_column(Enum(SessionType), default=SessionType.MANUAL)
```

### 4.2 更新相关的 Schema 文件

**文件**: `backend/app/schemas/scrape_session.py`

**添加导入**:
```python
from app.models.scrape_session import SessionType
```

**更新 Schema 类**:
```python
# 查找
class ScrapeSessionBase(BaseModel):
    session_type: str = Field("manual", description="会话类型")

# 替换为
class ScrapeSessionBase(BaseModel):
    session_type: SessionType = Field(SessionType.MANUAL, description="会话类型")
```

### 4.3 更新服务层代码

**文件**: `backend/app/services/scraping_orchestrator.py`

**添加导入**:
```python
from app.models.scrape_session import ScrapeSession, SessionType
```

**更新方法签名和调用**:
```python
# 查找
async def execute_scraping_session(
    self,
    db: AsyncSession,
    bot_config_id: int,
    session_type: str = 'manual'
) -> Optional[Dict[str, Any]]:

# 替换为
async def execute_scraping_session(
    self,
    db: AsyncSession,
    bot_config_id: int,
    session_type: SessionType = SessionType.MANUAL
) -> Optional[Dict[str, Any]]:

# 查找
async def execute_multiple_configs(
    self,
    db: AsyncSession,
    config_ids: List[int],
    session_type: str = 'batch'
) -> List[Dict[str, Any]]:

# 替换为
async def execute_multiple_configs(
    self,
    db: AsyncSession,
    config_ids: List[int],
    session_type: SessionType = SessionType.MANUAL
) -> List[Dict[str, Any]]:

# 查找
return await self.execute_multiple_configs(db, config_ids, 'auto')

# 替换为
return await self.execute_multiple_configs(db, config_ids, SessionType.AUTO)
```

### 4.4 更新路由层代码

**文件**: `backend/app/api/v1/routes/scraping_routes.py`

**添加导入**:
```python
from app.models.scrape_session import SessionType
```

**更新方法中的类型使用**:
```python
# 在 batch_trigger_scraping 方法中
# 查找
session_type = request_data.session_type

# 确保使用正确的枚举类型，如果需要转换：
session_type = SessionType(request_data.session_type) if isinstance(request_data.session_type, str) else request_data.session_type
```

### 4.5 为会话状态添加类型约束

**文件**: `backend/app/models/scrape_session.py`

**添加状态枚举类定义**:
```python
class SessionStatus(str, PyEnum):
    """会话状态枚举"""
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 执行成功
    FAILED = "failed"        # 执行失败
```

**修改 ScrapeSession 类**:
```python
# 查找这一行
status: Mapped[str] = mapped_column(String(20), default='pending')  # pending, running, completed, failed

# 替换为
status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.PENDING)
```

### 4.6 更新相关 Schema 文件

**文件**: `backend/app/schemas/scrape_session.py`

**添加导入**:
```python
from app.models.scrape_session import SessionType, SessionStatus
```

**更新 Schema 类**:
```python
# 查找
class ScrapeSessionBase(BaseModel):
    session_type: SessionType = Field(SessionType.MANUAL, description="会话类型")
    status: str = Field("pending", description="会话状态")

# 替换为
class ScrapeSessionBase(BaseModel):
    session_type: SessionType = Field(SessionType.MANUAL, description="会话类型")
    status: SessionStatus = Field(SessionStatus.PENDING, description="会话状态")
```

### 4.7 更新 CRUD 层代码

**文件**: `backend/app/crud/scrape_session.py`

**添加导入**:
```python
from app.models.scrape_session import ScrapeSession, SessionStatus
```

**更新方法中的状态使用**:
```python
# 查找
async def create_scrape_session(...):
    session = ScrapeSession(
        # ...
        status='pending',
        # ...
    )

# 替换为
async def create_scrape_session(...):
    session = ScrapeSession(
        # ...
        status=SessionStatus.PENDING,
        # ...
    )

# 查找
async def start_session(...):
    session.status = 'running'

# 替换为
async def start_session(...):
    session.status = SessionStatus.RUNNING

# 查找
async def complete_session(...):
    session.status = 'failed' if error_message else 'completed'

# 替换为
async def complete_session(...):
    session.status = SessionStatus.FAILED if error_message else SessionStatus.COMPLETED
```

### 4.8 更新路由层代码

**文件**: `backend/app/api/v1/routes/scraping_routes.py`

**添加导入**:
```python
from app.models.scrape_session import SessionType, SessionStatus
```

**更新查询参数类型**:
```python
# 查找
async def get_scrape_sessions(
    # ...
    status: str = None,
    # ...
):

# 替换为
async def get_scrape_sessions(
    # ...
    status: SessionStatus = None,
    # ...
):
```

### 完整的枚举定义

**文件**: `backend/app/models/scrape_session.py`

**最终的枚举类定义**:
```python
from sqlalchemy import String, DateTime, func, Integer, Text, ForeignKey, Enum
from enum import Enum as PyEnum

class SessionType(str, PyEnum):
    """会话类型枚举"""
    MANUAL = "manual"  # 手动触发
    AUTO = "auto"      # 定时任务自动触发

class SessionStatus(str, PyEnum):
    """会话状态枚举"""
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 执行成功
    FAILED = "failed"        # 执行失败

# 在 ScrapeSession 类中使用
class ScrapeSession(Base):
    # ...
    session_type: Mapped[SessionType] = mapped_column(Enum(SessionType), default=SessionType.MANUAL)
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.PENDING)
    # ...
```

## 5. 清理CRUD文件中的重复方法

### 5.1 删除重复的查询方法

**文件**: `backend/app/crud/scrape_session.py`

**删除以下整个方法**:
```python
@staticmethod
async def get_sessions_by_user(
    db: AsyncSession,
    user_id: int,
    limit: int = 50,
    status: Optional[str] = None,
    session_type: Optional[str] = None
) -> List[ScrapeSession]:
    """获取指定用户的所有爬取会话列表（兼容方法）"""
    return await CRUDScrapeSession.get_sessions(
        db, user_id=user_id, limit=limit,
        status=status, session_type=session_type
    )
```

**理由**: 这个方法只是 `get_sessions` 方法的简单包装，没有任何额外功能。

### 5.2 更新路由文件中的方法调用

由于删除了 `get_sessions_by_user` 方法，需要检查并更新所有使用该方法的地方。

**检查以下文件是否有调用**:
- `backend/app/api/v1/routes/scraping_routes.py`
- `backend/app/services/scraping_orchestrator.py`

**如果发现调用，请替换**:
```python
# 原来的调用
sessions = await CRUDScrapeSession.get_sessions_by_user(
    db, user_id, limit, status, session_type
)

# 替换为
sessions = await CRUDScrapeSession.get_sessions(
    db, user_id=user_id, limit=limit, status=status, session_type=session_type
)
```

## 6. 验证修改

重构完成后，请确保：

1. **编译检查**: 确保所有导入都正确，没有未定义的引用
2. **功能等价性**: 
   - PATCH 方法可以实现原 toggle 功能
   - `get_sessions` 方法可以完全替代 `get_sessions_by_user`
3. **权限一致性**: 所有权限检查都使用统一的逻辑
4. **错误处理**: HTTP 状态码和错误消息保持一致
5. **依赖项正常**: 移动后的依赖项在所有路由中正常工作
6. **类型约束**: 会话类型只能是 MANUAL 或 AUTO
7. **数据库兼容性**: 确保数据库迁移正确执行
8. **CRUD方法调用**: 检查所有路由和服务文件中是否还有对已删除方法的调用

## 7. 重构检查清单

### 7.1 删除的文件和方法
- [ ] `BotConfigToggleResponse` 类已删除
- [ ] `toggle_bot_config` 路由端点已删除
- [ ] `toggle_bot_config_status` CRUD方法已删除
- [ ] `get_sessions_by_user` CRUD方法已删除
- [ ] 相关导入声明已更新

### 7.2 替换的方法调用
- [ ] Bot配置路由中的权限检查已统一
- [ ] 爬取路由中的权限检查已统一
- [ ] Reddit内容路由中的权限检查已统一
- [ ] 所有 `get_sessions_by_user` 调用已替换为 `get_sessions`

### 7.3 新增的统一方法
- [ ] `get_accessible_bot_config` 方法已实现
- [ ] `get_accessible_session` 方法已实现
- [ ] 权限工具文件已重写

### 7.4 目录结构重组
- [ ] 依赖项文件已移动到 `backend/app/dependencies/`
- [ ] 所有导入路径已更新
- [ ] 旧的依赖项目录已清理

### 7.5 类型约束和枚举
- [ ] `SessionType` 枚举已定义和应用
- [ ] `SessionStatus` 枚举已定义和应用
- [ ] 相关Schema已更新
- [ ] 数据库迁移已执行

### 7.6 CRUD层重构
- [ ] 重复的CRUD方法已删除
- [ ] 所有CRUD调用已验证

## 8. 预期效果

重构后的代码将具有：
- ✅ **消除代码重复**: 
  - 6-7 处重复的权限检查逻辑合并为 2 个统一方法
  - 删除了 1 个完全重复的CRUD方法
  - 可选的基类重构进一步减少通用方法重复
- ✅ **RESTful 合规**: 使用标准的 PATCH 方法而不是自定义 toggle 端点
- ✅ **统一错误处理**: 一致的 HTTP 状态码和错误消息
- ✅ **清晰的目录结构**: 通用依赖项和版本特定依赖项分离
- ✅ **类型安全**: 会话类型和状态使用枚举约束，避免无效值
- ✅ **语义清晰**: 删除冲突的会话类型，保持概念一致
- ✅ **易于维护**: 
  - 权限逻辑修改只需要改一个地方
  - CRUD逻辑更加清晰，避免方法名混淆
  - 依赖项管理更加集中和统一
- ✅ **代码简化**: 每个权限检查从 4-5 行代码简化为 1 行