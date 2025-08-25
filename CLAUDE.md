# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Docker Development (Primary)
- `docker compose -f docker-compose.dev.yml up --build` - Start development environment
- `docker compose -f docker-compose.dev.yml up` - Start dev services (uses cache)
- `docker compose -f docker-compose.dev.yml down` - Stop dev services  
- `docker compose -f docker-compose.prod.yml up --build` - Start production environment
- `docker compose -f docker-compose.dev.yml logs backend` - View backend logs
- `docker compose -f docker-compose.dev.yml logs frontend` - View frontend logs
- `docker compose -f docker-compose.dev.yml logs taskiq_scheduler` - View TaskIQ scheduler logs
- `docker compose -f docker-compose.dev.yml logs taskiq_worker` - View TaskIQ worker logs

### Frontend (React + Vite + TypeScript)
- `cd frontend && npm run dev` - Start development server
- `cd frontend && npm run build` - Build for production
- `cd frontend && npm run lint` - Run ESLint

### Backend (FastAPI + Poetry)
- `cd backend && poetry run uvicorn app.main:app --reload` - Start development server
- `cd backend && poetry run alembic upgrade head` - Apply database migrations
- `cd backend && poetry run alembic revision --autogenerate -m "description"` - Create new migration

### Database Management
- Access PgAdmin at http://localhost:5050 (credentials from .env)
- PostgreSQL accessible at localhost:5433 (from host) or postgres:5432 (from containers)
- **Note**: Database migrations are handled automatically on Docker startup

### Task Queue Management
- Redis accessible at localhost:6379 (message broker and result backend)
- RabbitMQ accessible at localhost:5672 (alternative message broker)
- RabbitMQ Management UI at http://localhost:15672 (guest/guest)
- TaskIQ scheduler runs scheduled tasks automatically
- TaskIQ workers process background tasks

## Architecture Overview

### Project Structure
```
backend/                    # FastAPI backend
├── app/
│   ├── api/v1/            # API routes (auth, users, tasks, reddit_content)
│   │   └── routes/        # Route modules (auth_routes, user_routes, task_routes, reddit_content_routes)
│   ├── constant/          # Application constants
│   ├── core/              # Core configurations and components
│   │   ├── redis/         # Redis connection management (base, config, pool)
│   │   └── tasks/         # Task system registry and decorators
│   ├── crud/              # Database operations (user, password_reset, task_config, task_execution, reddit_content)
│   ├── db/                # Database connection and base classes
│   ├── dependencies/      # Dependency injection (current_user, request_context)
│   ├── middleware/        # Auth and logging middleware
│   ├── models/            # SQLAlchemy models (user, password_reset, task_config, task_execution, reddit_content)
│   ├── schemas/           # Pydantic schemas modularized by functionality:
│   │   ├── auth.py        # Authentication schemas
│   │   ├── user.py        # User management schemas
│   │   ├── task_config_schemas.py      # Task configuration schemas
│   │   ├── task_schedules_schemas.py   # Schedule management schemas
│   │   ├── task_executions_schemas.py  # Execution management schemas
│   │   ├── task_system_schemas.py      # System monitoring schemas
│   │   └── reddit_content.py           # Reddit content schemas
│   ├── services/          # Business logic services
│   │   ├── email_service.py            # Email service
│   │   ├── reddit_scraper_service.py   # Reddit scraping service
│   │   └── redis/         # Redis-based services
│   │       ├── auth.py                 # Authentication Redis service
│   │       ├── cache.py                # Caching Redis service
│   │       ├── history.py              # Enhanced schedule history service (state + history + metadata)
│   │       ├── scheduler_core.py       # Core TaskIQ scheduler service
│   │       └── scheduler.py            # Unified scheduler service (combines core + history)
│   ├── tasks/             # TaskIQ background tasks (cleanup, notification, data tasks)
│   ├── tests/             # Test files
│   └── utils/             # Common utilities (common)
├── alembic/               # Database migrations
├── broker.py              # TaskIQ broker configuration
├── scheduler.py           # TaskIQ scheduler configuration
└── pyproject.toml         # Poetry dependencies

frontend/                  # React frontend
├── src/
│   ├── components/        # React components (Layout, ProtectedRoute, TokenExpiryDialog, Scraper components)
│   ├── pages/             # Page components (Login, Register, Dashboard, Profile, ForgotPassword, ResetPassword, TaskManagementPage, SystemMonitoringPage, DemoPage, UserPage)
│   ├── services/          # API client (axios, authManager, uiManager, interceptors)
│   ├── stores/            # Zustand stores (auth-store, api-store, ui-store)
│   ├── types/             # TypeScript types (auth, user, bot, session, api)
│   └── utils/             # Utility functions (errorHandler)
└── package.json           # npm dependencies
```

### Backend Architecture
- **FastAPI** with async/await support using asyncpg for PostgreSQL
- **JWT Authentication** with access and refresh tokens (dual-token system)
- **Refactored TaskIQ Task System** (v2.4) with optimized Redis architecture:
  - **Eliminated double Redis connections** and functional overlap
  - **Separated concerns**: PostgreSQL for static configuration, Redis for dynamic scheduling state
  - **Unified services**: Combined scheduler core + enhanced history service
  - **Simplified execution status**: Boolean `is_success` instead of complex status enums
- **Reddit Scraping System** with bot configuration and session management
- **Middleware Stack** (order matters):
  1. AuthMiddleware - JWT validation (excludes auth endpoints)
  2. CORSMiddleware - Cross-origin requests
  3. RequestResponseLoggingMiddleware - Request/response logging
- **Configuration** using Pydantic Settings with nested configs (postgres, security, cors, redis, etc.)
- **Database**: SQLAlchemy 2.0 with automatic Alembic migrations
- **Logging**: Loguru for structured logging
- **Background Tasks**: TaskIQ 0.11.x with optimized Redis connection management

### Infrastructure Architecture

#### Environment Separation (Dev/Prod)
**Docker Architecture:**
- **Development Environment**: 
  - Hot-reload enabled containers with volume mounts
  - Full dependency installation for debugging
  - Real-time development server (uvicorn --reload)
- **Production Environment**:
  - Multi-stage builds for optimized images
  - Security-hardened containers (non-root user)
  - Production-only dependencies (`poetry install --only main`)
  - Gunicorn WSGI server with UvicornWorker

**Nginx Reverse Proxy:**
- **Development Configuration**:
  - Proxy mode to frontend development server (port 3000)
  - WebSocket support for hot module replacement
  - No caching for real-time updates
  - Basic security headers
- **Production Configuration**:
  - Direct static file serving from nginx
  - SSL/TLS termination with HTTP to HTTPS redirect
  - Advanced security headers (CSP, HSTS, XSS Protection)
  - Rate limiting (API: 10r/s, Auth: 5r/m)
  - Long-term caching for static assets (1 year + immutable)
  - Gzip compression optimized

#### Frontend Build Strategy
- **Development**: Live development server with volume-protected node_modules
- **Production**: Dedicated builder container → Static file extraction → Nginx serving

#### Service Architecture
```
Production Flow:
Internet → Nginx (SSL + Static Files) → Backend API → Database/Redis/RabbitMQ

Development Flow:
Internet → Nginx → Frontend Container (Hot Reload) → Backend Container → Database/Redis/RabbitMQ
```

#### Container Resource Management
- **Production**: Memory limits and health checks for all services
- **Development**: Unlimited resources for debugging flexibility
- **Networking**: Dedicated networks (prodNetWork/dbNetWork) with service isolation

### API Endpoints
**Authentication** (`/api/v1/auth`)
- `POST /auth/login` - User login (username/email + password)
- `POST /auth/refresh` - Refresh access token
- `POST /auth/revoke` - Revoke refresh token
- `POST /auth/logout` - Logout (revoke all tokens)
- `POST /auth/register` - User registration
- `GET /auth/me` - Get current user info
- `POST /auth/forgot-password` - Send password reset email
- `POST /auth/verify-reset-token?token=xxx` - Verify password reset token
- `POST /auth/reset-password` - Reset password with token

**User Management** (`/api/v1/users`)
- `POST /users` - Create user (admin only)
- `GET /users` - Get user list (with filtering/sorting)
- `GET /users/{user_id}` - Get specific user
- `PATCH /users/{user_id}` - Update user (unified endpoint for partial updates)
- `DELETE /users/{user_id}` - Delete user (admin only)

**Reddit Content Management** (`/api/v1/reddit`)
- `GET /reddit/posts` - Get Reddit posts with filtering and pagination
- `GET /reddit/posts/{post_id}` - Get specific Reddit post details
- `GET /reddit/posts/{post_id}/comments` - Get comments for specific post
- `GET /reddit/comments` - Get Reddit comments with filtering
- `GET /reddit/comments/{comment_id}` - Get specific comment details
- `DELETE /reddit/posts/{post_id}` - Delete specific Reddit post
- `DELETE /reddit/comments/{comment_id}` - Delete specific Reddit comment

**Task Management** (`/api/v1/tasks`) - **Refactored Architecture v2.4** (25 endpoints with modular schemas)
- **Configuration Management** (5 endpoints):
  - `GET /tasks/configs` - List task configurations (with filtering/pagination)
  - `POST /tasks/configs` - Create new task configuration
  - `GET /tasks/configs/{config_id}` - Get specific task configuration
  - `PUT /tasks/configs/{config_id}` - Update task configuration
  - `DELETE /tasks/configs/{config_id}` - Delete task configuration
- **Schedule Management** (7 endpoints):
  - `POST /tasks/schedules/{config_id}/{action}` - Start/stop/pause/resume scheduled tasks
  - `GET /tasks/schedules` - Get all scheduled jobs
  - `GET /tasks/schedules/{config_id}` - Get specific schedule status
  - `GET /tasks/schedules/{config_id}/history` - Get schedule history
  - `DELETE /tasks/schedules/{config_id}` - Stop and remove schedule
  - `POST /tasks/schedules/batch/{action}` - Batch schedule operations
  - `GET /tasks/schedules/summary` - Get scheduler status summary
- **Execution Management** (6 endpoints):
  - `GET /tasks/executions/by-config/{config_id}` - Get executions for specific config
  - `GET /tasks/executions/recent` - Get recent execution records
  - `GET /tasks/executions/failed` - Get failed execution records
  - `GET /tasks/executions/{config_id}/stats` - Get execution statistics
  - `GET /tasks/executions/{execution_id}` - Get specific execution details
  - `DELETE /tasks/executions/cleanup` - Clean up old execution records
- **Immediate Execution** (3 endpoints):
  - `POST /tasks/execute/{config_id}` - Execute specific config immediately
  - `POST /tasks/execute/by-type/{task_type}` - Execute by task type
  - `POST /tasks/execute/batch` - Batch execute multiple configs
- **System Monitoring** (4 endpoints):
  - `GET /tasks/system/status` - Get comprehensive system status
  - `GET /tasks/system/health` - Get system health check
  - `GET /tasks/system/enums` - Get enum values for dropdowns
  - `GET /tasks/system/dashboard` - Get dashboard data

### Core Models (Refactored v2.4)
- **User**: Basic user information (id, email, username, full_name, age, is_active, is_superuser)
- **RefreshToken**: JWT refresh token management with rotation
- **PasswordReset**: Password reset tokens with expiration and usage tracking
- **TaskConfig**: Task configuration (name, type, scheduler, parameters, schedule_config) - **Simplified**: Removed complex status enum
- **TaskExecution**: Task execution records with `is_success` boolean - **Simplified**: Replaced status enum with binary success/failure
- **RedditPost**: Reddit post data and metadata
- **RedditComment**: Reddit comment data and relationships

**Legacy Models** (removed/refactored during v2.4 update):
- ~~**RefreshToken**~~: JWT tokens now managed via Redis-based system
- ~~**ScheduleEvent**~~: Schedule event logging merged into Redis history service
- ~~**BotConfig**~~: Bot configuration system consolidated into task management
- ~~**ScrapeSession**~~: Scraping session management integrated into task execution system

### Schema Models (Modularized v2.4)
- **Authentication Schemas** (`auth.py`): LoginRequest, Token, PasswordResetRequest/Confirm/Response
- **User Management Schemas** (`user.py`): UserCreate, UserUpdate, UserResponse
- **Task Configuration Schemas** (`task_config_schemas.py`):
  - TaskConfigBase, TaskConfigCreate, TaskConfigUpdate, TaskConfigResponse
  - Supports dual cron format (expression + individual fields)
  - Includes Redis scheduling state integration
- **Schedule Management Schemas** (`task_schedules_schemas.py`):
  - ScheduledJobInfo, ScheduleActionRequest, ScheduleStatusResponse
  - ScheduleHistoryResponse, SchedulerSummaryResponse
- **Execution Management Schemas** (`task_executions_schemas.py`):
  - TaskExecutionResponse, ExecutionStatsResponse, ExecutionFilterRequest
  - Simplified with `is_success` boolean instead of complex status enums
- **System Monitoring Schemas** (`task_system_schemas.py`):
  - SystemStatusResponse, HealthCheckResponse, DashboardDataResponse
- **Reddit Content Schemas** (`reddit_content.py`): RedditPostResponse, RedditCommentResponse

**Architecture Benefits**:
- **Type Safety**: All 25 API endpoints have response_model validation
- **Modular Organization**: Schemas grouped by functionality instead of single large file
- **Zero Redundancy**: Eliminated duplicate schema classes
- **Enhanced Integration**: Database config + Redis scheduling state combined in responses

### Frontend Architecture
- **React 18** with TypeScript and Vite
- **Material-UI** for components and styling
- **Zustand** for state management (auth-store, api-store, ui-store)
- **State Management Pattern**:
  - `auth-store`: Authentication state, login/logout, user management
  - `api-store`: Unified API call management with loading/error states
  - `ui-store`: UI state (dialogs, notifications)
- **Route Protection**: `ProtectedRoute` component for access control
- **Unified Error Handling**: Centralized error processing with friendly messages
- **Axios** with smart interceptors for token management and refresh
- **Reddit Scraper Management**: Complete bot configuration and session monitoring interface

### Key Features

#### TaskIQ Task Management System
- **Distributed Task Processing**: TaskIQ 0.11.x with Redis/RabbitMQ message broker
- **Task Configuration**: Create, update, and manage task configurations via API
- **Multiple Scheduler Types**: Supports CRON, Interval, Date, and Manual scheduling
- **Dual Cron Format Support**: Accepts both `cron_expression` and individual cron fields
- **Task Execution**: Immediate execution and batch processing capabilities
- **System Monitoring**: Real-time task status, queue statistics, and system health
- **Task Types**: cleanup_tokens, cleanup_content, send_email, data_export, health_check, etc.
- **Error Handling**: Automatic retries, timeout handling, and failure tracking
- **Schedule Management**: Start, stop, pause, resume scheduled tasks

#### Reddit Scraping System
- **Bot Configuration**: Configure Reddit bots with subreddit targets, keywords, and posting rules
- **Session Management**: Track scraping sessions with status monitoring and detailed logs
- **Content Storage**: Store scraped Reddit posts and comments with full metadata
- **Real-time Monitoring**: Live status updates and session statistics
- **TaskIQ Integration**: Automated scraping via TaskIQ background tasks

#### Authentication & Security
- **Complete Auth Flow**: Registration, login, password reset with email verification
- **JWT Token System**: Access and refresh token rotation with secure storage
- **Role-based Access**: User roles and permissions system
- **Password Security**: Bcrypt hashing with secure token generation

#### User Interface
- **Responsive Design**: Material-UI components with mobile-friendly layouts
- **Real-time Updates**: Live data synchronization and status monitoring
- **Multi-language Support**: Chinese language interface with i18n structure
- **Advanced Components**: Data grids, dialogs, charts, and filtering systems

### Key Patterns
- **Backend**: Dependency injection for request context and authentication
- **Frontend**: Zustand stores → Components pattern with unified state management
- **API Communication**: Centralized axios instance with automatic token refresh
- **Route Protection**: Route-level access control with seamless redirects
- **Error Handling**: Backend-frontend aligned error codes and messages
- **Database**: CRUD pattern with SQLAlchemy models and auto-migrations
- **Configuration**: Environment-based with .env files

### Automatic Database Migration
- **On Docker Startup**: Automatically detects model changes and generates migrations
- **Migration Flow**:
  1. Check for database model changes
  2. Auto-generate migration files if changes detected
  3. Apply all pending migrations
  4. Start FastAPI server
- **No Manual Steps Required**: Just run `docker compose up`

### TaskIQ Task System Architecture (Refactored v2.4)

#### Optimized Components
- **TaskIQ Broker** (`broker.py`): Message broker configuration using Redis/RabbitMQ
- **TaskIQ Scheduler** (`scheduler.py`): Handles scheduled task execution with database synchronization
- **Core Services** (eliminated functional overlap):
  - **SchedulerCoreService** (`services/redis/scheduler_core.py`): Pure TaskIQ scheduling with independent Redis connection
  - **ScheduleHistoryRedisService** (`services/redis/history.py`): **Enhanced** - unified state, history, and metadata management
  - **SchedulerService** (`services/redis/scheduler.py`): Unified interface combining core + history services
- **Task Registry** (`core/tasks/registry.py`): Task type definitions and configuration - **Simplified**: Removed complex status enums
- **Task Routes** (`api/v1/routes/task_routes.py`): **Completely rewritten** - 25 RESTful API endpoints with modular architecture
- **Redis Manager** (`core/redis_manager.py`): **Optimized** - unified connection pool management

**Eliminated Components** (removed during refactoring):
- ~~**Task Manager**~~ (`services/task_manager.py`): Removed over-abstracted intermediate layer
- ~~**TaskServiceBase**~~, ~~**TaskExecutor**~~: Removed over-engineered base classes
- ~~**Implementation Layer**~~ (`app/implementation/`): Removed entire over-abstracted directory

#### Key Architectural Improvements
- **Connection Optimization**: Eliminated double Redis connections, unified connection pool
- **Functional Consolidation**: History service enhanced to handle state + metadata + history (no overlap)
- **Simplified Status Model**: Binary `is_success` instead of complex status state machines
- **Direct Service Calls**: API layer calls CRUD + Redis services directly (no intermediate abstractions)
- **Data Composition**: API responses combine PostgreSQL config + Redis scheduling state seamlessly

#### Task Types
- `cleanup_tokens` - Clean up expired authentication tokens
- `cleanup_content` - Clean up old scraped content
- `cleanup_events` - Clean up old schedule events
- `send_email` - Send email notifications
- `send_notification` - Send system notifications
- `data_export` - Export data to various formats
- `data_backup` - Backup system data
- `health_check` - System health monitoring
- `system_monitor` - System performance monitoring

#### Scheduler Types
- **Manual**: Execute only via API calls
- **CRON**: Execute on cron schedule (supports dual format)
- **Interval**: Execute at regular intervals
- **Date**: Execute once at specific date/time

#### Dual Cron Format Support
The system accepts both formats for CRON scheduling:

**Format 1: Individual Fields**
```json
{
  "minute": "0",
  "hour": "2", 
  "day": "*",
  "month": "*",
  "day_of_week": "*"
}
```

**Format 2: Cron Expression**
```json
{
  "cron_expression": "0 2 * * *"
}
```

#### Task Status Flow (Simplified v2.4)
**Database Execution Status** (PostgreSQL - `TaskExecution.is_success`):
- `true` - Task completed successfully
- `false` - Task failed with error

**Redis Scheduling Status** (`ScheduleStatus` enum):
- `inactive` - Task not scheduled
- `active` - Task actively scheduled in TaskIQ
- `paused` - Task temporarily suspended
- `error` - Scheduling error occurred

**TaskIQ Runtime Status** (handled by TaskIQ broker):
- `pending` - Task submitted but not yet started
- `running` - Task currently executing
- `revoked` - Task cancelled/revoked

**Architecture Separation**:
- **PostgreSQL**: Stores static configuration and execution results
- **Redis**: Manages dynamic scheduling state and history
- **TaskIQ**: Handles runtime task execution and queuing

### Development Notes
- The backend automatically runs migrations on startup via docker-compose
- Frontend proxy is handled by Vite dev server configuration  
- CORS is configured to allow frontend origin
- All services run in Docker with volume mounts for hot reloading
- Database connection uses asyncpg driver for better performance
- Reddit API integration using asyncpraw for asynchronous operations
- TaskIQ task system with distributed workers and scheduler containers
- Redis serves as primary message broker and result backend
- RabbitMQ available as alternative message broker
- TaskIQ scheduler automatically loads and manages scheduled tasks from database

### Authentication Flow
- **Login Process**: Returns access token (30min) and refresh token (7 days)
- **Backend Validation**: AuthMiddleware validates JWT tokens on protected routes
- **Frontend Management**: 
  - `AuthContext` provides application-level state initialization
  - `ProtectedRoute` handles route-level access control and redirects
  - Automatic token refresh via axios interceptors
- **Token Storage**: Refresh tokens stored in database with session management
- **Security**: Token rotation strategy with automatic cleanup
- **User Experience**: Seamless authentication with no page flashes

## Development Guidelines

### Frontend Development
- **State Management**: Use Zustand stores (`useAuthStore`, `useApiStore`, `useUIStore`) for all state management
- **API Calls**: Always use `api-store` methods (`fetchData`, `postData`, `patchData`, `deleteData`, `updateData`) instead of direct API calls
- **Route Protection**: Wrap all routes with `ProtectedRoute` component
- **Error Handling**: Use `extractErrorMessage()` or `extractAuthErrorMessage()` from `utils/errorHandler`
- **Forms**: Clear errors only when user starts typing, not on component mount
- **Loading States**: Use `getApiState(url)` from api-store to get loading/error states for specific endpoints

### Backend Development (Updated v2.4)
- **Constants**: Use constants from `app.constant.constants` instead of magic numbers/strings
- **Error Handling**: All custom exceptions should extend `ApiError` base class
- **HTTP Status**: Use correct status codes (201 for creation, 409 for conflicts, 403 for permissions)
- **Database Operations**: Use CRUD classes for all database operations
- **Transaction Handling**: Always use `db.add()`, `await db.commit()`, and `await db.refresh()` for database updates
- **Password Security**: Use `get_password_hash()` and `verify_password()` from `app.core.security`
- **Task Management**: Use `redis_services.scheduler` for task operations (unified interface)
- **Task Status**: Use boolean `is_success` for execution results, `ScheduleStatus` enum for scheduling state
- **SQLAlchemy Relations**: Use `lazy="select"` for relations that work with `selectinload`
- **Cron Scheduling**: Support both `cron_expression` and individual cron fields in schemas
- **Service Architecture**: Direct calls to CRUD + Redis services, avoid over-abstraction
- **Schema Organization**: Use modular schemas (`task_config_schemas`, `task_schedules_schemas`, etc.)
- **Connection Management**: Use unified Redis connection pool, avoid multiple Redis connections
- **Imports**: Ensure all models are properly exported from `__init__.py` files

### Common Patterns (Updated v2.4)
- **API Calls**: Use api-store methods with automatic loading/error state management
- **Redirects**: Let `ProtectedRoute` handle authentication redirects automatically
- **Loading States**: Managed by api-store and accessed via `getApiState(url)`
- **Error Display**: Show errors immediately, clear only on user interaction
- **Task Management**: Direct pattern - API → CRUD + Redis services (no intermediate layers)
- **Task Configuration**: Support dual cron format (expression or individual fields)
- **Background Tasks**: Implement via TaskIQ with optimized Redis connection management
- **Schedule Management**: Database-driven with Redis state synchronization
- **Data Composition**: Combine PostgreSQL config + Redis scheduling state in API responses
- **Status Management**: Use binary `is_success` for execution, enum for scheduling state
- **Service Separation**: Core scheduling (TaskIQ) + Enhanced history (state + metadata + events)
- **Connection Optimization**: Single unified Redis connection pool for all services except TaskIQ scheduler

### Environment-Specific Development Guidelines

#### Development Environment Usage
- **Start Services**: `docker compose -f docker-compose.dev.yml up --build`
- **Hot Reload**: Frontend and backend support real-time code changes
- **Debugging**: Full dependency access, detailed logging (INFO level)
- **Database Access**: PgAdmin at http://localhost:5050
- **Message Queue**: RabbitMQ Management at http://localhost:15672
- **Redis Monitoring**: RedisInsight at http://localhost:5540
- **File Changes**: Volume mounts enable instant code sync
- **Security**: Basic security headers, no rate limiting for development

#### Production Environment Usage
- **Start Services**: `docker compose -f docker-compose.prod.yml up --build`
- **SSL Configuration**: Requires valid SSL certificates in `nginx/ssl/`
- **Domain Setup**: Configure `warabi.dpdns.org` in nginx configuration
- **Security**: Full security headers, rate limiting, HTTPS redirect
- **Performance**: Optimized builds, static file caching, resource limits
- **Monitoring**: Health checks and structured JSON logging
- **User Security**: Non-root containers, minimal attack surface

#### Environment File Management
- **Development**: Use `.env.dev` with localhost configurations
- **Production**: Use `.env.prod` with production credentials and URLs
- **Consistency**: All environments follow unified variable order
- **Security**: Production uses stronger passwords and security settings

### Route Structure
- `/login` - User login page
- `/register` - User registration page  
- `/forgot-password` - Request password reset via email
- `/reset-password?token=xxx` - Reset password with valid token
- `/dashboard` - Main dashboard (protected)
- `/profile` - User profile management (protected)
- `/user` - User management page (protected)
- `/management/tasks` - Task configuration and management (protected)
- `/management/monitoring` - System monitoring and task execution status (protected)
- `/demo` - Demo page for testing features
- **Legacy Route Redirects**: `/scraper/*` and `/management/scraper/*` redirect to `/management/tasks`

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
- to memorize
- to memorize
- to memorize