下面是一份重构指南，请按照这份指南对我目前backend/app 中的代码进行部分修改

-----

## **项目架构重构文档**

### **1. 概述**

本文档旨在指导后续的专项重构工作，以全面对齐项目设定的新架构目标：**模块化、职责分离、高内聚低耦合**。本次重构将聚焦于两个关键点：

1.  **基础设施层整合**：将遗留的 `redis_manager.py` 彻底分解，并将其功能融入到全新的 `infrastructure` 层中，实现基础设施与核心业务的完全解耦。
2.  **业务逻辑层构建**：为 `auth` 和 `tasks` 核心业务模块创建独立的 Service 层，将业务逻辑从 API Endpoints 中剥离，使架构层次更清晰。

完成这些步骤后，项目将完全遵循 **API 层 → 业务逻辑层 → 数据/基础设施层** 的单向依赖原则，显著提升代码的可维护性、可测试性和可扩展性。

### **2. 第一步：拆分 `redis_manager.py` 并融入 `infrastructure`**

#### **2.1. 目标**

  - **移除**位于 `core` 目录下的 `redis_manager.py`，因为它属于基础设施的范畴，不应存在于核心配置目录中。
  - **消除**其作为“大一统”管理器的反模式，将其功能分解到 `infrastructure` 目录中对应的独立服务里。
  - **统一**应用获取 Redis 连接的方式，全部通过 `infrastructure/database/` 提供的依赖注入函数。

#### **2.2. 行动计划**

**阶段一：统一 Redis 连接池管理**

1.  **确认职责**：检查并确保 `infrastructure/database/redis_pool.py` 是项目中**唯一**负责创建和管理 Redis 连接池 (`ConnectionPool`) 的地方。
2.  **提供连接依赖**：确认 `infrastructure/database/redis_base.py` 提供了一个 FastAPI 依赖项函数，如 `get_redis_connection()`，用于向应用的其他部分提供 Redis 连接实例。
3.  **迁移配置**：确保所有 Redis 相关的配置（主机、端口、数据库等）都通过 `core/config.py` 进行加载，并由 `redis_pool.py` 使用。

**阶段二：重构依赖 `redis_manager` 的服务**

逐一排查项目中所有导入并使用 `redis_manager` 的地方，并按以下模式进行重构。主要涉及缓存、调度器等功能。

以 **`CacheService`** 为例：

**重构前 (`infrastructure/cache/cache_service.py`)**

```python
# 旧模式：依赖于全局的 redis_manager
from app.core.redis_manager import redis_manager

class CacheService:
    def get(self, key: str):
        # 直接使用 redis_manager 的一个特定客户端
        return redis_manager.cache.get(key)
```

**重构后 (`infrastructure/cache/cache_service.py`)**

```python
# 新模式：通过构造函数或方法接收一个 Redis 连接实例
from redis.asyncio import Redis

class CacheService:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def get(self, key: str):
        return await self.redis.get(key)

# 在依赖注入时，动态创建 CacheService 实例
from app.infrastructure.database.redis_base import get_redis_connection

def get_cache_service(redis: Redis = Depends(get_redis_connection)) -> CacheService:
    return CacheService(redis_client=redis)
```

**阶段三：删除遗留文件**

1.  在完成所有依赖点的重构后，确认项目中不再有任何代码导入 `core/redis_manager.py`。
2.  **安全删除** `backend/app/core/redis_manager.py` 文件。

-----

### **3. 第二步：为 `auth` 和 `tasks` 模块创建 `service.py`**

#### **3.1. 目标**

  - 将 **业务逻辑** 从 API Endpoints (路由函数) 中完全抽离。
  - 使 API Endpoints 变得“薄”，只负责**请求校验、调用服务、响应格式化**等 HTTP 相关工作。
  - 封装业务流程，使其可被复用和独立测试。

#### **3.2. `auth` 模块 Service 层构建**

1.  **创建文件**: 在 `backend/app/modules/auth/` 目录下创建 `service.py`。
2.  **迁移业务逻辑**: 将 `api/v1/endpoints/auth.py` 和 `api/v1/endpoints/users.py` 中的核心业务逻辑迁移至新建的 `AuthService` 类中。

**迁移示例：用户注册**

**重构前 (`api/v1/endpoints/auth.py`)**

```python
from app.modules.auth import repository as auth_repo
from app.core import exceptions

@router.post("/register")
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    # 业务逻辑直接写在 Endpoint 中
    existing_user = auth_repo.user.get_by_email(db, email=user_in.email)
    if existing_user:
        raise exceptions.EmailAlreadyExistsError()
    user = auth_repo.user.create(db, obj_in=user_in)
    # email_service.send_verification_email(...)
    return user
```

**重构后 (`modules/auth/service.py`)**

```python
from sqlalchemy.orm import Session
from app.modules.auth import models, schemas, repository
from app.infrastructure.external import email_service
from app.infrastructure.auth import auth_service as infra_auth_service # JWT 服务
from app.core import exceptions

class AuthService:
    def register_user(self, db: Session, user_in: schemas.UserCreate):
        existing_user = repository.user.get_by_email(db, email=user_in.email)
        if existing_user:
            raise exceptions.EmailAlreadyExistsError()
        user = repository.user.create(db, obj_in=user_in)
        # email_service.send_verification_email(...)
        return user
    
    # ... login, update_profile, reset_password 等其他业务方法

auth_service = AuthService()
```

**重构后 (`api/v1/endpoints/auth.py`)**

```python
from app.modules.auth.service import auth_service

@router.post("/register")
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    # Endpoint 变得非常简洁，只调用 service
    return auth_service.register_user(db=db, user_in=user_in)
```

**需要迁移的逻辑清单**:

  - `auth.py`: 注册、登录、请求密码重置、执行密码重置。
  - `users.py`: 获取/更新当前用户信息、更新当前用户密码、根据ID获取用户。

#### **3.3. `tasks` 模块 Service 层构建**

1.  **创建文件**: 在 `backend/app/modules/tasks/` 目录下创建 `service.py`。
2.  **迁移业务逻辑**: 将 `api/v1/endpoints/tasks.py` 中的业务逻辑和数据编排工作迁移至 `TaskService` 类。

**迁移示例：获取系统健康状态**

**重构前 (`api/v1/endpoints/tasks.py`)**

```python
from app.infrastructure.scheduler import status as scheduler_status

@router.get("/system-health")
def get_system_health():
    # 编排逻辑在 Endpoint 中
    broker_status = scheduler_status.get_broker_status()
    workers_status = scheduler_status.get_workers_status()
    # ... 可能还有其他数据组合 ...
    return {"broker": broker_status, "workers": workers_status}
```

**重构后 (`modules/tasks/service.py`)**

```python
from sqlalchemy.orm import Session
from app.modules.tasks import repository
from app.infrastructure.scheduler import status as scheduler_status

class TaskService:
    def get_system_health_status(self):
        broker_status = scheduler_status.get_broker_status()
        workers_status = scheduler_status.get_workers_status()
        return {"broker": broker_status, "workers": workers_status}
    
    def get_all_task_configs(self, db: Session):
        return repository.task_config.get_multi(db)

    # ... 其他业务方法

task_service = TaskService()
```

**重构后 (`api/v1/endpoints/tasks.py`)**

```python
from app.modules.tasks.service import task_service

@router.get("/system-health")
def get_system_health():
    # 只负责调用 service
    return task_service.get_system_health_status()
```

**需要迁移的逻辑清单**:

  - 获取所有任务配置。
  - 创建/更新任务配置。
  - 获取系统健康状态、计划任务列表、任务执行历史。
  - 手动触发任务。
