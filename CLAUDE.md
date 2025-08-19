# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Docker Development (Primary)
- `docker compose up --build` - Start all services (frontend, backend, postgres, pgadmin, redis, rabbitmq, taskiq workers/scheduler)
- `docker compose up` - Start all services (uses cache, faster startup)
- `docker compose down` - Stop all services
- `docker compose logs backend` - View backend logs
- `docker compose logs frontend` - View frontend logs
- `docker compose logs taskiq_scheduler` - View TaskIQ scheduler logs
- `docker compose logs taskiq_worker` - View TaskIQ worker logs

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
│   ├── api/v1/            # API routes (auth, users, tasks, bot_config, scraping, reddit_content)
│   ├── core/              # Configuration, security, logging, constants, exceptions, task_registry
│   ├── crud/              # Database operations (user, token, task_config, task_execution, schedule_event, etc.)
│   ├── db/                # Database connection and base classes
│   ├── dependencies/      # Dependency injection (current_user, request_context)
│   ├── middleware/        # Auth and logging middleware
│   ├── models/            # SQLAlchemy models (user, token, task_config, task_execution, schedule_event, etc.)
│   ├── schemas/           # Pydantic schemas (auth, user, task_config, job_schemas, etc.)
│   ├── services/          # Business logic (email_service, task_manager, scraping_orchestrator)
│   ├── tasks/             # TaskIQ background tasks (cleanup, notification, data tasks)
│   ├── tests/             # Test files
│   └── utils/             # Common utilities (common, permissions)
├── alembic/               # Database migrations
├── broker.py              # TaskIQ broker configuration
├── scheduler.py           # TaskIQ scheduler configuration
└── pyproject.toml         # Poetry dependencies

frontend/                  # React frontend
├── src/
│   ├── components/        # React components (Layout, ProtectedRoute, TokenExpiryDialog, Scraper components)
│   ├── pages/             # Page components (Login, Register, Dashboard, Profile, ForgotPassword, ResetPassword, BotManagementPage, SessionManagementPage, DemoPage, UserPage)
│   ├── services/          # API client (axios, authManager, uiManager, interceptors)
│   ├── stores/            # Zustand stores (auth-store, api-store, ui-store)
│   ├── types/             # TypeScript types (auth, user, bot, session, api)
│   └── utils/             # Utility functions (errorHandler)
└── package.json           # npm dependencies
```

### Backend Architecture
- **FastAPI** with async/await support using asyncpg for PostgreSQL
- **JWT Authentication** with access and refresh tokens (dual-token system)
- **TaskIQ Task Management System** with Redis/RabbitMQ message broker
- **Reddit Scraping System** with bot configuration and session management
- **Middleware Stack** (order matters):
  1. AuthMiddleware - JWT validation (excludes auth endpoints)
  2. CORSMiddleware - Cross-origin requests
  3. RequestResponseLoggingMiddleware - Request/response logging
- **Configuration** using Pydantic Settings with nested configs (postgres, security, cors, redis, etc.)
- **Database**: SQLAlchemy 2.0 with automatic Alembic migrations
- **Logging**: Loguru for structured logging
- **Background Tasks**: TaskIQ 0.11.x for distributed task processing and scheduling

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

**Bot Configuration** (`/api/v1/bot-configs`)
- `GET /bot-configs` - Get bot configurations
- `POST /bot-configs` - Create new bot configuration
- `GET /bot-configs/{config_id}` - Get specific bot configuration
- `PATCH /bot-configs/{config_id}` - Update bot configuration
- `DELETE /bot-configs/{config_id}` - Delete bot configuration

**Scraping Management** (`/api/v1/scraping`)
- `POST /scraping/start` - Start scraping session
- `POST /scraping/stop` - Stop scraping session
- `GET /scraping/status` - Get scraping status
- `GET /scraping/sessions` - Get scraping sessions
- `GET /scraping/sessions/{session_id}` - Get specific session

**Reddit Content** (`/api/v1/reddit`)
- `GET /reddit/posts` - Get Reddit posts
- `GET /reddit/posts/{post_id}` - Get specific Reddit post
- `GET /reddit/posts/{post_id}/comments` - Get post comments
- `GET /reddit/comments` - Get Reddit comments

**Task Management** (`/api/v1/tasks`)
- `GET /tasks/system/status` - Get system status (scheduler, broker, task counts)
- `GET /tasks/system/health` - Get system health check
- `GET /tasks/configs` - List task configurations (with filtering/pagination)
- `GET /tasks/configs/{config_id}` - Get specific task configuration
- `POST /tasks/configs` - Create new task configuration
- `PUT /tasks/configs/{config_id}` - Update task configuration
- `PATCH /tasks/configs/{config_id}` - Partially update task configuration
- `DELETE /tasks/configs/{config_id}` - Delete task configuration
- `POST /tasks/configs/batch` - Batch create configurations
- `DELETE /tasks/configs/batch` - Batch delete configurations
- `POST /tasks/configs/{config_id}/schedule` - Manage scheduled task (start/stop/pause/resume)
- `GET /tasks/scheduled` - Get all scheduled jobs
- `POST /tasks/configs/{config_id}/execute` - Execute task immediately
- `POST /tasks/execute/by-type` - Execute task by type
- `POST /tasks/execute/batch` - Batch execute configurations
- `GET /tasks/status/{task_id}` - Get task execution status
- `GET /tasks/active` - Get active running tasks
- `GET /tasks/queues` - Get queue statistics
- `POST /tasks/revoke/{task_id}` - Revoke/cancel task
- `GET /tasks/task-types` - Get supported task types
- `GET /tasks/enums` - Get enum values for dropdowns
- `POST /tasks/validate` - Validate task configuration

### Core Models
- **User**: Basic user information (id, email, username, full_name, age, is_active, is_superuser)
- **RefreshToken**: JWT refresh token management with rotation
- **PasswordReset**: Password reset tokens with expiration and usage tracking
- **TaskConfig**: Task configuration (name, type, scheduler, parameters, schedule_config)
- **TaskExecution**: Task execution records with status and results
- **ScheduleEvent**: Schedule event logging (executed, error, missed, paused, resumed)
- **BotConfig**: Reddit bot configuration (subreddits, keywords, posting rules)
- **ScrapeSession**: Scraping session management and tracking
- **RedditPost**: Reddit post data and metadata
- **RedditComment**: Reddit comment data and relationships

### Schema Models
- **UserCreate**: User registration data
- **UserUpdate**: Unified user update model (supports partial updates)
- **UserResponse**: User data response
- **LoginRequest**: Login credentials
- **Token**: JWT token response
- **PasswordResetRequest**: Forgot password request (email)
- **PasswordResetConfirm**: Reset password with token and new password
- **PasswordResetResponse**: Generic response for password reset operations
- **TaskConfigCreate/Update/Response**: Task configuration schemas (supports dual cron format)
- **SystemStatusResponse**: System status with scheduler/broker state
- **TaskExecutionResult**: Task execution response
- **ScheduledJobInfo**: Scheduled job information
- **BotConfigCreate/Update/Response**: Bot configuration schemas
- **ScrapeSessionCreate/Update/Response**: Scraping session schemas
- **RedditPostResponse**: Reddit post data schema
- **RedditCommentResponse**: Reddit comment data schema

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

### TaskIQ Task System Architecture

#### Components
- **TaskIQ Broker** (`broker.py`): Message broker configuration using Redis/RabbitMQ
- **TaskIQ Scheduler** (`scheduler.py`): Handles scheduled task execution with database synchronization
- **Task Manager** (`services/task_manager.py`): High-level task management service
- **Task Registry** (`core/task_registry.py`): Task type definitions and configuration
- **Task Routes** (`api/v1/routes/task_routes.py`): RESTful API for task management

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

#### Task Status Flow
1. **pending** - Task submitted but not yet started
2. **running** - Task currently executing
3. **success** - Task completed successfully
4. **failed** - Task failed with error
5. **revoked** - Task cancelled/revoked

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

### Backend Development
- **Constants**: Use `StatusCode` and `ErrorMessages` from `app.core.constants` instead of magic numbers/strings
- **Error Handling**: All custom exceptions should extend `ApiError` base class
- **HTTP Status**: Use correct status codes (201 for creation, 409 for conflicts, 403 for permissions)
- **Database Operations**: Use CRUD classes for all database operations
- **Transaction Handling**: Always use `db.add()`, `await db.commit()`, and `await db.refresh()` for database updates
- **Password Security**: Use `get_password_hash()` and `verify_password()` from `app.core.security`
- **Task Management**: Use `TaskManager` service for all task operations, not direct scheduler access
- **SQLAlchemy Relations**: Use `lazy="select"` for relations that work with `selectinload` 
- **Cron Scheduling**: Support both `cron_expression` and individual cron fields in schemas
- **Imports**: Ensure all models are properly exported from `__init__.py` files

### Common Patterns
- **API Calls**: Use api-store methods with automatic loading/error state management
- **Redirects**: Let `ProtectedRoute` handle authentication redirects automatically
- **Loading States**: Managed by api-store and accessed via `getApiState(url)`
- **Error Display**: Show errors immediately, clear only on user interaction
- **Task Management**: Use TaskManager service → CRUD → TaskIQ pattern
- **Task Configuration**: Support dual cron format (expression or individual fields)
- **Background Tasks**: Implement via TaskIQ with distributed processing
- **Schedule Management**: Database-driven with automatic scheduler synchronization

### Route Structure
- `/login` - User login page
- `/register` - User registration page  
- `/forgot-password` - Request password reset via email
- `/reset-password?token=xxx` - Reset password with valid token
- `/dashboard` - Main dashboard (protected)
- `/profile` - User profile management (protected)
- `/user` - User management page (protected)
- `/scraper/bots` - Bot configuration management (protected)
- `/scraper/sessions` - Scraping session monitoring (protected)
- `/demo` - Demo page for testing features

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
- to memorize