# APScheduler + Celery 混合架构重构指南

## 1. 现有项目架构

### 当前架构图
```
FastAPI Backend (app/main.py)
    ↓
APScheduler (app/tasks/scheduler.py) - 内存调度
    ↓
Background Tasks (app/tasks/jobs/*.py) - 同步执行
    ↓
PostgreSQL (业务数据存储)
```

### 现有项目结构
```
backend/
├── app/
│   ├── main.py                    # FastAPI应用入口
│   ├── api/v1/routes/            # API路由
│   │   ├── auth_routes.py
│   │   ├── bot_config_routes.py  # Bot配置管理
│   │   ├── scraping_routes.py    # 爬取控制
│   │   └── task_routes.py        # 任务管理
│   ├── tasks/                    # 当前任务系统
│   │   ├── scheduler.py          # APScheduler配置
│   │   ├── manager.py            # 任务管理器
│   │   ├── jobs/
│   │   │   ├── scraping.py       # 爬取任务
│   │   │   └── cleanup.py        # 清理任务
│   │   └── decorators.py         # 任务装饰器
│   ├── services/                 # 业务服务
│   │   ├── reddit_scraper_service.py
│   │   └── scraping_orchestrator.py
│   └── crud/                     # 数据访问层
├── docker-compose.yml            # 当前3个容器
└── pyproject.toml               # 当前依赖配置
```

### 当前运行容器 (3个)
- `frontend` - React前端
- `backend` - FastAPI + APScheduler
- `postgres` - PostgreSQL数据库

## 2. 重构后的项目架构

### 目标架构图
```
FastAPI Backend (API + 动态任务管理)
    ↓
APScheduler (调度器) → RabbitMQ (消息队列) → Celery Workers (分布式执行)
    ↓                     ↓                      ↓
PostgreSQL (调度存储)   消息持久化             PostgreSQL (结果存储)
```

### 重构后项目结构
```
backend/
├── app/
│   ├── main.py                    # FastAPI应用入口 (修改)
│   ├── celery_app.py             # 🆕 Celery应用配置
│   ├── api/v1/routes/            # API路由 (部分修改)
│   │   ├── auth_routes.py
│   │   ├── bot_config_routes.py  # ✏️ 修改任务管理调用
│   │   ├── scraping_routes.py    # ✏️ 修改任务触发方式
│   │   └── task_routes.py        # ✏️ 更新任务管理API
│   ├── tasks/                    # 重构任务系统
│   │   ├── scheduler.py          # 🆕 混合调度器 (替代旧scheduler.py)
│   │   ├── celery_tasks.py       # 🆕 Celery任务定义
│   │   ├── message_sender.py     # 🆕 消息发送服务
│   │   └── [删除] jobs/, manager.py, decorators.py
│   ├── services/                 # 业务服务 (保持不变)
│   │   ├── reddit_scraper_service.py
│   │   ├── scraping_orchestrator.py
│   │   └── schedule_manager.py   # 🆕 调度管理服务
│   └── crud/                     # 数据访问层 (保持不变)
├── docker-compose.yml            # ✏️ 扩展到7个容器
└── pyproject.toml               # ✏️ 添加Celery依赖
```

### 重构后运行容器 (7个)
- `frontend` - React前端
- `backend` - FastAPI + APScheduler调度器
- `postgres` - PostgreSQL数据库
- `rabbitmq` - RabbitMQ消息队列 🆕
- `celery_worker` - 任务执行容器 🆕
- `flower` - Celery监控界面 🆕
- `pgadmin` - 数据库管理界面

## 3. 需要添加的文件夹和文件

### 🆕 新增核心文件
```
app/
├── celery_app.py                 # Celery应用配置
├── tasks/
│   ├── scheduler.py       # 混合调度器
│   ├── celery_tasks.py          # Celery任务定义
│   └── message_sender.py        # 消息发送工具
└── services/
    └── schedule_manager.py       # 调度管理服务
```

### 🆕 新增配置文件
```
scripts/                         # 🆕 启动脚本目录
├── start_celery_worker.sh       # Celery Worker启动脚本
├── start_celery_beat.sh         # Celery Beat启动脚本（备用）
└── start_flower.sh              # Flower启动脚本
```

### 🆕 新增Docker相关
```
docker-compose.yml               # 扩展容器配置
.env                            # 添加Celery和RabbitMQ配置
```

## 4. 需要修改的现存文件

### 📝 配置文件修改

#### `pyproject.toml`
```toml
[tool.poetry.dependencies]
# 保留现有依赖...
apscheduler = "^3.10.4"          # 保留APScheduler

# 🆕 添加Celery相关依赖
celery = {extras = ["amqp", "sqlalchemy"], version = "^5.3.0"} # RabbitMQ + PostgreSQL 结果后端
kombu = "^5.3.0"
redis = "^5.0.0"                 # 备用broker选项
flower = "^2.0.1"                # 监控工具
```

#### `.env` 环境变量
```env
# ... 现有配置 ...

# RabbitMQ Configuration
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VHOST=/

# Celery Configuration (可选，有默认值)
# CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672/
# CELERY_RESULT_BACKEND=db+postgresql+asyncpg://user:pass@host/db

# Flower Configuration
FLOWER_USER=admin
FLOWER_PASSWORD=admin_password
```

#### `docker-compose.yml`
```yaml
version: "3.8"

services:
  # ... 现有服务保持不变 ...

  rabbitmq:
    image: rabbitmq:3.12-management
    env_file:
      - .env
    ports:
      - "5672:5672"    # AMQP 端口
      - "15672:15672"  # 管理界面端口
    environment:
      - RABBITMQ_DEFAULT_USER=${RABBITMQ_USER:-guest}
      - RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASSWORD:-guest}
      - RABBITMQ_DEFAULT_VHOST=${RABBITMQ_VHOST:-/}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - dbNetWork

  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.celery
    env_file:
      - .env
    environment:
      - POSTGRES_HOST=${POSTGRES_HOST}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_USER=${RABBITMQ_USER:-guest}
      - RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-guest}
      - C_FORCE_ROOT=true  # 允许以 root 运行
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    command: celery -A celery_worker worker --loglevel=info --concurrency=2 -Q default,cleanup,scraping
    volumes:
      - ./backend:/app
    networks:
      - dbNetWork
    deploy:
      replicas: 2  # 可以运行多个 worker
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3

  flower:
    image: mher/flower:2.0
    env_file:
      - .env
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=amqp://${RABBITMQ_USER:-guest}:${RABBITMQ_PASSWORD:-guest}@rabbitmq:5672/${RABBITMQ_VHOST:-/}
      - FLOWER_PORT=5555
      - FLOWER_BASIC_AUTH=${FLOWER_USER:-admin}:${FLOWER_PASSWORD:-admin}
    depends_on:
      - rabbitmq
      - celery_worker
    networks:
      - dbNetWork
    command: celery flower --broker=amqp://${RABBITMQ_USER:-guest}:${RABBITMQ_PASSWORD:-guest}@rabbitmq:5672/${RABBITMQ_VHOST:-/}

volumes:
  postgres_data:
  rabbitmq_data:  # 新增

networks:
  dbNetWork:
    driver: bridge
```

### 📝 核心应用文件修改

#### `app/main.py`
```python
# ✏️ 修改生命周期管理
from app.tasks.scheduler import scheduler  # 替代原scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    await scheduler.start()  # 启动混合调度器
    yield
    # 关闭时
    scheduler.shutdown()
```

#### `app/core/config.py`
```python
# 在现有配置类中添加

class RabbitMQSettings(BaseSettings):
    """RabbitMQ 配置"""
    HOST: str = "rabbitmq"
    PORT: int = 5672
    USER: str = "guest"
    PASSWORD: str = "guest"
    VHOST: str = "/"
    
    @property
    def URL(self) -> str:
        return f"amqp://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.VHOST}"
    
    model_config = SettingsConfigDict(
        env_prefix="RABBITMQ_",
        env_file=[".env.local", ".env"],
        env_file_encoding="utf-8",
        extra="allow"
    )


class CelerySettings(BaseSettings):
    """Celery 配置"""
    BROKER_URL: Optional[str] = None
    RESULT_BACKEND: Optional[str] = None
    
    @field_validator("BROKER_URL", mode="before")
    @classmethod
    def set_broker_url(cls, v: Optional[str], info: Any) -> str:
        if v:
            return v
        # 默认使用 RabbitMQ
        rabbitmq = RabbitMQSettings()
        return rabbitmq.URL
    
    @field_validator("RESULT_BACKEND", mode="before")
    @classmethod
    def set_result_backend(cls, v: Optional[str], info: Any) -> str:
        if v:
            return v
        # 默认使用 PostgreSQL
        postgres = PostgresSettings()
        return f"db+{postgres.SQLALCHEMY_DATABASE_URL}"
    
    model_config = SettingsConfigDict(
        env_prefix="CELERY_",
        env_file=[".env.local", ".env"],
        env_file_encoding="utf-8",
        extra="allow"
    )


class Settings(BaseSettings):
    # ... 现有配置 ...
    rabbitmq: RabbitMQSettings = RabbitMQSettings()
    celery: CelerySettings = CelerySettings()
```

### 📝 API路由修改

#### `app/api/v1/routes/bot_config_routes.py`
```python
# ✏️ 替换导入
# from app.tasks.jobs.scraping import create_bot_scraping_task, remove_bot_scraping_task
from app.services.schedule_manager import ScheduleManager

@router.post("", response_model=BotConfigResponse, status_code=201)
async def create_bot_config(...):
    # ✏️ 修改任务创建调用
    if bot_config.auto_scrape_enabled:
        # 原来: await create_bot_scraping_task(...)
        # 现在: 
        ScheduleManager.create_bot_schedule(
            bot_config.id, 
            bot_config.name,
            bot_config.scrape_interval_hours
        )
```

#### `app/api/v1/routes/scraping_routes.py`
```python
# ✏️ 修改批量爬取实现
@router.post("/bot-configs/batch-scrape")
async def batch_trigger_scraping(...):
    # 原来: 直接调用orchestrator.execute_multiple_configs()
    # 现在: 发送任务到Celery队列
    from app.tasks.message_sender import MessageSender
    
    tasks = []
    for config_id in valid_config_ids:
        task_id = await MessageSender.send_scraping_task(
            config_id, session_type, queue='scraping'
        )
        tasks.append(task_id)
```

#### `app/api/v1/routes/task_routes.py`
```python
# ✏️ 更新任务管理API
# 需要同时管理APScheduler任务和Celery任务状态
from app.tasks.scheduler import scheduler

@router.get("", response_model=List[JobInfo])
async def list_jobs(...):
    # APScheduler任务列表
    scheduler_jobs = scheduler.get_jobs()
    
    # 🆕 Celery任务状态（通过Flower API或直接查询）
    celery_tasks = await get_celery_task_status()
    
    # 合并返回
    return scheduler_jobs + celery_tasks
```

### 📝 任务系统重构

#### 删除的文件
```
❌ app/tasks/scheduler.py        # 替换为hybrid_scheduler.py
❌ app/tasks/manager.py          # 功能整合到其他服务
❌ app/tasks/decorators.py       # Celery内置重试等功能
❌ app/tasks/jobs/scraping.py    # 重写为celery_tasks.py
❌ app/tasks/jobs/cleanup.py     # 重写为celery_tasks.py
```

#### 修改的导入
```python
# 所有使用原任务系统的文件需要更新导入：

# 原来:
from app.tasks import task_scheduler
from app.tasks.jobs.scraping import create_bot_scraping_task

# 现在:  
from app.tasks.scheduler import scheduler
from app.services.schedule_manager import ScheduleManager
```

## 5. 重构步骤详解

### 步骤1: 安装新依赖
```bash
cd backend
poetry add celery[redis] kombu flower
```

### 步骤2: 创建新文件
```bash
# 创建Celery相关文件
touch app/celery_app.py
touch app/tasks/scheduler.py
touch app/tasks/celery_tasks.py
touch app/tasks/message_sender.py
touch app/services/schedule_manager.py
```

### 步骤3: 删除旧文件
```bash
# 删除旧的任务系统文件
rm app/tasks/scheduler.py
rm app/tasks/manager.py  
rm app/tasks/decorators.py
rm -rf app/tasks/jobs/
```

### 步骤4: 修改配置
```bash
# 更新Docker Compose（添加新容器）
# 更新环境变量配置
# 更新依赖配置
```

### 步骤5: 修改业务逻辑
```bash
# 更新所有涉及任务调度的路由文件
# 更新导入语句
# 修改任务调用方式
```

## 6. 关键改动点对比

### 任务创建方式
```python
# 🔴 原来 (直接执行)
from app.tasks.jobs.scraping import create_bot_scraping_task

await create_bot_scraping_task(bot_config_id, name, interval_hours)

# 🟢 现在 (APScheduler调度 + Celery执行)
from app.services.schedule_manager import ScheduleManager

ScheduleManager.create_bot_schedule(bot_config_id, name, interval_hours)
```

### 任务执行方式
```python
# 🔴 原来 (同步执行)
@task_scheduler.add_job(...)
async def execute_bot_scraping(bot_config_id):
    orchestrator = ScrapingOrchestrator()
    result = await orchestrator.execute_scraping_session(...)
    return result

# 🟢 现在 (异步消息)
# APScheduler调度器发送消息到RabbitMQ
async def _send_scraping_task_to_queue(bot_config_id):
    message = {
        'task': 'execute_bot_scraping',
        'args': [bot_config_id],
        'queue': 'scraping'
    }
    await rabbitmq_sender.send_message(message)

# Celery Worker执行实际任务
@celery_app.task
def execute_bot_scraping(bot_config_id):
    # 执行逻辑保持不变，只是运行环境改为Celery Worker
```

### 手动任务触发
```python
# 🔴 原来 (直接异步执行)
@router.post("/scraping/start")
async def start_scraping(...):
    orchestrator = ScrapingOrchestrator()
    result = await orchestrator.execute_scraping_session(...)

# 🟢 现在 (发送到队列)
@router.post("/scraping/start") 
async def start_scraping(...):
    task_id = await MessageSender.send_scraping_task(
        config_id, session_type='manual', queue='scraping'
    )
    return {"task_id": task_id, "status": "queued"}
```

## 7. 迁移验证清单

### ✅ 功能验证
- [ ] APScheduler调度器正常启动
- [ ] RabbitMQ消息队列正常运行
- [ ] Celery Workers正常接收和执行任务
- [ ] 定时任务按预期调度
- [ ] 手动任务触发正常
- [ ] 任务重试机制工作
- [ ] 数据库连接正常

### ✅ 监控验证
- [ ] Flower界面显示Worker状态
- [ ] RabbitMQ管理界面显示队列状态
- [ ] FastAPI文档正常访问
- [ ] 数据库中任务执行历史正常记录