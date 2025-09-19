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

**目标**：明确现有配置来源与归属，确保环境切换、参数拆分与后续回滚均有依据。

**操作步骤**
- 为 `.env.example`、`.env.prod.example`、`docker-compose*.yml`、Nginx 与 `oauth2_proxy` 模板制作时间戳备份：
  ```bash
  cp .env.prod .env.prod.bak_$(date +%Y%m%d)
  cp docker-compose.prod.yml docker-compose.prod.yml.bak_$(date +%Y%m%d)
  ```
- 在根目录整理《Step0.md》，对比 `.env.dev` 快照、`local_script/env_backup` 与 Compose 文件，标注 **静态密钥**、**可调参数**、**暂未使用** 三类；此清单即后续 Redis 动态配置的权威来源。
- 统一收敛环境读取逻辑：`backend/app/core/config.py` 中通过 `get_env_file()` 自动选择 `.env.dev`/`.env.prod`，并使用 Pydantic Settings 子配置（`PostgresSettings`、`SecuritySettings` 等）集中定义所有环境变量。
- 在 `Settings` 聚合类中保留所有静态字段，并为动态参数预留 `dynamic_settings_defaults()` 映射，后续阶段将按此输出作为 Redis 兜底值。
- 与 DevOps/运维确认 Redis、Nginx、`oauth2_proxy`、证书与自建模型等依赖资源状态，形成实施清单（Issue/Jira）并获团队确认。

**验收**：`Step0.md` 已完整列出静态/动态变量；`backend/app/core/config.py` 可在不同环境正确加载配置并提供默认动态参数；核心配置文件存在最新备份且实施清单经团队评审。

---

## 阶段 1 —— 配置分层与 Redis 初始化 ✅（已完成）

**目标**：保留密钥型配置在环境变量中，把可调参数迁移到 Redis，并对键空间与持久化策略做好约束。

**操作步骤**
- `.env*` 继续托管数据库、JWT、第三方 API Key 等静态密钥，动态参数只保留默认值，真实覆盖写入 Redis。
- 在 `backend/app/infrastructure/redis/keyspace.py` 中新增 `redis_keys.app.dynamic_settings()` / `dynamic_settings_metadata()`，统一生成 `app:dynamic_settings` 与 `app:dynamic_settings:meta` 键名，避免业务代码硬编码。
- 以 `Settings.dynamic_settings_defaults()` 的输出为模板准备 JSON 文档，并手动灌入 Redis：
  ```bash
  redis-cli -h <host> -a <password> SET $(python -c "from app.infrastructure.redis.keyspace import redis_keys;print(redis_keys.app.dynamic_settings())") '<JSON>'
  ```
- 生产环境生成内部调用密钥：
  ```bash
  openssl rand -hex 32
  ```
  写入 `.env.prod` / `.env.example` / `.env.prod.example` 的 `INTERNAL_API_SECRET` 字段，并在部署清单中同步到运行节点。
- 检查 Redis 配置：启用 `appendonly yes` (everysec) 或 RDB+AOF 混合持久化，补充备份策略与监控告警。

**验收**：Redis 中 `app:dynamic_settings`、`app:dynamic_settings:meta` 均存在且与默认值一致；`.env*` 文件包含 `INTERNAL_API_SECRET`；Redis 持久化策略与备份落地。

---

## 阶段 2 —— 实现 DynamicSettingsService ✅（已完成）

**目标**：将 Redis 动态配置封装为可复用服务，确保读取、更新、容错与元数据记录均可统一处理。

**操作步骤**
- 在 `backend/app/infrastructure/dynamic_settings/service.py` 实现 `DynamicSettingsService`：
  - 构造函数接受 `RedisBase` 与 `Settings`，默认使用 `redis_keys.app.dynamic_settings()`、`dynamic_settings_metadata()` 作为键名。
  - `defaults()` 返回 `settings.dynamic_settings_defaults()` 的副本；`get_all()` 先调用 `RedisBase.ensure_connection()`，若 Redis 异常或载荷类型错误则记录日志并返回默认值；成功时将 Redis 覆盖层叠加到默认值。
  - `get_overrides()` 与 `get_metadata()` 分别返回原始覆盖值和最近更新时间等元数据；异常时抛出或返回空字典以供上层判断。
  - `update()` 校验入参为 `dict`，基于最新合并结果打补丁，调用 `RedisBase.set_json()` 写入主键，并在 `:meta` 键记录 `updated_at` 与 `updated_fields`。
- 通过 `@lru_cache` 的 `_build_dynamic_settings_service()` + `get_dynamic_settings_service()` 提供 FastAPI 依赖，保证应用内共享单例并自动复用 Redis 连接池。
- `Settings.dynamic_settings_defaults()` 返回的字段范围仅包含可调参数，便于服务按需覆盖。
- 在业务代码中接入服务：`backend/app/modules/knowledge_base/service.py` 通过 `_resolve_dynamic_settings()` 异步获取配置，失败时回退静态默认值，并对类型做防御性校验。
- 为 WebSocket、REST 等入口统一注入依赖：如 `backend/app/api/v1/endpoints/knowledge.py`、`llm_ws.py` 使用 `Depends(get_dynamic_settings_service)`，确保所有读取路径走服务层。

**验收**：所有动态参数读取均改为通过 `DynamicSettingsService`；Redis 故障或返回非 JSON 对象时业务自动兜底；`backend/app/tests/infrastructure/test_dynamic_settings_service.py` 覆盖加载/写入/容错逻辑并全部通过。

---

## 阶段 3 —— 管理 API 与安全依赖 ✅（已完成）

**目标**：提供仅供内部调用的管理端接口，实现动态参数查询、更新及安全校验。

**操作步骤**
- 在 `backend/app/api/v1/endpoints/admin_settings.py` 建立新路由：`APIRouter(prefix="/admin/settings", tags=["admin-settings"], dependencies=[Depends(verify_internal_access)])`，最终对外路径为 `/api/v1/admin/settings`。
- 复用 `backend/app/api/dependencies.py` 中新增的 `verify_internal_access`：校验 `X-Internal-Secret` 请求头是否与 `settings.INTERNAL_API_SECRET` 匹配，并在未配置密钥时直接拒绝请求。
- 使用 `backend/app/modules/admin_settings/schemas.py` 定义契约：
  - `AdminSettingsResponse` 返回 `defaults`、`overrides`、`effective`、`updated_at` 与 `redis_status`；
  - `AdminSettingsUpdate` 允许对 RAG 参数进行部分更新并内建上下界校验（`extra="forbid"`）。
- 在 `backend/app/modules/admin_settings/service.py` 编排业务：`read_settings()` 合并默认值、Redis 覆盖与元数据，并在 Redis 不可用时回退；`update_settings()` 校验请求体、调用 `DynamicSettingsService.update()`、再读取覆盖/元数据并返回响应。
- 通过 `admin_settings_service` 组合路由处理：
  - `GET /` 调用 `read_settings()` 返回当前状态；
  - `PUT /` 调用 `update_settings()`，自动记录最近更新字段与时间戳。
- 将新路由加入 `backend/app/api/v1/router.py` 并随主应用 `app/main.py` 的 `/api` 根路径挂载，使所有入口统一经过认证中间件和日志链路。
- 为后续审计扩展保留钩子：`AdminSettingsService` 会在 Redis 元数据中写入 `updated_at` 与 `updated_fields`，便于追加数据库/日志审计。

**验收**：运行 `poetry run pytest backend/app/tests/api/test_admin_settings.py` 全部通过；省略 `X-Internal-Secret` 或密钥错误时返回 403；成功更新后 Redis 中的 `app:dynamic_settings`、`:meta` 字段刷新并可通过 `GET` 查询到最新值。

---

## 阶段 4 —— 超级管理员前端

**目标**：在 `admin` 子域渲染专属前端，展示/编辑动态参数并避免在代码中硬编码域名。

**操作步骤**
- 先在环境文件中声明管理员子域：向 `.env.example`、`.env.prod`、`.env.prod.example` 添加 `SUBDOMAIN_ADMIN=admin`，并为前端构建提供镜像变量（如 `frontend/.env.admin` 或 `frontend/.env.production` 中写入 `VITE_DOMAIN_MAIN=${DOMAIN_MAIN}`、`VITE_SUBDOMAIN_ADMIN=${SUBDOMAIN_ADMIN}`）。
- 在 `frontend/src/pages/` 新建 `AdminSettingsPage.tsx`：
  - 页面读取 `/api/v1/admin/settings`，展示默认值、当前值、最后更新时间及 Redis 状态。
  - 表单提交时向 `PUT /api/v1/admin/settings` 发送补丁请求，并在成功后刷新列表。
  - 对无权/未登录状态给出提示，必要时提供“恢复默认值”按钮。
- 在路由层根据运行域名决定是否注入页面：
  ```ts
  const adminHost = `${import.meta.env.VITE_SUBDOMAIN_ADMIN}.${import.meta.env.VITE_DOMAIN_MAIN}`;
  const isAdminHost = window.location.hostname === adminHost;
  ```
  仅当 `isAdminHost` 为真时才注册诸如 `/settings`、`/settings/history` 的超级管理员路由，其余环境不加载相关代码。
- 若使用 Zustand/React Query 等状态管理，请在 `frontend/src/services` 新增专用请求封装，自动附带 `X-Internal-Secret`（由 `oauth2_proxy` + Nginx 注入）并处理 403/500。
- 在 `frontend/src/routes.tsx` 或集中路由模块中插入懒加载路由（`React.lazy` + `Suspense`），确保非 admin 域不会打包多余代码。
- 更新文档/README，说明如何在本地通过 hosts + `VITE_SUBDOMAIN_ADMIN` 预览管理员页面。

**验收**：`npm run lint`、`npm run build`、`npm run test` 均通过；部署到 `admin.<DOMAIN_MAIN>` 后可读取并更新设置；在主域或其它子域访问时不会渲染管理员路由。

---

## 阶段 5 —— Nginx 与 oauth2_proxy 配置

**目标**：确保仅来自 `admin` 子域、通过 `oauth2_proxy` 校验的请求才能注入内部密钥访问后端，其他入口一律拒绝。

**操作步骤**
- 变量透传：
  - 在 `docker-compose.prod.yml` 的 `nginx`、`oauth2_proxy` 服务下补充 `SUBDOMAIN_ADMIN` 环境变量，确保容器内可读取；必要时将 `INTERNAL_API_SECRET` 通过 `env_file` 暴露给 Nginx。
  - 更新 `nginx/entrypoint.sh`，把 `SUBDOMAIN_ADMIN` 加入 `required_vars` 与 `VARS_TO_SUBSTITUTE`，生成模板时自动替换。
- 主域限制：在 `nginx/conf/prod/common-locations-prod.conf.template` 增加保护段：
  ```nginx
  location ^~ /api/v1/admin/ {
      return 404;
  }

  location /api/ {
      proxy_set_header X-Internal-Secret "";
      # 其他已有代理指令保持不变
  }
  ```
  确保主域所有转发都会显式清空 `X-Internal-Secret`。
- 管理域模板：新增 `nginx/conf/prod/admin.conf.template`（或等效文件），并在 `nginx/nginx.prod.conf.template` 中 `include` 该模板。示例：
  ```nginx
  server {
      listen 443 ssl;
      server_name ${SUBDOMAIN_ADMIN}.${DOMAIN_MAIN};
      ssl_certificate /etc/nginx/ssl/server.pem;
      ssl_certificate_key /etc/nginx/ssl/server.key;

      set $internal_api_secret "${INTERNAL_API_SECRET}";

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
          return 302 https://auth.${DOMAIN_MAIN}/oauth2/start?rd=$scheme://$host$request_uri;
      }
  }
  ```
- oauth2_proxy 互锁：
  - `docker-compose.prod.yml` 中确认 `oauth2_proxy` 暴露 `OAUTH2_PROXY_COOKIE_DOMAINS=.${DOMAIN_MAIN}`、`OAUTH2_PROXY_WHITELIST_DOMAINS=.${DOMAIN_MAIN}`，并允许 `rd=https://admin.${DOMAIN_MAIN}`。
  - 校验 `OAUTH2_PROXY_UPSTREAMS` 指向 `static://200`（仅做鉴权），并在 `nginx/conf/prod/auth.conf.template` 中保留健康检查回源。
- 部署校验：渲染模板后执行 `docker compose -f docker-compose.prod.yml exec nginx nginx -t`，再使用 `curl -I https://admin.${DOMAIN_MAIN}/api/v1/admin/settings` 等命令验证 302/200/404 流程。

**验收**：
- `${DOMAIN_MAIN}`（主域）请求 `/api/v1/admin/settings` 返回 404 且 Header 中无 `X-Internal-Secret`。
- `admin.${DOMAIN_MAIN}` 未登录访问被 302 重定向至 `oauth2_proxy`，登录后能够携带正确的 `X-Internal-Secret` 访问后端。
- Nginx 日志中可以看到 `admin` 与主域访问路径分离，`oauth2_proxy` 健康检查通过。

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
- `backend/app/infrastructure/dynamic_settings/service.py`：动态配置服务实现
- `backend/app/modules/admin_settings/`：Schema 与业务层
- `backend/app/api/v1/endpoints/admin_settings.py`：管理 API 路由
- `backend/app/api/dependencies.py`：`verify_internal_access`
- `backend/app/api/v1/endpoints/knowledge.py` / `llm_ws.py`：示例依赖注入
- `frontend/src/pages/AdminSettingsPage.tsx`、`frontend/src/routes.tsx`：超级管理员界面与路由开关
- `docker-compose.prod.yml`、`nginx/entrypoint.sh`、`nginx/conf/prod/*.template`：网关与代理配置
- `.env*`、`frontend/.env.*`：密钥、子域与前端构建变量

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
