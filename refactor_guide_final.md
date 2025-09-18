# 超管动态配置最终实装指南

> 目标：将密钥（Secrets）与动态参数（Parameters）彻底解耦，在 Redis 中集中管理可调参数，通过独立的 `admin.my-domain.com` + `oauth2_proxy` + 双重校验为超级管理员提供唯一入口，并保证可观测性与回滚能力。

---

## 阶段一览

1. **基线准备**：备份配置、梳理参数、对齐依赖
2. **配置分层**：划分静态/动态参数，初始化 Redis 存储
3. **动态服务**：实现 `DynamicSettingsService` 并改造业务读取逻辑
4. **管理 API**：新增受保护的 `/api/v1/admin/settings` 路由
5. **超级管理员前端**：在 `admin.my-domain.com` 提供参数管理界面
6. **网关与认证**：配置 Nginx 与 `oauth2_proxy`，注入内部密钥
7. **审计与回滚**：记录变更、设置降级路径
8. **验证与上线**：在测试/生产环境逐步发布并监控

每个阶段完成后执行验收项，全部通过后再进入下一阶段。

---

## 阶段 0 —— 基线与准备 ✅（已完成）

**目标**：明确现有配置与依赖，避免遗漏和回滚困难。

**操作步骤**
- 备份 `.env*`、`docker-compose*.yml`、Nginx、`oauth2_proxy` 配置：
  ```bash
  cp .env.prod .env.prod.bak_$(date +%Y%m%d)
  cp docker-compose.prod.yml docker-compose.prod.yml.bak_$(date +%Y%m%d)
  ```
- 在 `backend/app/core/config.py` 中列出当前所有参数，标记为 **密钥/参数** 两类。
- 与 DevOps 确认 Redis、Nginx、`oauth2_proxy`、证书等资源可用。
- 创建实施清单（可用 Issue/Jira），拆分任务给后端、前端、运维。

**验收**：完成参数分类表；所有关键配置存在最新备份；实施清单获团队确认。

---

## 阶段 1 —— 配置分层与 Redis 初始化 ✅（已完成）

**目标**：让密钥继续停留在环境变量，把可调参数集中写入 Redis，并保留默认兜底。

**操作步骤**
- 保留静态密钥在 `.env*`：数据库、JWT、第三方 API Key 等。
- 选定 Redis 键名（建议 `app:dynamic_settings`），将参数 JSON 化：
  ```json
  {
    "RAG_TOP_K": 5,
    "RAG_MIN_SIM": 0.78,
    "...": "..."
  }
  ```
  ```bash
  redis-cli -h <host> -a <password> SET app:dynamic_settings '...JSON...'
  ```
- 为生产环境生成内部密钥：
  ```bash
  openssl rand -hex 32
  ```
  写入 `.env.prod`：`INTERNAL_API_SECRET=<上一步输出>`。
- 若需要多环境，分别写入 `.env.dev`、`.env.staging` 并同步 Redis。
- 为 Redis 开启 AOF everysec 或 RDB+AOF，并配置备份/监控。

**验收**：Redis 键存在，读取内容与默认参数匹配；所有节点 `.env*` 已包含 `INTERNAL_API_SECRET`；Redis 持久化策略可用。

---

## 阶段 2 —— 实现 DynamicSettingsService

**目标**：封装动态参数读取/写入逻辑，使业务代码透明地获得合并结果。

**操作步骤**
- 在 `backend/app/services/`（或模块内合适位置）新建 `dynamic_settings.py`：
  ```python
  class DynamicSettingsService:
      def __init__(self, redis_client, settings: Settings):
          self.redis = redis_client
          self.defaults = settings.dynamic_settings_defaults()

      async def get_all(self) -> dict:
          merged = dict(self.defaults)
          raw = await self.redis.get("app:dynamic_settings")
          if raw:
              merged.update(json.loads(raw))
          return merged

      async def update(self, payload: dict) -> dict:
          merged = await self.get_all()
          merged.update(payload)
          await self.redis.set("app:dynamic_settings", json.dumps(merged))
          return merged
  ```
- 在 `Settings` 中新增 `dynamic_settings_defaults()`（或等效方法），只返回可调参数默认值。
- 在 FastAPI 依赖中提供 `get_dynamic_settings_service()`，注入 Redis client 与 `settings`。
- 修改使用参数的模块（如 `app/modules/knowledge_base/service.py`）改为依赖服务：
  ```python
  settings = await dynamic_settings_service.get_all()
  top_k = settings["RAG_TOP_K"]
  ```
- 处理 Redis 故障：捕获异常后记录日志并回退默认值。

**验收**：相关模块不再直接读取环境变量；Redis 缺失/异常时业务继续可用；pytest 添加覆盖：命中/未命中 Redis、更新失败时回退。

---

## 阶段 3 —— 管理 API 与安全依赖

**目标**：提供受保护的管理端接口，实现参数读取与更新。

**操作步骤**
- 在 `backend/app/api/v1/routes/` 新建 `admin_settings.py`：
  ```python
  router = APIRouter(prefix="/api/v1/admin/settings", tags=["admin-settings"],
                     dependencies=[Depends(verify_internal_access)])
  ```
- 定义 Pydantic schema：
  - `AdminSettingsResponse`：包含默认值、当前值、最后更新时间。
  - `AdminSettingsUpdate`：允许部分字段更新，包含范围校验。
- 实现两个端点：
  - `GET /`：返回当前/默认参数、更新时间、Redis 状态。
  - `PUT /`：校验请求体 → 调用 `DynamicSettingsService.update()` → 记录审计。
- 在 `backend/app/api/dependencies.py`（或新建）实现 `verify_internal_access`：
  ```python
  async def verify_internal_access(
      x_internal_secret: str | None = Header(alias="X-Internal-Secret"),
      settings: Settings = Depends(get_settings),
  ) -> None:
      if not x_internal_secret or x_internal_secret != settings.INTERNAL_API_SECRET:
          raise HTTPException(status_code=403, detail="Internal access required")
  ```
- 将新 router 注册到主应用：`app/main.py` 或根 router 中引入。
- 为审计准备事件记录（数据库表或日志）。

**验收**：本地运行 `poetry run pytest app/tests/admin/test_settings.py` 通过；非 admin 请求得到 403；更新接口能正确刷新 Redis；审计记录生效。

---

## 阶段 4 —— 超级管理员前端

**目标**：在 `admin.my-domain.com` 渲染专属界面，提供参数展示与编辑。

**操作步骤**
- 在 `frontend/src/pages/` 新建 `AdminSettingsPage.tsx`，使用 `fetch`/`axios` 调用前述 API。
- 在路由配置中按域名条件加载：
  ```ts
  const isAdminHost = window.location.hostname === "admin.my-domain.com";
  ```
  仅在 `isAdminHost` 为真时注册 `/settings` 等超级管理员路由。
- 页面应显示：参数名称、当前值、默认值、最后一次修改时间/账号、提交按钮；支持重置为默认值。
- 在 `VITE_API_URL` 设置中为 admin 域配置单独的 `.env` 条目（例如 `.env.admin`）。
- 为能力不足的参数展示 `readonly` 状态，避免误操作。

**验收**：`npm run lint`、`npm run build` 通过；`admin.my-domain.com` 可成功读取/更新参数；非 admin 域访问管理路由时不渲染页面。

---

## 阶段 5 —— Nginx 与 oauth2_proxy 配置

**目标**：确保只有通过 `oauth2_proxy` 验证的请求，且来源于 `admin` 域，才能携带内部密钥访问后端。

**操作步骤**
- **主域 `my-domain.com`**：
  ```nginx
  location ^~ /api/v1/admin/ {
      return 404;
  }

  location ^~ /api/ {
      proxy_set_header X-Internal-Secret "";
      proxy_pass http://backend;
  }
  ```
- **管理域 `admin.my-domain.com`**：
  ```nginx
  location / {
      auth_request /oauth2/auth;
      proxy_pass http://admin_frontend;
  }

  location /api/ {
      auth_request /oauth2/auth;
      error_page 401 = @oauth2_signin;
      proxy_set_header X-Internal-Secret $internal_api_secret;
      proxy_pass http://backend;
  }

  location @oauth2_signin {
      return 302 https://auth.my-domain.com/oauth2/start?rd=$scheme://$host$request_uri;
  }
  ```
- 在 Nginx `env` 或模板中注入 `$internal_api_secret`，值来源于 `.env.prod`。
- 配置 `oauth2_proxy`：仅允许你的邮箱/组，启用 `cookie_secure true`、`cookie_refresh 1h`、`cookie_expire 12h`、`set_xauthrequest true`。
- 部署后重载 Nginx 并验证证书、重定向流程、Header 注入。

**验收**：
- 未登录访问 `admin.my-domain.com` 自动跳转认证。
- 认证通过后请求头包含正确的 `X-Internal-Secret`。
- 从 `my-domain.com` 直接请求 `/api/v1/admin/settings` 返回 404。

---

## 阶段 6 —— 审计、回滚与降级

**目标**：保证历史可追踪、异常可恢复。

**操作步骤**
- 在后端 `update` 接口中记录审计（数据库表或日志服务）：时间、修改人、变更字段、旧值/新值。
- 建立 Redis 变更快照：每次写入前将旧值存储到 `app:dynamic_settings:history`（list 或 stream）。
- 在前端提供“恢复默认值/上一版本”按钮，触发后端恢复逻辑。
- 发生 Redis 故障时，后端自动回退默认值并通过监控告警。
- 在 CI/CD 中添加 Smoke Test（读取设置、更新设置后校验）。

**验收**：审计记录可查询；执行回滚命令能恢复到上一版本；Redis 故障演练时后端返回默认值并发出告警。

---

## 阶段 7 —— 验证、发布与监控

**目标**：端到端验证后平稳上线。

**操作步骤**
- 在测试环境按以上步骤全部部署，执行以下验证脚本：
  ```bash
  # 1. 未登录访问（应 302）
  curl -I https://admin.my-domain.com/api/v1/admin/settings

  # 2. 登录后访问（应 200，手动或使用存储的 Cookie）
  # 3. 主域访问（应 404/403）
  curl -I https://my-domain.com/api/v1/admin/settings
  ```
- 在测试环境更新参数，确认业务功能即时生效（无需重启）。
- 准备发布 Runbook：包括变更步骤、回滚步骤、联系人。
- 生产环境部署：
  1. 发布后端
  2. 发布前端
  3. 应用 Nginx/`oauth2_proxy` 配置
  4. 验证三条访问路径
- 上线后 24 小时内重点监控：Redis 命中率、Nginx 401/403、后端错误日志。

**验收**：测试/生产验证脚本通过；Runbook 与回滚方案归档；监控无异常。

---

## 附录 A —— 关键文件与目录

- `backend/app/core/config.py`：`Settings`、默认值、`INTERNAL_API_SECRET`
- `backend/app/services/dynamic_settings.py`：动态配置服务
- `backend/app/api/v1/routes/admin_settings.py`：管理 API 路由
- `backend/app/dependencies/security.py`：`verify_internal_access`
- `frontend/src/pages/AdminSettingsPage.tsx`：超级管理员界面
- `docker-compose.prod.yml` / Nginx 模板：网关与代理配置
- `.env*`：密钥与内部访问密钥

---

## 附录 B —— 发布前检查清单

- [ ] Redis 键 `app:dynamic_settings` 与默认值一致
- [ ] `.env*` 已包含最新 `INTERNAL_API_SECRET`
- [ ] FastAPI 动态参数所有读取路径均使用服务
- [ ] 管理 API 覆盖率与自动化测试通过
- [ ] 管理前端构建结果已部署，域名指向正确
- [ ] Nginx/`oauth2_proxy` 配置加载并已验证 Header 注入
- [ ] 审计/回滚逻辑手动演练成功
- [ ] 上线 Runbook 与回滚预案已归档并告知团队

完成以上步骤，即可在保持密钥安全的前提下，实现超级管理员独享的动态参数管理能力，并确保系统具备观察、回滚与降级的全链路保障。
