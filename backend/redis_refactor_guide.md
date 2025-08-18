根据你的代码架构和要求，我来修改重构文档中的ScheduleRedisService部分，使用RedisScheduleSource实现真正的调度器功能。

# Redis 重构指南：构建高性能后端应用（修正版）

**你好！**
本次任务是根据您现有的后端架构，对Redis使用进行优化重构。基于您的代码分析，我发现您已经有良好的TaskIQ+Redis基础架构，因此重构将更专注于业务层面的优化。

**核心目标:**
1. **移除技术债务**：废弃不再需要的 `schedule_events` 和 `refresh_tokens` 数据库表。
2. **提升性能**：将Token验证、用户缓存、调度记录等高频操作从 PostgreSQL 迁移到 Redis。
3. **统一架构**：基于现有Redis连接，建立统一的Redis服务层。

-----

## 1. 当前架构分析

**需要重构的问题：**
- `refresh_tokens` 表：每次Token验证都查询数据库
- `schedule_events` 表：被TaskIQ调度机制取代但仍在使用
- 用户信息缓存缺失：N+1查询问题
- Redis功能分散：缺乏统一的业务服务层

-----

## 2. 重构方案（基于现有架构）

我们将在您现有的Redis基础上，添加业务服务层，而不是重新构建基础设施。

**设计原则：**
- Redis 服务基类: 负责管理单例的 Redis 连接池，提供基础的客户端实例，并可封装通用的错误处理逻辑。
- 具体服务 (AuthService, CacheService等): 继承自基类，封装特定业务领域的 Redis 操作，提供清晰的接口供应用层调用。
- 调度器服务: 基于现有的RedisScheduleSource，提供真正的分布式调度能力。
- Redis 服务管理器: 作为依赖注入的入口，统一管理所有 Redis 服务的生命周期和实例化。
- 确保所有的核心功能都已迁移到新的Redis服务架构上后:
	删除 schedule_events 相关文件: 移除与旧的调度历史表相关的所有模型、CRUD和Schema文件。
	删除旧的 token 相关文件: 移除与旧的数据库Token表相关的所有模型和CRUD文件。
	删除旧的 redis_timeout_store.py: 移除旧的、分散的超时监控实现。

-----

## 3. 实施步骤

### 第 1 步：创建简化的Redis服务基类

**3.1. 创建Redis服务基类**
```python
# backend/app/core/redis_core.py
import redis.asyncio as redis
import json
from typing import Any, Dict, Optional
from app.core.config import settings

class RedisBase:
    """Redis服务基类，复用现有配置"""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
    
    async def get_client(self) -> redis.Redis:
        """获取Redis客户端，复用现有配置"""
        if not self._client:
            self._client = redis.from_url(
                settings.redis.CONNECTION_URL,
                decode_responses=True,
                max_connections=10
            )
        return self._client
    
    async def close(self):
        """关闭Redis连接"""
        if self._client:
            await self._client.close()
            self._client = None
    
    async def set_json(self, key: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """存储JSON数据"""
        client = await self.get_client()
        try:
            result = await client.set(key, json.dumps(data), ex=ttl)
            return result is True
        except Exception:
            return False
    
    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """获取JSON数据"""
        client = await self.get_client()
        try:
            data = await client.get(key)
            return json.loads(data) if data else None
        except Exception:
            return None
    
    async def delete(self, key: str) -> bool:
        """删除键"""
        client = await self.get_client()
        try:
            result = await client.delete(key)
            return result > 0
        except Exception:
            return False
```

### 第 2 步：创建业务Redis服务

**3.2. 认证Redis服务**
```python
# backend/app/services/auth_redis.py
from typing import Optional, Set
from datetime import datetime, timedelta
from app.core.redis_core import RedisBase
from app.core.config import settings
import json

class AuthRedisService(RedisBase):
    """认证相关的Redis服务"""
    
    def __init__(self):
        super().__init__()
        self.token_prefix = "auth:token:"
        self.user_tokens_prefix = "auth:user_tokens:"
    
    async def store_refresh_token(
        self,
        token: str,
        user_id: int,
        expires_in_days: int = None
    ) -> bool:
        """存储刷新令牌"""
        if expires_in_days is None:
            expires_in_days = settings.security.REFRESH_TOKEN_EXPIRE_DAYS
        
        ttl = expires_in_days * 24 * 3600  # 转换为秒
        
        token_data = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=expires_in_days)).isoformat()
        }
        
        client = await self.get_client()
        
        # 使用pipeline提高性能
        pipe = client.pipeline()
        # 存储token数据
        pipe.set(f"{self.token_prefix}{token}", json.dumps(token_data), ex=ttl)
        # 添加到用户token集合
        pipe.sadd(f"{self.user_tokens_prefix}{user_id}", token)
        pipe.expire(f"{self.user_tokens_prefix}{user_id}", ttl)
        
        try:
            await pipe.execute()
            return True
        except Exception:
            return False
    
    async def get_refresh_token_payload(self, token: str) -> Optional[dict]:
        """获取刷新令牌数据"""
        return await self.get_json(f"{self.token_prefix}{token}")
    
    async def revoke_token(self, token: str) -> bool:
        """撤销令牌"""
        client = await self.get_client()
        
        # 先获取token数据以便从用户集合中移除
        token_data = await self.get_refresh_token_payload(token)
        if not token_data:
            return False
        
        user_id = token_data.get("user_id")
        
        pipe = client.pipeline()
        pipe.delete(f"{self.token_prefix}{token}")
        if user_id:
            pipe.srem(f"{self.user_tokens_prefix}{user_id}", token)
        
        try:
            await pipe.execute()
            return True
        except Exception:
            return False
    
    async def revoke_all_user_tokens(self, user_id: int) -> bool:
        """撤销用户的所有令牌"""
        client = await self.get_client()
        
        # 获取用户所有token
        try:
            tokens = await client.smembers(f"{self.user_tokens_prefix}{user_id}")
            if not tokens:
                return True
            
            pipe = client.pipeline()
            # 删除所有token
            for token in tokens:
                pipe.delete(f"{self.token_prefix}{token}")
            # 删除用户token集合
            pipe.delete(f"{self.user_tokens_prefix}{user_id}")
            
            await pipe.execute()
            return True
        except Exception:
            return False
```

**3.3. 用户缓存Redis服务**
```python
# backend/app/services/cache_redis.py
from typing import Optional, Dict, Any
from app.core.redis_core import RedisBase

class CacheRedisService(RedisBase):
    """用户缓存Redis服务"""
    
    def __init__(self):
        super().__init__()
        self.user_prefix = "cache:user:"
        self.default_ttl = 300  # 5分钟
    
    async def get_user_cache(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户缓存"""
        return await self.get_json(f"{self.user_prefix}{user_id}")
    
    async def set_user_cache(self, user_id: int, user_data: Dict[str, Any]) -> bool:
        """设置用户缓存"""
        return await self.set_json(
            f"{self.user_prefix}{user_id}",
            user_data,
            ttl=self.default_ttl
        )
    
    async def invalidate_user_cache(self, user_id: int) -> bool:
        """清除用户缓存"""
        return await self.delete(f"{self.user_prefix}{user_id}")
```

**3.4. 调度历史记录Redis服务（辅助服务）**
```python
# backend/app/services/schedule_history_redis.py
from typing import List, Dict, Any, Optional
import json
from app.core.redis_core import RedisBase

class ScheduleHistoryRedisService(RedisBase):
    """调度历史记录服务 - 记录任务执行历史和状态"""
    
    def __init__(self):
        super().__init__()
        self.history_prefix = "schedule:history:"
        self.status_prefix = "schedule:status:"
        self.max_history = 100  # 保留最近100条记录
    
    async def add_history_event(
        self,
        config_id: int,
        event_data: Dict[str, Any]
    ) -> bool:
        """添加调度历史事件"""
        client = await self.get_client()
        
        try:
            pipe = client.pipeline()
            # 添加到历史列表头部
            pipe.lpush(f"{self.history_prefix}{config_id}", json.dumps(event_data))
            # 保持列表长度
            pipe.ltrim(f"{self.history_prefix}{config_id}", 0, self.max_history - 1)
            await pipe.execute()
            return True
        except Exception:
            return False
    
    async def get_history(self, config_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取调度历史"""
        client = await self.get_client()
        
        try:
            history_data = await client.lrange(f"{self.history_prefix}{config_id}", 0, limit - 1)
            return [json.loads(item) for item in history_data]
        except Exception:
            return []
    
    async def update_status(self, config_id: int, status: str) -> bool:
        """更新调度状态"""
        client = await self.get_client()
        
        try:
            await client.set(f"{self.status_prefix}{config_id}", status, ex=3600)  # 1小时过期
            return True
        except Exception:
            return False
```

**3.5. Redis调度器服务（真正的调度器）**
```python
# backend/app/services/scheduler_redis.py
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from taskiq import ScheduledTask
from taskiq_redis import RedisScheduleSource

from app.core.config import settings
from app.models.task_config import TaskConfig
from app.constant.task_registry import TaskType, ConfigStatus, SchedulerType, TaskRegistry

logger = logging.getLogger(__name__)


class SchedulerRedisService:
    """基于RedisScheduleSource的分布式调度器服务"""
    
    def __init__(self):
        # 使用RedisScheduleSource作为调度源
        self.schedule_source = RedisScheduleSource(url=settings.redis.CONNECTION_URL)
        self._initialized = False
    
    async def initialize(self):
        """初始化调度器"""
        if self._initialized:
            return
        
        try:
            await self.schedule_source.startup()
            self._initialized = True
            logger.info("Redis调度源初始化成功")
        except Exception as e:
            logger.error(f"Redis调度源初始化失败: {e}")
            raise
    
    async def shutdown(self):
        """关闭调度器"""
        try:
            await self.schedule_source.shutdown()
            self._initialized = False
            logger.info("Redis调度源已关闭")
        except Exception as e:
            logger.error(f"Redis调度源关闭失败: {e}")
    
    async def register_task(self, config: TaskConfig) -> bool:
        """注册调度任务到Redis"""
        try:
            from app.constant.task_registry import get_task_function
            
            # 获取任务函数
            task_func = get_task_function(config.task_type)
            if not task_func:
                logger.error(f"找不到任务类型 {config.task_type} 对应的任务函数")
                return False
            
            # 准备任务参数
            args = [config.id]
            kwargs = config.parameters or {}
            
            # 生成唯一的任务ID
            task_id = f"{TaskRegistry.SCHEDULED_TASK_PREFIX}{config.id}"
            
            # 创建调度任务参数
            task_params = {
                "schedule_id": task_id,
                "task_name": task_func.task_name,
                "args": args,
                "kwargs": kwargs,
                "labels": {
                    "config_id": str(config.id),
                    "task_type": config.task_type.value,
                    "scheduler_type": config.scheduler_type.value,
                }
            }
            
            # 根据调度类型添加调度参数
            schedule_params = self._get_schedule_params(config.scheduler_type, config.schedule_config)
            if not schedule_params:
                logger.error(f"无法创建调度参数: {config.scheduler_type} - {config.schedule_config}")
                return False
            
            task_params.update(schedule_params)
            
            # 创建调度任务
            scheduled_task = ScheduledTask(**task_params)
            
            # 添加到Redis调度源
            await self.schedule_source.add_schedule(scheduled_task)
            
            logger.info(f"成功注册调度任务: {config.name} (ID: {config.id})")
            return True
            
        except Exception as e:
            logger.error(f"注册调度任务失败 {config.name}: {e}")
            return False
    
    async def unregister_task(self, config_id: int) -> bool:
        """取消注册调度任务"""
        try:
            task_id = f"{TaskRegistry.SCHEDULED_TASK_PREFIX}{config_id}"
            await self.schedule_source.delete_schedule(task_id)
            logger.info(f"成功取消调度任务: config_id={config_id}")
            return True
        except Exception as e:
            logger.error(f"取消调度任务失败 config_id={config_id}: {e}")
            return False
    
    async def update_task(self, config: TaskConfig) -> bool:
        """更新调度任务"""
        try:
            # 先取消旧的调度
            await self.unregister_task(config.id)
            
            # 如果任务仍然是活跃的，重新注册
            if config.status == ConfigStatus.ACTIVE and config.scheduler_type != SchedulerType.MANUAL:
                return await self.register_task(config)
            
            return True
        except Exception as e:
            logger.error(f"更新调度任务失败 {config.id}: {e}")
            return False
    
    async def get_all_schedules(self) -> List[Dict[str, Any]]:
        """获取所有调度任务"""
        try:
            schedules = await self.schedule_source.get_schedules()
            
            tasks = []
            for schedule in schedules:
                task_info = {
                    "task_id": getattr(schedule, 'schedule_id', 'unknown'),
                    "task_name": schedule.task_name,
                    "schedule": getattr(schedule, 'cron', getattr(schedule, 'time', 'unknown')),
                    "labels": schedule.labels,
                    "next_run": self._get_next_run_time(schedule)
                }
                tasks.append(task_info)
            
            return tasks
        except Exception as e:
            logger.error(f"获取调度任务列表失败: {e}")
            return []
    
    async def pause_task(self, config_id: int) -> bool:
        """暂停调度任务（通过删除调度实现）"""
        return await self.unregister_task(config_id)
    
    async def resume_task(self, config: TaskConfig) -> bool:
        """恢复调度任务（通过重新注册实现）"""
        return await self.register_task(config)
    
    def _get_schedule_params(self, scheduler_type: SchedulerType, schedule_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """根据配置创建TaskIQ调度参数"""
        try:
            if scheduler_type == SchedulerType.CRON:
                # Cron调度
                if "cron_expression" in schedule_config:
                    cron_expression = schedule_config["cron_expression"]
                else:
                    minute = schedule_config.get("minute", "*")
                    hour = schedule_config.get("hour", "*")
                    day = schedule_config.get("day", "*")
                    month = schedule_config.get("month", "*")
                    day_of_week = schedule_config.get("day_of_week", "*")
                    cron_expression = f"{minute} {hour} {day} {month} {day_of_week}"
                
                return {"cron": cron_expression}
                
            elif scheduler_type == SchedulerType.DATE:
                # 一次性调度
                run_date = schedule_config.get("run_date")
                if isinstance(run_date, str):
                    run_date = datetime.fromisoformat(run_date)
                return {"time": run_date}
                
            else:
                logger.warning(f"不支持的调度类型: {scheduler_type}")
                return None
                
        except Exception as e:
            logger.error(f"创建调度参数失败: {e}")
            return None
    
    def _get_next_run_time(self, scheduled_task) -> Optional[str]:
        """获取下次运行时间"""
        try:
            from datetime import timedelta
            if hasattr(scheduled_task, 'cron') and scheduled_task.cron:
                # 简化实现：返回当前时间加1分钟
                next_time = datetime.now() + timedelta(minutes=1)
                return next_time.isoformat()
            elif hasattr(scheduled_task, 'time') and scheduled_task.time:
                return scheduled_task.time.isoformat()
        except:
            pass
        return None
```

**3.6. 超时监控Redis服务**
```python
# backend/app/services/timeout_redis.py
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from app.core.redis_core import RedisBase
from app.utils.common import get_current_time

class TimeoutRedisService(RedisBase):
    """超时监控Redis服务，替换现有的redis_timeout_store"""
    
    def __init__(self):
        super().__init__()
        self.tasks_hash_key = "timeout:tasks"  # 存储任务详细信息
        self.index_key = "timeout:index"       # 按过期时间排序的索引
    
    async def add_task(
        self,
        task_id: str,
        config_id: int,
        timeout_seconds: int,
        started_at: datetime
    ) -> bool:
        """添加任务到超时监控"""
        client = await self.get_client()
        
        try:
            deadline = started_at.timestamp() + timeout_seconds
            
            task_data = {
                "task_id": task_id,
                "config_id": config_id,
                "timeout_seconds": timeout_seconds,
                "started_at": started_at.isoformat(),
                "deadline": deadline
            }
            
            pipe = client.pipeline()
            # 存储任务详细信息到Hash
            pipe.hset(self.tasks_hash_key, task_id, json.dumps(task_data))
            # 添加到过期时间索引（Sorted Set，按deadline排序）
            pipe.zadd(self.index_key, {task_id: deadline})
            
            await pipe.execute()
            return True
        except Exception:
            return False
    
    async def remove_task(self, task_id: str) -> bool:
        """移除任务（任务完成或取消时调用）"""
        client = await self.get_client()
        
        try:
            pipe = client.pipeline()
            pipe.hdel(self.tasks_hash_key, task_id)
            pipe.zrem(self.index_key, task_id)
            await pipe.execute()
            return True
        except Exception:
            return False
    
    async def get_expired_tasks(self) -> List[Dict[str, Any]]:
        """获取所有超时的任务，使用高效的Redis操作"""
        client = await self.get_client()
        
        try:
            current_timestamp = get_current_time().timestamp()
            
            # 使用ZRANGEBYSCORE获取所有deadline小于当前时间的任务ID
            expired_task_ids = await client.zrangebyscore(
                self.index_key,
                min=0,
                max=current_timestamp
            )
            
            if not expired_task_ids:
                return []
            
            # 批量获取任务详细信息
            task_data_list = await client.hmget(self.tasks_hash_key, *expired_task_ids)
            
            expired_tasks = []
            for task_data_str in task_data_list:
                if task_data_str:
                    try:
                        task_data = json.loads(task_data_str)
                        expired_tasks.append(task_data)
                    except json.JSONDecodeError:
                        continue
            
            return expired_tasks
        except Exception:
            return []
    
    async def get_all_tasks(self) -> List[Dict[str, Any]]:
        """获取所有监控中的任务（用于调试和清理）"""
        client = await self.get_client()
        
        try:
            all_task_data = await client.hgetall(self.tasks_hash_key)
            
            tasks = []
            for task_id, task_data_str in all_task_data.items():
                try:
                    task_data = json.loads(task_data_str)
                    tasks.append(task_data)
                except json.JSONDecodeError:
                    continue
            
            return tasks
        except Exception:
            return []
    
    async def cleanup_completed_tasks(self, task_ids: List[str]) -> int:
        """批量清理已完成的任务"""
        if not task_ids:
            return 0
        
        client = await self.get_client()
        
        try:
            pipe = client.pipeline()
            for task_id in task_ids:
                pipe.hdel(self.tasks_hash_key, task_id)
                pipe.zrem(self.index_key, task_id)
            
            results = await pipe.execute()
            
            # 计算实际删除的数量（每个任务两个操作）
            deleted_count = sum(1 for i in range(0, len(results), 2) if results[i])
            return deleted_count
        except Exception:
            return 0
```

### 第 3 步：创建Redis服务管理器

**3.7. Redis服务管理器**
```python
# backend/app/services/redis_manager.py
from app.services.auth_redis import AuthRedisService
from app.services.cache_redis import CacheRedisService
from app.services.schedule_history_redis import ScheduleHistoryRedisService
from app.services.scheduler_redis import SchedulerRedisService
from app.services.timeout_redis import TimeoutRedisService

class RedisServiceManager:
    """Redis服务管理器"""
    
    def __init__(self):
        self.auth = AuthRedisService()
        self.cache = CacheRedisService()
        self.history = ScheduleHistoryRedisService()  # 调度历史记录服务
        self.scheduler = SchedulerRedisService()  # 真正的调度器服务
        self.timeout = TimeoutRedisService()  # 超时监控服务
    
    async def initialize(self):
        """初始化所有服务"""
        # 初始化调度器
        await self.scheduler.initialize()
    
    async def close_all(self):
        """关闭所有Redis连接"""
        await self.auth.close()
        await self.cache.close()
        await self.history.close()
        await self.scheduler.shutdown()
        await self.timeout.close()

# 全局实例
redis_services = RedisServiceManager()
```

### 第 4 步：集成到应用生命周期

**3.8. 修改main.py**
```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import router
from app.core.config import settings
from app.dependencies.request_context import request_context_dependency
from app.middleware.logging import RequestResponseLoggingMiddleware
from app.middleware.auth import AuthMiddleware, DEFAULT_EXCLUDE_PATHS
from app.core.logging import setup_logging
from app.core.exceptions import ApiError, AuthenticationError
from app.utils.common import create_exception_handlers
from app.core.task_manager import task_manager
from app.broker import broker
from app.services.redis_manager import redis_services  # 使用新的Redis服务管理器

# 配置日志系统
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # 启动时
        await broker.startup()
        
        # 初始化Redis服务管理器（包含所有Redis服务）
        await redis_services.initialize()
        logger.info("Redis服务管理器初始化成功")
        
        # 初始化任务管理器
        await task_manager.initialize()
        logger.info("TaskIQ任务管理器启动成功")
        
        # 从数据库加载调度任务到Redis
        from app.db.base import AsyncSessionLocal
        from app.crud.task_config import crud_task_config
        
        async with AsyncSessionLocal() as db:
            # 获取所有需要调度的活跃任务配置
            configs = await crud_task_config.get_scheduled_configs(db)
            
            loaded_count = 0
            failed_count = 0
            
            for config in configs:
                try:
                    # 使用Redis调度器服务注册任务
                    success = await redis_services.scheduler.register_task(config)
                    if success:
                        loaded_count += 1
                        logger.debug(f"成功加载调度任务: {config.name} (ID: {config.id})")
                        
                        # 记录到调度历史
                        await redis_services.history.add_history_event(
                            config_id=config.id,
                            event_data={
                                "event": "task_loaded",
                                "task_name": config.name,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        )
                    else:
                        failed_count += 1
                        logger.warning(f"加载调度任务失败: {config.name} (ID: {config.id})")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"加载任务 {config.name} (ID: {config.id}) 时出错: {e}")
            
            logger.info(f"从数据库加载调度任务完成: 成功 {loaded_count} 个, 失败 {failed_count} 个")
        
        logger.info("应用启动成功")
        
    except Exception as e:
        logger.error(f"启动失败: {e}")
    
    yield
    
    # 关闭时
    try:
        await broker.shutdown()
        await task_manager.shutdown()
        
        # 关闭所有Redis服务
        await redis_services.close_all()
        
        logger.info("应用关闭成功")
    except Exception as e:
        logger.error(f"关闭失败: {e}")


app = FastAPI(
    title="FastAPI Demo",
    description="A demo FastAPI application with restructured routes",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    dependencies=[Depends(request_context_dependency)],
    exception_handlers=create_exception_handlers(),
    lifespan=lifespan  # 添加生命周期管理
)

# 设置中间件（注意顺序很重要）
# 中间件的执行顺序与添加顺序相反

# 1. 请求/响应日志记录中间件 (最后执行，最先完成)
app.add_middleware(
    RequestResponseLoggingMiddleware,
    log_request_body=True,
    log_response_body=True,
    max_body_length=4096,
    exclude_paths=[
        "/docs", 
        "/redoc", 
        "/openapi.json",
        "/static/*"
    ],
    exclude_extensions=[
        ".css", ".js", ".ico", ".png", ".jpg", ".svg", ".woff", ".woff2"
    ]
)

# 2. CORS中间件 (倒数第二执行)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. JWT认证中间件 (倒数第三执行，但实际是第一个处理请求的中间件)
app.add_middleware(
    AuthMiddleware,
    exclude_paths=DEFAULT_EXCLUDE_PATHS,
    exclude_path_regexes=[
        "^/api/v1/public/.*$",
        "^/static/.*$"
    ]
)

# 包含API路由
app.include_router(router, prefix="/api")
```

**3.9. 更新scheduler.py（集成新的Redis调度器）**
```python
# backend/app/scheduler.py
"""
TaskIQ Scheduler 配置
使用Redis服务管理器中的调度器
"""
import logging
from taskiq import TaskiqScheduler

from app.broker import broker
from app.services.redis_manager import redis_services

logger = logging.getLogger(__name__)

# 创建调度器，使用Redis服务管理器中的调度源
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        redis_services.scheduler.schedule_source,
    ],
)

# 导出简化的接口函数
async def register_scheduled_task(config):
    """注册调度任务"""
    return await redis_services.scheduler.register_task(config)

async def unregister_scheduled_task(config_id):
    """取消注册调度任务"""
    return await redis_services.scheduler.unregister_task(config_id)

async def update_scheduled_task(config):
    """更新调度任务"""
    return await redis_services.scheduler.update_task(config)

async def get_scheduled_tasks():
    """获取所有调度任务"""
    return await redis_services.scheduler.get_all_schedules()

async def pause_scheduled_task(config_id):
    """暂停调度任务"""
    return await redis_services.scheduler.pause_task(config_id)

async def resume_scheduled_task(config):
    """恢复调度任务"""
    return await redis_services.scheduler.resume_task(config)

async def initialize_scheduler():
    """初始化调度器"""
    await redis_services.scheduler.initialize()

async def shutdown_scheduler():
    """关闭调度器"""
    await redis_services.scheduler.shutdown()
```

**3.10. 重构超时装饰器**
```python
# backend/app/core/timeout_decorator.py (使用新的Redis服务)
import asyncio
import functools
import logging
from typing import Optional, Callable
from datetime import datetime

from app.db.base import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.task_execution import crud_task_execution
from app.crud.task_config import crud_task_config
from app.models.task_execution import ExecutionStatus
from app.services.redis_manager import redis_services  # 使用新的Redis服务
from app.utils.common import get_current_time

logger = logging.getLogger(__name__)

def with_timeout(func: Callable):
    """
    任务超时装饰器 - 使用新的Redis超时监控服务
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # 获取config_id和task_id
        config_id = kwargs.get('config_id')
        task_id = kwargs.get('task_id')
        
        if not task_id:
            import uuid
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            kwargs['task_id'] = task_id
        
        # 统一创建 db session
        async with AsyncSessionLocal() as db:
            # 获取超时配置
            timeout_seconds = await _get_timeout_seconds(db, config_id)
            
            # 如果没有超时设置，直接执行
            if not timeout_seconds:
                return await func(*args, **kwargs)
            
            # 记录开始时间
            started_at = get_current_time()
            
            # 注册到新的Redis超时监控服务
            if config_id:
                await redis_services.timeout.add_task(
                    task_id=task_id,
                    config_id=config_id,
                    timeout_seconds=timeout_seconds,
                    started_at=started_at
                )
            
            try:
                # 使用asyncio.wait_for实现超时
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
                
                # 任务成功完成，更新状态
                await _update_task_status(
                    db=db,
                    task_id=task_id,
                    status=ExecutionStatus.SUCCESS,
                    started_at=started_at,
                    result={"return_value": result} if result is not None else None
                )
                
                # 记录到调度历史
                await redis_services.history.add_history_event(
                    config_id=config_id,
                    event_data={
                        "task_id": task_id,
                        "status": "success",
                        "started_at": started_at.isoformat(),
                        "completed_at": get_current_time().isoformat(),
                        "result": result
                    }
                )
                
                return result
                
            except asyncio.TimeoutError:
                # 任务超时
                error_msg = f"任务超时 (限制: {timeout_seconds}秒)"
                logger.error(f"任务 {task_id} {error_msg}")
                
                await _update_task_status(
                    db=db,
                    task_id=task_id,
                    status=ExecutionStatus.TIMEOUT,
                    started_at=started_at,
                    error_message=error_msg
                )
                
                # 记录到调度历史
                await redis_services.history.add_history_event(
                    config_id=config_id,
                    event_data={
                        "task_id": task_id,
                        "status": "timeout",
                        "started_at": started_at.isoformat(),
                        "error": error_msg
                    }
                )
                
                raise
                
            except Exception as e:
                # 其他错误
                logger.error(f"任务 {task_id} 执行失败: {e}")
                
                await _update_task_status(
                    db=db,
                    task_id=task_id,
                    status=ExecutionStatus.FAILED,
                    started_at=started_at,
                    error_message=str(e)
                )
                
                # 记录到调度历史
                await redis_services.history.add_history_event(
                    config_id=config_id,
                    event_data={
                        "task_id": task_id,
                        "status": "failed",
                        "started_at": started_at.isoformat(),
                        "error": str(e)
                    }
                )
                
                raise
                
            finally:
                # 从Redis注销任务（使用新的服务）
                await redis_services.timeout.remove_task(task_id)
                
                # 更新调度状态
                if config_id:
                    status = "idle"  # 任务完成后设置为空闲
                    await redis_services.history.update_status(config_id, status)
    
    return wrapper

async def _get_timeout_seconds(db: AsyncSession, config_id: Optional[int]) -> Optional[int]:
    """获取任务超时配置"""
    if not config_id:
        return None
    
    try:
        config = await crud_task_config.get(db, config_id)
        return config.timeout_seconds if config else None
    except Exception as e:
        logger.warning(f"获取超时配置失败: {e}")
        return None

async def _update_task_status(
    db: AsyncSession,
    task_id: str,
    status: ExecutionStatus,
    started_at: datetime,
    result: Optional[dict] = None,
    error_message: Optional[str] = None
):
    """更新任务执行状态"""
    try:
        execution = await crud_task_execution.get_by_task_id(db, task_id)
        if execution:
            completed_at = get_current_time()
            duration = (completed_at - started_at).total_seconds()
            
            await crud_task_execution.update_status(
                db=db,
                execution_id=execution.id,
                status=status,
                completed_at=completed_at,
                duration_seconds=duration,
                result=result,
                error_message=error_message
            )
    except Exception as e:
        logger.error(f"更新任务状态失败: {e}")
```

**3.11. 重构超时监控任务**
```python
# backend/app/tasks/timeout_monitor_task.py (使用新的Redis服务)
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.broker import broker
from app.db.base import AsyncSessionLocal
from app.crud.task_execution import crud_task_execution
from app.crud.task_config import crud_task_config
from app.models.task_execution import ExecutionStatus, TaskExecution
from app.models.task_config import TaskConfig
from app.services.redis_manager import redis_services  # 使用新的Redis服务
from app.utils.common import get_current_time
from sqlalchemy import select

logger = logging.getLogger(__name__)

@broker.task(
    task_name="timeout_monitor",
    queue="monitor",
    retry_on_error=False,  # 监控任务不重试
)
async def timeout_monitor_task(
    config_id: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    超时监控任务 - 使用新的Redis超时监控服务
    """
    logger.info("开始执行超时监控...")
    
    # 使用新的Redis服务获取超时任务
    timeout_tasks = await redis_services.timeout.get_expired_tasks()
    
    if not timeout_tasks:
        logger.debug("没有检测到超时任务")
        return {
            "config_id": config_id,
            "checked_at": get_current_time().isoformat(),
            "timeout_count": 0
        }
    
    logger.warning(f"检测到 {len(timeout_tasks)} 个超时任务")
    
    # 批量获取数据，避免N+1查询
    task_ids = [task["task_id"] for task in timeout_tasks]
    config_ids = list(set(task["config_id"] for task in timeout_tasks))
    
    configs_map = await _batch_get_configs(config_ids)
    executions_map = await _batch_get_executions(task_ids)
    
    # 处理每个超时任务
    processed_count = 0
    processed_task_ids = []
    
    async with AsyncSessionLocal() as db:
        for task_data in timeout_tasks:
            try:
                task_id = task_data["task_id"]
                config_id = task_data["config_id"]
                started_at = datetime.fromisoformat(task_data["started_at"])
                timeout_seconds = task_data["timeout_seconds"]
                
                # 从缓存中获取配置和执行记录
                config = configs_map.get(config_id)
                execution = executions_map.get(task_id)
                
                config_name = config.name if config else f"Config#{config_id}"
                
                # 更新任务状态为超时
                if execution and execution.status == ExecutionStatus.RUNNING:
                    running_time = (get_current_time() - started_at).total_seconds()
                    error_msg = f"任务超时 (运行时间: {running_time:.1f}秒, 限制: {timeout_seconds}秒)"
                    
                    await crud_task_execution.update_status(
                        db=db,
                        execution_id=execution.id,
                        status=ExecutionStatus.TIMEOUT,
                        completed_at=get_current_time(),
                        error_message=error_msg
                    )
                    
                    # 记录到调度历史
                    await redis_services.history.add_history_event(
                        config_id=config_id,
                        event_data={
                            "task_id": task_id,
                            "status": "timeout",
                            "error": error_msg,
                            "timestamp": get_current_time().isoformat()
                        }
                    )
                    
                    logger.warning(f"标记任务 {task_id} ({config_name}) 为超时状态")
                    processed_count += 1
                
                processed_task_ids.append(task_id)
                
            except Exception as e:
                logger.error(f"处理超时任务 {task_data.get('task_id')} 时出错: {e}")
    
    # 从Redis中清理已处理的任务（使用新的服务）
    if processed_task_ids:
        await redis_services.timeout.cleanup_completed_tasks(processed_task_ids)
    
    result = {
        "config_id": config_id,
        "checked_at": get_current_time().isoformat(),
        "timeout_count": len(timeout_tasks),
        "processed_count": processed_count
    }
    
    logger.info(f"超时监控完成: 检测 {len(timeout_tasks)} 个，处理 {processed_count} 个")
    return result

async def _batch_get_configs(config_ids: List[int]) -> Dict[int, TaskConfig]:
    """批量获取任务配置，避免N+1查询"""
    if not config_ids:
        return {}
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TaskConfig).where(TaskConfig.id.in_(config_ids))
        )
        configs = result.scalars().all()
        
        return {config.id: config for config in configs}

async def _batch_get_executions(task_ids: List[str]) -> Dict[str, TaskExecution]:
    """批量获取任务执行记录，避免N+1查询"""
    if not task_ids:
        return {}
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TaskExecution).where(TaskExecution.task_id.in_(task_ids))
        )
        executions = result.scalars().all()
        
        return {execution.task_id: execution for execution in executions}

@broker.task(
    task_name="cleanup_timeout_monitor",
    queue="cleanup",
    retry_on_error=False,
)
async def cleanup_timeout_monitor_task(
    config_id: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    清理Redis中的过期监控数据 - 使用新的Redis服务
    """
    logger.info("开始清理超时监控数据...")
    
    # 使用新的Redis服务获取所有任务
    all_tasks = await redis_services.timeout.get_all_tasks()
    
    if not all_tasks:
        return {
            "config_id": config_id,
            "cleaned_at": get_current_time().isoformat(),
            "total_tasks": 0,
            "cleaned_count": 0
        }
    
    # 批量获取所有任务的执行状态，避免N+1查询
    task_ids = [task["task_id"] for task in all_tasks]
    executions_map = await _batch_get_executions(task_ids)
    
    # 找出已经完成的任务
    completed_task_ids = []
    for task_data in all_tasks:
        task_id = task_data["task_id"]
        execution = executions_map.get(task_id)
        
        if not execution or execution.status != ExecutionStatus.RUNNING:
            completed_task_ids.append(task_id)
    
    # 使用新的Redis服务清理已完成的任务
    cleaned_count = 0
    if completed_task_ids:
        cleaned_count = await redis_services.timeout.cleanup_completed_tasks(completed_task_ids)
    
    result = {
        "config_id": config_id,
        "cleaned_at": get_current_time().isoformat(),
        "total_tasks": len(all_tasks),
        "cleaned_count": cleaned_count
    }
    
    logger.info(f"清理完成: 总任务 {len(all_tasks)}，清理 {cleaned_count}")
    return result
```

**3.12. 重构任务管理器task_manager**
```python
"""
任务管理服务
统一管理任务的创建、调度、执行和监控
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from app.broker import broker
from app.services.redis_manager import redis_services  # 使用新的Redis服务管理器
from app.db.base import AsyncSessionLocal
from app.models.task_config import TaskConfig
from app.schemas.task_config_schemas import TaskConfigCreate, TaskConfigUpdate, TaskConfigQuery
from app.crud.task_config import crud_task_config
from app.crud.task_execution import crud_task_execution
from app.constant.task_registry import TaskType, ConfigStatus, SchedulerType, TaskRegistry
from app.models.task_execution import TaskExecution, ExecutionStatus
import uuid

logger = logging.getLogger(__name__)


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self.broker = broker
        self._initialized = False
        self._active_tasks = {}  # 缓存活跃任务
    
    async def initialize(self):
        """初始化任务管理器"""
        if self._initialized:
            return
        
        try:
            # 注意：调度器的初始化已经在main.py中通过redis_services.initialize()完成
            # 这里只需要标记初始化完成
            self._initialized = True
            logger.info("任务管理器初始化完成")
            
        except Exception as e:
            logger.error(f"任务管理器初始化失败: {e}")
            raise
    
    async def shutdown(self):
        """关闭任务管理器"""
        try:
            # 注意：Redis服务的关闭在main.py中统一处理
            self._initialized = False
            logger.info("任务管理器已关闭")
        except Exception as e:
            logger.error(f"任务管理器关闭失败: {e}")
    
    async def create_task_config(self, **config_data) -> Optional[int]:
        """创建任务配置"""
        async with AsyncSessionLocal() as db:
            try:
                # 创建配置对象
                config_obj = TaskConfigCreate(**config_data)
                config = await crud_task_config.create(db, config_obj)
                
                # 如果是调度任务且状态为活跃，注册到调度器
                if (config.scheduler_type != SchedulerType.MANUAL and 
                    config.status == ConfigStatus.ACTIVE):
                    # 使用新的Redis调度器服务
                    await redis_services.scheduler.register_task(config)
                    
                    # 记录调度事件到Redis历史
                    await redis_services.history.add_history_event(
                        config_id=config.id,
                        event_data={
                            "event": "task_scheduled",
                            "job_id": f"{TaskRegistry.SCHEDULED_TASK_PREFIX}{config.id}",
                            "job_name": config.name,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
                
                logger.info(f"已创建任务配置: {config.id} - {config.name}")
                return config.id
                
            except Exception as e:
                logger.error(f"创建任务配置失败: {e}")
                return None
    
    async def update_task_config(self, config_id: int, update_data: Dict[str, Any]) -> bool:
        """更新任务配置"""
        async with AsyncSessionLocal() as db:
            try:
                config = await crud_task_config.get(db, config_id)
                if not config:
                    return False
                
                # 创建更新对象
                update_obj = TaskConfigUpdate(**update_data)
                updated_config = await crud_task_config.update(db, config, update_obj)
                
                # 更新调度器中的任务
                if updated_config.scheduler_type != SchedulerType.MANUAL:
                    await redis_services.scheduler.update_task(updated_config)
                    
                    # 记录更新事件
                    await redis_services.history.add_history_event(
                        config_id=config_id,
                        event_data={
                            "event": "task_updated",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
                
                logger.info(f"已更新任务配置: {config_id}")
                return True
                
            except Exception as e:
                logger.error(f"更新任务配置失败: {e}")
                return False
    
    async def delete_task_config(self, config_id: int) -> bool:
        """删除任务配置"""
        async with AsyncSessionLocal() as db:
            try:
                # 先从调度器中移除
                await redis_services.scheduler.unregister_task(config_id)
                
                # 从数据库删除
                success = await crud_task_config.delete(db, config_id)
                
                if success:
                    # 记录删除事件
                    await redis_services.history.add_history_event(
                        config_id=config_id,
                        event_data={
                            "event": "task_deleted",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
                    logger.info(f"已删除任务配置: {config_id}")
                    
                return success
                
            except Exception as e:
                logger.error(f"删除任务配置失败: {e}")
                return False
    
    async def execute_task_immediately(self, config_id: int, **kwargs) -> Optional[str]:
        """立即执行任务"""
        async with AsyncSessionLocal() as db:
            try:
                config = await crud_task_config.get(db, config_id)
                if not config:
                    raise ValueError(f"任务配置不存在: {config_id}")
                
                # 获取任务函数
                task_func = self._get_task_function(config.task_type)
                if not task_func:
                    raise ValueError(f"不支持的任务类型: {config.task_type}")
                
                # 合并参数
                task_params = {**(config.parameters or {}), **kwargs}
                
                # 生成任务ID
                task_id = str(uuid.uuid4())
                task_params['task_id'] = task_id  # 传递task_id给任务函数
                
                # 发送任务到队列
                task = await task_func.kiq(config_id, **task_params)
                
                # 记录任务执行
                execution = await crud_task_execution.create(
                    db=db,
                    config_id=config_id,
                    task_id=task.task_id,
                    status=ExecutionStatus.RUNNING,
                    started_at=datetime.utcnow()
                )
                
                # 注册到超时监控器（使用新的Redis服务）
                if config.timeout_seconds:
                    await redis_services.timeout.add_task(
                        task_id=task.task_id,
                        config_id=config_id,
                        timeout_seconds=config.timeout_seconds,
                        started_at=execution.started_at
                    )
                
                # 记录执行事件
                await redis_services.history.add_history_event(
                    config_id=config_id,
                    event_data={
                        "event": "task_executed",
                        "task_id": task.task_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                
                # 更新状态
                await redis_services.history.update_status(config_id, "running")
                
                logger.info(f"已立即执行任务 {config_id}，任务ID: {task.task_id}")
                return task.task_id
                
            except Exception as e:
                logger.error(f"立即执行任务失败: {e}")
                
                # 记录失败事件
                await redis_services.history.add_history_event(
                    config_id=config_id,
                    event_data={
                        "event": "task_execution_failed",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                
                return None
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        try:
            # 先尝试从活跃任务缓存获取
            if task_id in self._active_tasks:
                return self._active_tasks[task_id]
            
            # 从Redis结果后端获取任务状态
            is_ready = await self.broker.result_backend.is_result_ready(task_id)
            
            if is_ready:
                result = await self.broker.result_backend.get_result(task_id)
                
                status_info = {
                    "task_id": task_id,
                    "status": ExecutionStatus.SUCCESS.value if result.is_err is False else ExecutionStatus.FAILED.value,
                    "result": result.return_value if result.is_err is False else None,
                    "error": str(result.error) if result.is_err and result.error else None,
                    "execution_time": result.execution_time if hasattr(result, 'execution_time') else None
                }
                
                # 更新数据库中的执行记录
                async with AsyncSessionLocal() as db:
                    execution = await crud_task_execution.get_by_task_id(db, task_id)
                    if execution:
                        await crud_task_execution.update_status(
                            db=db,
                            execution_id=execution.id,
                            status=ExecutionStatus.SUCCESS if result.is_err is False else ExecutionStatus.FAILED,
                            completed_at=datetime.utcnow(),
                            result={"return_value": result.return_value} if result.is_err is False else None,
                            error_message=str(result.error) if result.is_err else None
                        )
                        
                        # 更新Redis中的状态
                        if execution.config_id:
                            status = "success" if result.is_err is False else "failed"
                            await redis_services.history.update_status(execution.config_id, status)
                
                return status_info
            else:
                # 任务还在执行中或不存在
                async with AsyncSessionLocal() as db:
                    execution = await crud_task_execution.get_by_task_id(db, task_id)
                    
                    if execution:
                        return {
                            "task_id": task_id,
                            "status": execution.status,
                            "result": execution.result,
                            "error": execution.error_message,
                            "started_at": execution.started_at.isoformat() if execution.started_at else None,
                            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                        }
                    else:
                        return {
                            "task_id": task_id,
                            "status": TaskRegistry.TASK_STATUS_PENDING,
                            "result": None,
                            "error": None,
                        }
                        
        except Exception as e:
            logger.error(f"获取任务状态失败 {task_id}: {e}")
            return {
                "task_id": task_id,
                "status": TaskRegistry.TASK_STATUS_ERROR,
                "result": None,
                "error": str(e),
            }
    
    async def manage_scheduled_task(self, config_id: int, action: str) -> Dict[str, Any]:
        """
        管理调度任务（启动、停止、暂停、恢复、重载）
        
        Args:
            config_id: 任务配置ID
            action: 操作类型
            
        Returns:
            操作结果
        """
        async with AsyncSessionLocal() as db:
            try:
                config = await crud_task_config.get(db, config_id)
                if not config:
                    return {
                        "success": False,
                        "message": f"任务配置 {config_id} 不存在",
                        "config_id": config_id
                    }
                
                success = False
                new_status = config.status
                
                if action == "start":
                    # 启动任务调度
                    if config.scheduler_type != SchedulerType.MANUAL:
                        success = await redis_services.scheduler.register_task(config)
                        new_status = ConfigStatus.ACTIVE if success else ConfigStatus.ERROR
                    
                elif action == "stop":
                    # 停止任务调度
                    success = await redis_services.scheduler.unregister_task(config_id)
                    new_status = ConfigStatus.INACTIVE if success else ConfigStatus.ERROR
                    
                elif action == "pause":
                    # 暂停任务调度
                    success = await redis_services.scheduler.pause_task(config_id)
                    new_status = ConfigStatus.PAUSED if success else ConfigStatus.ERROR
                    
                elif action == "resume":
                    # 恢复任务调度
                    success = await redis_services.scheduler.resume_task(config)
                    new_status = ConfigStatus.ACTIVE if success else ConfigStatus.ERROR
                    
                elif action == "reload":
                    # 重新加载任务调度
                    success = await redis_services.scheduler.update_task(config)
                    new_status = ConfigStatus.ACTIVE if success else ConfigStatus.ERROR
                
                # 更新数据库状态
                if new_status != config.status:
                    await crud_task_config.update_status(db, config_id, new_status)
                
                # 记录调度事件到Redis
                event_type_map = {
                    "start": "task_started",
                    "stop": "task_stopped",
                    "pause": "task_paused",
                    "resume": "task_resumed",
                    "reload": "task_reloaded"
                }
                
                await redis_services.history.add_history_event(
                    config_id=config_id,
                    event_data={
                        "event": event_type_map.get(action, "task_action"),
                        "action": action,
                        "success": success,
                        "new_status": new_status.value,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                
                # 更新Redis中的状态
                await redis_services.history.update_status(config_id, new_status.value)
                
                return {
                    "success": success,
                    "message": f"任务 {config_id} {action} {'成功' if success else '失败'}",
                    "action": action,
                    "config_id": config_id,
                    "status": new_status.value
                }
                
            except Exception as e:
                logger.error(f"管理调度任务失败 {config_id}: {e}")
                
                # 记录错误事件
                await redis_services.history.add_history_event(
                    config_id=config_id,
                    event_data={
                        "event": "task_action_failed",
                        "action": action,
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                
                return {
                    "success": False,
                    "message": f"操作失败: {str(e)}",
                    "action": action,
                    "config_id": config_id,
                    "status": "error"
                }
    
    async def list_active_tasks(self) -> List[Dict[str, Any]]:
        """列出活跃的任务执行记录"""
        from app.constant.task_registry import TaskRegistry
        
        async with AsyncSessionLocal() as db:
            executions = await crud_task_execution.get_running_executions(db)
            
            tasks = []
            for e in executions:
                # 获取实时状态
                status = await self.get_task_status(e.task_id)
                
                # 获取任务配置以获取队列信息
                config = await crud_task_config.get(db, e.config_id)
                queue_name = TaskRegistry.DEFAULT_QUEUE
                
                if config and config.task_type:
                    try:
                        queue_name = TaskRegistry.get_queue_name(config.task_type)
                    except Exception:
                        queue_name = TaskRegistry.DEFAULT_QUEUE
                
                tasks.append({
                    "task_id": e.task_id,
                    "config_id": e.config_id,
                    "config_name": config.name if config else None,
                    "status": status.get("status", e.status.value if hasattr(e.status, 'value') else e.status),
                    "started_at": e.started_at.isoformat() if e.started_at else None,
                    "queue": queue_name,
                    "task_type": config.task_type.value if config and config.task_type else None,
                    "parameters": config.parameters if config else {},
                })
            
            return tasks
    
    async def _check_broker_connection(self) -> bool:
        """检查broker连接状态"""
        try:
            # 检查 result backend (Redis) 连接
            if self.broker.result_backend:
                test_task_id = "connection_test_" + str(datetime.utcnow().timestamp())
                await self.broker.result_backend.is_result_ready(test_task_id)
            
            return True
            
        except Exception as e:
            logger.warning(f"Broker连接检查失败: {e}")
            return False
    
    async def _get_scheduled_jobs_count(self) -> int:
        """获取已调度的任务数量"""
        try:
            # 使用新的Redis调度器服务
            tasks = await redis_services.scheduler.get_all_schedules()
            return len(tasks)
        except Exception as e:
            logger.warning(f"获取调度任务数量失败: {e}")
            return 0
    
    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            # 检查各组件状态
            broker_connected = await self._check_broker_connection()
            scheduled_count = await self._get_scheduled_jobs_count()
            active_tasks = await self.list_active_tasks()
            
            # 获取任务配置统计
            async with AsyncSessionLocal() as db:
                stats = await crud_task_config.get_stats(db)
            
            # 从Redis获取最近的调度历史（可选）
            recent_history = []
            try:
                # 获取最近的调度事件
                for config_id in range(1, min(6, stats.get("total_configs", 0) + 1)):
                    history = await redis_services.history.get_history(config_id, limit=1)
                    if history:
                        recent_history.extend(history)
            except:
                pass  # 历史记录是可选的
            
            return {
                "broker_connected": broker_connected,
                "scheduler_running": self._initialized,
                "total_configs": stats.get("total_configs", 0),
                "active_configs": stats.get("active_configs", 0),
                "total_scheduled_jobs": scheduled_count,
                "total_active_tasks": len(active_tasks),
                "timestamp": datetime.utcnow().isoformat(),
                "scheduler": {
                    "initialized": self._initialized,
                    "scheduled_tasks": scheduled_count,
                    "redis_connected": redis_services.scheduler._initialized
                },
                "worker": {
                    "broker_connected": broker_connected,
                    "active_tasks": len(active_tasks)
                },
                "queues": {
                    TaskRegistry.DEFAULT_QUEUE: {
                        "status": TaskRegistry.QUEUE_STATUS_ACTIVE if broker_connected else TaskRegistry.QUEUE_STATUS_DISCONNECTED
                    }
                },
                "recent_events": recent_history[:5]  # 最近5个事件
            }
            
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {
                "broker_connected": False,
                "scheduler_running": False,
                "total_configs": 0,
                "active_configs": 0,
                "total_scheduled_jobs": 0,
                "total_active_tasks": 0,
                "timestamp": datetime.utcnow().isoformat(),
                "scheduler": {"initialized": False, "scheduled_tasks": 0, "error": str(e)},
                "worker": {"broker_connected": False, "active_tasks": 0, "error": str(e)},
                "queues": {}
            }
    
    def _get_task_function(self, task_type: TaskType):
        """根据任务类型获取任务函数"""
        from app.constant.task_registry import get_task_function
        return get_task_function(task_type)
    
    async def get_task_config(self, config_id: int, verify_scheduler_status: Optional[bool] = False, include_stats: Optional[bool] = False) -> Optional[Dict[str, Any]]:
        """获取任务配置详情"""
        async with AsyncSessionLocal() as db:
            config = await crud_task_config.get_with_relations(db, config_id)
            if not config:
                return None
            
            result = {
                'id': config.id,
                'name': config.name,
                'description': config.description,
                'task_type': config.task_type.value if hasattr(config.task_type, 'value') else config.task_type,
                'scheduler_type': config.scheduler_type.value if hasattr(config.scheduler_type, 'value') else config.scheduler_type,
                'status': config.status.value if hasattr(config.status, 'value') else config.status,
                'parameters': config.parameters or {},
                'schedule_config': config.schedule_config or {},
                'max_retries': config.max_retries or 0,
                'timeout_seconds': config.timeout_seconds,
                'priority': config.priority,
                'created_at': config.created_at.isoformat() if config.created_at else None,
                'updated_at': config.updated_at.isoformat() if config.updated_at else None
            }
            
            # 验证调度器中的状态
            if verify_scheduler_status:
                scheduled_tasks = await redis_services.scheduler.get_all_schedules()
                task_id = f"{TaskRegistry.SCHEDULED_TASK_PREFIX}{config_id}"
                is_scheduled = any(t.get("task_id") == task_id for t in scheduled_tasks)
                result['scheduler_status'] = "scheduled" if is_scheduled else "not_scheduled"
            
            # 包含执行统计数据
            if include_stats:
                stats = await crud_task_config.get_execution_stats(db, config_id)
                result["stats"] = stats
                
                # 从Redis获取最近的历史记录
                history = await redis_services.history.get_history(config_id, limit=10)
                result["recent_history"] = history
            
            return result
    
    async def list_task_configs(self, query: TaskConfigQuery) -> List[Dict[str, Any]]:
        """列出任务配置"""
        async with AsyncSessionLocal() as db:
            configs, _ = await crud_task_config.get_by_query(db, query)
            
            results = []
            
            for c in configs:
                config_dict = {
                    'id': c.id,
                    'name': c.name,
                    'description': c.description,
                    'task_type': c.task_type.value if hasattr(c.task_type, 'value') else c.task_type,
                    'scheduler_type': c.scheduler_type.value if hasattr(c.scheduler_type, 'value') else c.scheduler_type,
                    'status': c.status.value if hasattr(c.status, 'value') else c.status,
                    'parameters': c.parameters or {},
                    'schedule_config': c.schedule_config or {},
                    'priority': c.priority,
                    'created_at': c.created_at.isoformat() if c.created_at else None,
                    'max_retries': c.max_retries or 0,
                    'timeout_seconds': c.timeout_seconds,
                    'updated_at': c.updated_at.isoformat() if c.updated_at else None,
                    'scheduler_status': None,
                    'stats': None
                }
                results.append(config_dict)
            return results

    @staticmethod
    async def record_task_execution(db, config_id: Optional[int], status: str, result: Dict = None, error: str = None):
        """记录任务执行结果到数据库"""
        execution = TaskExecution(
            config_id=config_id,
            task_id=str(uuid.uuid4()),
            status=status,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            result=result,
            error_message=error
        )
        db.add(execution)
        await db.commit()
        
        # 记录到Redis历史
        await redis_services.history.add_history_event(
            config_id=config_id or 0,
            event_data={
                "event": "task_execution_recorded",
                "task_id": execution.task_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat()
            }
        )


# 全局任务管理器实例
task_manager = TaskManager()
```

**3.13. 重构broker.py**
```python
"""
TaskIQ Broker 配置
统一管理任务队列和调度器
"""
import uuid
import os
from typing import Optional
from taskiq import TaskiqEvents
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

from app.core.config import settings

# 配置 RabbitMQ broker
broker = AioPikaBroker(
    url=settings.rabbitmq.URL,
).with_id_generator(
    lambda: str(uuid.uuid4())
).with_result_backend(
    RedisAsyncResultBackend(
        redis_url=settings.redis.CONNECTION_URL,
        result_ex_time=settings.taskiq.RESULT_EX_TIME,
    )
)

# 配置任务事件监听器
@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def on_worker_startup(state: dict) -> None:
    """Worker 启动时的初始化"""
    # 注意：不再需要在这里连接Redis超时存储
    # Redis服务的初始化已经移到了main.py的lifespan中
    pass


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def on_worker_shutdown(state: dict) -> None:
    """Worker 关闭时的清理"""
    # 注意：不再需要在这里断开Redis超时存储
    # Redis服务的清理已经移到了main.py的lifespan中
    pass

```

### 第 5 步：重构业务逻辑

以下部分保持不变，只是引用路径改为使用新的redis_services：

```python
# backend/app/api/v1/routes/auth_routes.py (主要修改部分)
from app.services.redis_manager import redis_services

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> Token:
    try:
        # ... 用户验证逻辑保持不变 ...
        
        # 创建令牌对
        access_token, refresh_token, expires_at = create_token_pair(
            subject=str(user.id), 
            remember_me=login_data.remember_me
        )
        
        # 在创建新令牌前，先吊销该用户的所有现有刷新令牌
        await redis_services.auth.revoke_all_user_tokens(user.id)
        
        # 将刷新令牌存储到Redis而不是数据库
        await redis_services.auth.store_refresh_token(
            token=refresh_token,
            user_id=user.id,
            expires_in_days=settings.security.REFRESH_TOKEN_EXPIRE_DAYS
        )
        
        return Token(
            access_token=access_token, 
            refresh_token=refresh_token,
            token_type="bearer",
            expires_at=expires_at
        )
    except Exception as e:
        raise handle_error(e)
@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    refresh_data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> Token:
    try:
        # 验证刷新令牌的有效性
        is_valid, payload, error_type = verify_token(refresh_data.refresh_token)
        if not is_valid:
            if error_type == "expired":
                raise InvalidRefreshTokenError("刷新令牌已过期")
            else:
                raise InvalidRefreshTokenError()
        
        # 检查令牌类型
        if payload.get("type") != "refresh_token":
            raise InvalidRefreshTokenError("无效的令牌类型")
        
        # 从Redis检查刷新令牌是否存在
        token_data = await redis_services.auth.get_refresh_token_payload(refresh_data.refresh_token)
        if not token_data:
            raise InvalidRefreshTokenError()
        
        # 提取用户标识
        user_id = token_data.get("user_id")
        if not user_id:
            raise InvalidRefreshTokenError("令牌缺少用户标识")
        
        # 吊销当前使用的刷新令牌
        await redis_services.auth.revoke_token(refresh_data.refresh_token)
        
        # 创建新的令牌对
        access_token, new_refresh_token, expires_at = create_token_pair(subject=str(user_id))
        
        # 存储新的刷新令牌到Redis
        await redis_services.auth.store_refresh_token(
            token=new_refresh_token,
            user_id=user_id
        )
        
        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_at=expires_at
        )
    except Exception as e:
        raise handle_error(e)
@router.post("/logout", status_code=204)
async def logout(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> None:
    try:
        # 吊销用户的所有刷新令牌（从Redis）
        await redis_services.auth.revoke_all_user_tokens(current_user.id)
    except Exception as e:
        raise handle_error(e)

```

```python
# backend/app/dependencies/current_user.py (主要修改部分)
from app.services.redis_manager import redis_services
async def get_current_user_from_request(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> User:
    # ... token验证逻辑保持不变 ...
    
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise AuthenticationError("无效的用户ID格式")
    
    # 首先尝试从Redis缓存获取用户信息
    cached_user = await redis_services.cache.get_user_cache(user_id)
    if cached_user:
        # 将缓存数据转换为User对象
        user = User(**cached_user)
        request.state.current_user = user
        return user
    
    # 缓存未命中，从数据库查询
    user = await crud_user.get(db, id=user_id)
    if not user:
        logger.warning(f"有效令牌但找不到用户ID: {user_id}")
        raise UserNotFoundError()
    
    # 将用户信息存入Redis缓存
    user_dict = {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "age": user.age,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat()
    }
    await redis_services.cache.set_user_cache(user_id, user_dict)
    
    request.state.current_user = user
    return user

```

### 第 6 步：清理旧代码

**3.14. 删除相关文件（确认迁移完成后）**
```bash
# 删除数据库Token模型相关文件
rm backend/app/models/token.py
rm backend/app/crud/token.py

# 删除schedule_events相关文件（如果已被Redis完全替代）
rm backend/app/models/schedule_event.py
rm backend/app/crud/schedule_event.py
rm backend/app/schemas/schedule_event.py

# 删除旧的redis_timeout_store.py（已被新服务替代）
rm backend/app/core/redis_timeout_store.py
```

**3.15. 修改数据库迁移**
创建新的Alembic迁移来删除不需要的表：
```python
# 在alembic/versions/中创建新迁移
"""remove_unused_tables
Revision ID: xxx
Revises: xxx
Create Date: xxx
"""
def upgrade():
    # 删除refresh_tokens表
    op.drop_table('refresh_tokens')
    
    # 删除schedule_events表（如果确认不再需要）
    op.drop_table('schedule_events')

def downgrade():
    # 如果需要回滚，重新创建这些表
    pass
```

-----

## 4. 重构优势

**性能提升：**
- Token验证从数据库IO变为Redis内存操作
- 用户查询缓存减少数据库负载
- 调度任务通过RedisScheduleSource实现分布式调度
- 调度历史使用Redis Lists提高写入性能

**架构优化：**
- 真正的分布式调度器替代了单机的scheduler.py
- 调度历史记录与调度执行解耦
- 与现有TaskIQ架构深度集成
- 统一的Redis服务管理

**功能增强：**
- 支持分布式环境下的任务调度
- 调度状态和历史的实时记录
- 完整的超时监控机制
- 所有Redis操作统一管理

**维护性改善：**
- 清晰的服务职责划分
- 统一的Redis连接管理
- 简化的错误处理
- 更好的代码复用性

-----