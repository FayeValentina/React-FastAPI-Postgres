# React-FastAPI-Postgres

Full-stack web application featuring a **FastAPI** backend and a **React** (Vite + TypeScript) frontend.

### Architecture Highlights
- **JWT authentication** secures API endpoints and can be paired with **oauth2-proxy** for single sign-on.
- **Redis caching** accelerates reads and, together with **RabbitMQ**, powers **TaskIQ** background jobs.
- **PostgreSQL** stores persistent data.
- **Nginx** reverse proxy routes requests between services.

Docker Compose files are provided for both development and production environments.

## Project Structure

```
.
├── backend/                # FastAPI application, TaskIQ workers & scheduler
├── frontend/               # React client built with Vite
├── nginx/                  # Nginx templates and startup scripts
├── docker-compose.dev.yml  # Development stack with hot reload
├── docker-compose.prod.yml # Production stack with static build
└── README.md
```

## Development with Docker

1. Copy the example environment file:
   ```bash
   cp .env.example .env.dev
   ```
2. Start the development stack:
   ```bash
   docker compose -f docker-compose.dev.yml up --build
   ```
3. Access the services:
   - Frontend: <http://localhost>
   - API docs: <http://localhost/api/docs>
   - pgAdmin, RedisInsight and Portainer are also available in the dev stack.

## Production Deployment

1. Prepare production variables:
   ```bash
   cp .env.prod.example .env.prod
   ```
2. Build and run:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```
The production compose file builds the frontend, runs the FastAPI application, TaskIQ worker and scheduler,
PostgreSQL, RabbitMQ and Redis behind an Nginx reverse proxy with optional `oauth2-proxy` for web SSO.

## Local Development Without Docker

### Backend
```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Testing
```bash
cd backend && poetry run pytest
cd frontend && npm test
```

## Defining Tasks & Parameters

This project exposes a single global task registry that auto-discovers workers and provides a typed description of each task to the frontend. Use typing metadata to make task parameters self-descriptive and renderable.

- Registry: `backend/app/infrastructure/tasks/task_registry_decorators.py`
- Workers: `backend/app/modules/tasks/workers/*`
- Introspection: `GET /api/v1/tasks/system/task-info`

### Core Rules
- Use `@task("TASK_NAME", queue="…")` to register a task. Pair with TaskIQ's `@broker.task` as needed.
- Define parameters with Python types and `typing.Annotated` to attach UI metadata.
- Hide internal params from the UI:
  - `config_id`: `Annotated[Optional[int], {"exclude_from_ui": True}] = None`
  - `context`: `Annotated[Context, {"exclude_from_ui": True}] = TaskiqDepends()`
- Enum-like values: prefer `Literal[...]` (or Python `Enum`). The registry auto-sets `ui_hint='select'` and supplies `choices`.
- Complex structures (`dict`, `list`, nested types): annotate `{"ui_hint": "json"}` to render a JSON editor.
- Numbers: use `int`/`float` and optionally set `min`/`max`/`step` in UI meta.
- Email: either set `{"ui_hint": "email"}` or rely on name heuristic (`...email`).

Supported UI meta keys inside `Annotated[..., {…}]`:
- `exclude_from_ui`: boolean
- `ui_hint`: `select` | `number` | `text` | `email` | `boolean` | `json` | `password` | `textarea`
- `choices`: list of values (used with `select`)
- `example`: example value (e.g., JSON structure hint for dict/list)
- Optional refinements: `label`, `description`, `placeholder`, `min`, `max`, `step`, `pattern`

Type metadata returned by the API is `type_info` with `type` and nested `args` (no `raw`). Frontend primarily uses `parameters[].ui` to render.

### Examples

1) Export data with format select and JSON date range
```python
from typing import Annotated, Optional, Dict
from taskiq import Context, TaskiqDepends

@task("DATA_EXPORT", queue="default")
@broker.task(task_name="export_data", queue="default", retry_on_error=True, max_retries=3)
@execution_handler
async def export_data(
    config_id: Annotated[Optional[int], {"exclude_from_ui": True}] = None,
    export_format: Annotated[str, {"ui_hint": "select", "choices": ["json", "csv", "excel"]}] = "json",
    date_range: Annotated[Optional[Dict[str, str]], {"ui_hint": "json"}] = None,
    context: Annotated[Context, {"exclude_from_ui": True}] = TaskiqDepends(),
):
    ...
```

2) Backup type using Literal choices
```python
from typing import Annotated, Optional, Literal

@task("DATA_BACKUP", queue="default")
@broker.task(task_name="backup_data", queue="default", retry_on_error=True, max_retries=3)
@execution_handler
async def backup_data(
    config_id: Annotated[Optional[int], {"exclude_from_ui": True}] = None,
    backup_type: Annotated[Literal["full", "incremental"], {"ui_hint": "select"}] = "full",
    context: Annotated[Context, {"exclude_from_ui": True}] = TaskiqDepends(),
):
    ...
```

3) Cleanup tasks with numeric constraints
```python
from typing import Annotated, Optional

@task("CLEANUP_TOKENS", queue="cleanup")
@broker.task(task_name="cleanup_expired_tokens", queue="cleanup", retry_on_error=True, max_retries=3)
@execution_handler
async def cleanup_expired_tokens(
    config_id: Annotated[Optional[int], {"exclude_from_ui": True}] = None,
    days_old: Annotated[int, {"ui_hint": "number", "min": 1}] = 7,
    context: Annotated[Context, {"exclude_from_ui": True}] = TaskiqDepends(),
):
    ...
```

4) Email task with required fields
```python
from typing import Annotated, Optional

@task("SEND_EMAIL", queue="default")
@broker.task(task_name="send_email", queue="default", retry_on_error=True, max_retries=3)
@execution_handler
async def send_email(
    to_email: Annotated[str, {"ui_hint": "email"}],
    subject: str,
    config_id: Annotated[Optional[int], {"exclude_from_ui": True}] = None,
    context: Annotated[Context, {"exclude_from_ui": True}] = TaskiqDepends(),
):
    ...
```

### Auto-Discovery & Introspection
- Auto-discovery runs at startup: `app.main:lifespan` calls `auto_discover_tasks()`.
- Inspect tasks and parameters at runtime: `GET /api/v1/tasks/system/task-info`.
- Each parameter includes:
  - `name`, `type`, `type_info` (structured), `default`, `required`, `kind`, `ui`.

With these conventions, the frontend can render dynamic parameter forms reliably from the backend as the single source of truth.
