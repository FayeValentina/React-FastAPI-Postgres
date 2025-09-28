# `router.py` (v1) 文档

此文件是API版本1（v1）的根路由器。它的主要职责是聚合所有属于该版本的API端点。

## 主要功能

1.  **创建v1路由**：创建了一个 `APIRouter` 实例，作为v1版本所有API的集合点。

2.  **包含子路由**：通过 `router.include_router()` 方法，将来自 `app.api.v1.endpoints` 目录下的各个模块的路由包含进来。每个子路由都代表了一组相关的功能，例如：
    - `users.router`：处理用户相关的操作（如获取用户信息）。
    - `auth.router`：处理认证相关的操作（如登录、注册、刷新令牌）。
    - `content.router`：处理内容抓取和管理相关的操作。
    - `tasks.router`：处理后台任务（如Celery任务）相关的操作。
    - `knowledge.router`：处理知识库相关的操作。
    - `llm_ws.router`：处理与大语言模型（LLM）通过WebSocket进行交互的路由。
    - `admin_settings.router`：处理管理员设置相关的操作。

这个文件起到了组织和构建v1版本API结构的核心作用，使得API端点可以模块化管理。
