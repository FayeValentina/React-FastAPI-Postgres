# Backend Service - React-FastAPI-Postgres (Refactored v2.4)

FastAPI backend service with refactored TaskIQ task management system, providing comprehensive APIs for user management, task scheduling, and Reddit content scraping. Features optimized Redis architecture and modular API design.

## 🚀 Features

### Core Functionality
- **Authentication System**: JWT-based auth with access/refresh tokens
- **User Management**: Registration, login, profile management, password reset
- **Task Management System**: **Refactored v2.4** - Optimized TaskIQ with unified Redis architecture
- **Background Tasks**: Distributed task processing with TaskIQ 0.11.x
- **Schedule Management**: CRON, Date, Interval, and Manual scheduling with dual format support
- **Reddit Content Management**: Store and retrieve scraped Reddit posts and comments
- **System Monitoring**: Real-time task status, queue statistics, and health monitoring

### Technical Features
- **Async/Await**: Full asynchronous support with asyncpg and asyncpraw
- **Auto Migrations**: Automatic database schema migrations on startup
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation (25 task endpoints)
- **Structured Logging**: Comprehensive logging with Loguru
- **Security**: CORS, authentication middleware, input validation
- **Optimized Architecture**: Eliminated Redis connection duplication, simplified status models
- **Modular Schemas**: Type-safe API responses with organized schema files
- **Direct Service Calls**: Removed over-abstracted layers for better performance

## 📁 Project Structure

```
backend/                        # FastAPI backend (Refactored v2.4)
├── app/
│   ├── api/v1/                 # API routes
│   │   ├── routes/
│   │   │   ├── auth_routes.py          # Authentication endpoints
│   │   │   ├── user_routes.py          # User management
│   │   │   ├── task_routes.py          # Task management (25 endpoints, completely rewritten)
│   │   │   └── reddit_content_routes.py # Content retrieval
│   │   └── dependencies/       # Route dependencies
│   ├── constant/               # Application constants
│   │   └── constants.py       # HTTP status codes and messages
│   ├── core/                   # Core functionality
│   │   ├── config.py          # Configuration management
│   │   ├── security.py        # JWT and password handling
│   │   ├── exceptions.py      # Custom exception classes
│   │   ├── logging.py         # Logging configuration
│   │   ├── redis_manager.py   # Unified Redis connection management
│   │   ├── redis/             # Redis connection components
│   │   │   ├── base.py        # Redis base class
│   │   │   ├── config.py      # Redis configuration
│   │   │   └── pool.py        # Connection pool management
│   │   └── tasks/             # Task system core
│   │       ├── decorators.py  # Task decorators and execution tracking
│   │       └── registry.py    # Task type registry (simplified enums)
│   ├── crud/                   # Database operations
│   │   ├── user.py            # User CRUD operations
│   │   ├── password_reset.py  # Password reset CRUD
│   │   ├── task_config.py     # Task configuration CRUD (simplified)
│   │   ├── task_execution.py  # Task execution CRUD (is_success boolean)
│   │   └── reddit_content.py  # Content storage
│   ├── db/                     # Database setup
│   │   ├── base.py            # Database session management
│   │   └── base_class.py      # SQLAlchemy base model
│   ├── dependencies/           # Dependency injection
│   │   ├── current_user.py    # User context
│   │   └── request_context.py # Request context
│   ├── middleware/             # Custom middleware
│   │   ├── auth.py            # JWT authentication
│   │   └── logging.py         # Request/response logging
│   ├── models/                 # SQLAlchemy models (simplified)
│   │   ├── user.py            # User model
│   │   ├── password_reset.py  # Password reset model
│   │   ├── task_config.py     # Task configuration (no status field)
│   │   ├── task_execution.py  # Task execution (is_success boolean)
│   │   └── reddit_content.py  # Reddit post/comment models
│   ├── schemas/                # Modular Pydantic schemas (v2.4)
│   │   ├── auth.py            # Authentication schemas
│   │   ├── user.py            # User schemas
│   │   ├── task_config_schemas.py      # Task configuration schemas
│   │   ├── task_schedules_schemas.py   # Schedule management schemas
│   │   ├── task_executions_schemas.py  # Execution management schemas
│   │   ├── task_system_schemas.py      # System monitoring schemas
│   │   ├── token.py           # Token schemas
│   │   ├── password_reset.py  # Password reset schemas
│   │   └── reddit_content.py  # Content schemas
│   ├── services/               # Business logic services
│   │   ├── email_service.py           # Email notifications
│   │   ├── reddit_scraper_service.py  # Reddit API integration
│   │   └── redis/             # Optimized Redis services (unified architecture)
│   │       ├── auth.py                 # Authentication Redis service
│   │       ├── cache.py                # Caching Redis service
│   │       ├── history.py              # Enhanced: state + history + metadata (unified)
│   │       ├── scheduler_core.py       # Core TaskIQ scheduling (independent connection)
│   │       └── scheduler.py            # Unified scheduler service (combines core + history)
│   ├── tasks/                  # TaskIQ background tasks
│   │   ├── cleanup_tasks.py   # Cleanup operations
│   │   ├── data_tasks.py      # Data processing tasks
│   │   ├── notification_tasks.py      # Notification tasks
│   │   └── test_timeout_task.py       # Testing tasks
│   ├── tests/                  # Test files
│   ├── utils/                  # Utility functions
│   │   └── common.py          # Common utilities
│   └── main.py                # FastAPI application
├── alembic/                    # Database migrations
├── broker.py                   # TaskIQ broker configuration
├── scheduler.py                # TaskIQ scheduler configuration
├── Dockerfile                  # Docker configuration
├── pyproject.toml             # Poetry dependencies
└── README.md                  # This file
```

## 🛠️ Technology Stack

### Core Dependencies
- **FastAPI 0.109+**: Modern, fast web framework for building APIs
- **SQLAlchemy 2.0**: Advanced ORM with async support
- **PostgreSQL**: Robust relational database
- **asyncpg**: High-performance PostgreSQL adapter
- **Alembic**: Database schema migration tool

### Authentication & Security
- **python-jose**: JWT token handling
- **passlib + bcrypt**: Password hashing
- **python-multipart**: Form data handling

### Task Management (Refactored v2.4)
- **TaskIQ 0.11.x**: Distributed task processing and scheduling
- **Redis**: Message broker and result backend (optimized connection management)
- **RabbitMQ**: Alternative message broker support
- **Unified Redis Architecture**: Eliminated double connections and functional overlap

### Reddit Integration
- **asyncpraw**: Asynchronous Reddit API wrapper
- **aiohttp**: Async HTTP client

### Utilities
- **Loguru**: Modern logging library
- **Pydantic**: Data validation and settings
- **python-dotenv**: Environment variable management

## 🚀 Development Setup

### Prerequisites
- Python 3.11+
- Poetry (dependency management)
- PostgreSQL 17+

### Local Development

1. **Install dependencies:**
```bash
cd backend
poetry install
```

2. **Set up environment variables:**
```bash
# Copy environment template
cp ../.env.example ../.env
# Edit .env with your database credentials and secrets
```

3. **Database setup:**
```bash
# Start PostgreSQL (if using Docker)
docker run --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres:17

# Run migrations
poetry run alembic upgrade head
```

4. **Start development server:**
```bash
poetry run uvicorn app.main:app --reload
```

5. **Access API documentation:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Docker Development

This service is part of a Docker Compose setup. See the root directory's README.md for complete setup instructions.

```bash
# Start all services
docker compose up --build

# View backend logs
docker compose logs backend

# Execute commands in backend container
docker compose exec backend poetry run alembic upgrade head
```

## 🌐 API Endpoints

### Authentication (`/api/v1/auth`)
```
POST   /auth/login              # User login
POST   /auth/register           # User registration  
POST   /auth/refresh            # Refresh access token
POST   /auth/revoke             # Revoke refresh token
POST   /auth/logout             # Logout (revoke all tokens)
GET    /auth/me                 # Get current user info
POST   /auth/forgot-password    # Send password reset email
POST   /auth/verify-reset-token # Verify reset token
POST   /auth/reset-password     # Reset password with token
```

### User Management (`/api/v1/users`)
```
POST   /users                   # Create user (admin only)
GET    /users                   # List users (with filtering)
GET    /users/{user_id}         # Get specific user
PATCH  /users/{user_id}         # Update user
DELETE /users/{user_id}         # Delete user (admin only)
```

### Task Management (`/api/v1/tasks`) - **Refactored v2.4** (25 endpoints)
```
# Configuration Management (5 endpoints)
GET    /tasks/configs           # List task configurations
POST   /tasks/configs           # Create new task configuration
GET    /tasks/configs/{id}      # Get specific configuration
PUT    /tasks/configs/{id}      # Update configuration
DELETE /tasks/configs/{id}      # Delete configuration

# Schedule Management (7 endpoints)
POST   /tasks/schedules/{id}/{action}  # Start/stop/pause/resume
GET    /tasks/schedules         # Get all scheduled jobs
GET    /tasks/schedules/{id}    # Get specific schedule status
GET    /tasks/schedules/{id}/history  # Get schedule history
DELETE /tasks/schedules/{id}    # Stop and remove schedule
POST   /tasks/schedules/batch/{action} # Batch operations
GET    /tasks/schedules/summary # Get scheduler summary

# Execution Management (6 endpoints)
GET    /tasks/executions/by-config/{id}  # Get executions for config
GET    /tasks/executions/recent         # Get recent executions
GET    /tasks/executions/failed         # Get failed executions
GET    /tasks/executions/{id}/stats     # Get execution statistics
GET    /tasks/executions/{id}           # Get execution details
DELETE /tasks/executions/cleanup       # Clean old records

# Immediate Execution (3 endpoints)
POST   /tasks/execute/{id}      # Execute specific config
POST   /tasks/execute/by-type/{type}    # Execute by task type
POST   /tasks/execute/batch     # Batch execute configs

# System Monitoring (4 endpoints)
GET    /tasks/system/status     # Get system status
GET    /tasks/system/health     # Get health check
GET    /tasks/system/enums      # Get enum values
GET    /tasks/system/dashboard  # Get dashboard data
```

### Reddit Content (`/api/v1/reddit`)
```
GET    /reddit/posts            # Get scraped posts
GET    /reddit/posts/{post_id}  # Get specific post
GET    /reddit/posts/{post_id}/comments # Get post comments
GET    /reddit/comments         # Get scraped comments
```

## 🏗️ Architecture

### Application Structure (Refactored v2.4)
- **API Layer**: FastAPI routes with automatic documentation (25 task endpoints)
- **Direct Service Calls**: CRUD + Redis services (eliminated over-abstracted layers)
- **CRUD Layer**: Database operations and data access
- **Model Layer**: SQLAlchemy models and modular Pydantic schemas

### Key Patterns (Updated)
- **Dependency Injection**: Database sessions and user context
- **Middleware Stack**: Authentication, CORS, logging
- **CRUD Pattern**: Consistent database operations
- **Direct Service Pattern**: API → CRUD + Redis services (no intermediate layers)
- **Exception Handling**: Custom exceptions with proper HTTP status codes
- **Data Composition**: PostgreSQL config + Redis scheduling state combined
- **Connection Optimization**: Unified Redis connection pool (except TaskIQ scheduler)
- **Modular Schemas**: Type-safe responses organized by functionality

### Database Design (Simplified)
- **Users**: Authentication and profile information
- **Password Reset**: Password reset token management
- **Task Config**: Task configuration (removed complex status enum)
- **Task Execution**: Execution records with `is_success` boolean (simplified)
- **Reddit Content**: Posts and comments with relationships

### Redis Architecture (Optimized)
- **Scheduler Core**: Independent TaskIQ connection (required)
- **Enhanced History**: Unified state + history + metadata management
- **Authentication**: Token blacklisting and session management
- **Caching**: General purpose caching service
- **Connection Pool**: Unified pool for all services except TaskIQ scheduler

## 🔧 Configuration

### Environment Variables
```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=reddit_scraper
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# JWT Security
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# TaskIQ Configuration
REDIS_URL=redis://localhost:6379
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Reddit API
REDDIT_CLIENT_ID=your-reddit-client-id
REDDIT_CLIENT_SECRET=your-reddit-client-secret
REDDIT_USER_AGENT=YourApp/1.0

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### Settings Management
Configuration is managed through Pydantic Settings with nested configurations:
- `PostgresSettings`: Database configuration
- `SecuritySettings`: JWT and security settings
- `CORSSettings`: Cross-origin resource sharing
- `RedisSettings`: Redis connection and TaskIQ configuration
- `RedditSettings`: Reddit API credentials

## 🧪 Testing

### Running Tests
```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app

# Run specific test file
poetry run pytest app/tests/test_auth.py

# Run with verbose output
poetry run pytest -v
```

### Test Structure
- `test_auth.py`: Authentication flow tests
- `test_users.py`: User management tests
- `test_task_management.py`: Task configuration and execution tests
- `test_redis_services.py`: Redis service integration tests
- `test_models.py`: Database model tests

## 📊 Database Management

### Migrations
```bash
# Create new migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback migration
poetry run alembic downgrade -1

# View migration history
poetry run alembic history
```

### Database Operations
- **Automatic Migrations**: On Docker startup, schema changes are detected and applied
- **Transaction Management**: Proper commit/rollback handling
- **Connection Pooling**: Efficient database connection management
- **Query Optimization**: Async queries with proper relationships

## 🔐 Security

### Authentication Flow
1. User login with credentials
2. Server validates and returns JWT access token (30min) and refresh token (7days)
3. Client includes access token in Authorization header
4. Server validates token on protected routes
5. Client refreshes tokens before expiration

### Security Features
- **Password Hashing**: Bcrypt with salt
- **JWT Tokens**: Secure token generation and validation
- **Token Rotation**: Refresh token rotation for enhanced security
- **CORS Configuration**: Proper cross-origin request handling
- **Input Validation**: Pydantic schema validation
- **SQL Injection Protection**: SQLAlchemy ORM prevents SQL injection

## 🚀 Deployment

### Production Considerations
- **Environment Variables**: Use production secrets
- **Database**: Use managed PostgreSQL service
- **Logging**: Configure log aggregation
- **Monitoring**: Set up health checks and metrics
- **Scaling**: Consider horizontal scaling with load balancer

### Docker Production
```bash
# Build production image
docker build -t reddit-scraper-backend .

# Run with production environment
docker run -p 8000:8000 --env-file .env reddit-scraper-backend
```

## 📝 Development Guidelines

### Code Style
- **PEP 8**: Follow Python style guide
- **Type Hints**: Use type annotations
- **Docstrings**: Document functions and classes
- **Error Handling**: Use custom exceptions with proper HTTP status codes

### Best Practices (Updated v2.4)
- **Async/Await**: Use async operations for I/O
- **Database**: Use CRUD classes for database operations
- **Task Management**: Use `redis_services.scheduler` for task operations
- **Status Handling**: Use boolean `is_success` for execution results
- **Connection Management**: Use unified Redis connection pool
- **Schema Organization**: Use modular schemas by functionality
- **Service Architecture**: Direct CRUD + Redis service calls
- **Validation**: Validate input with Pydantic schemas
- **Testing**: Write tests for all endpoints
- **Logging**: Use structured logging with context

### Contributing
1. Create feature branch from main
2. Write tests for new functionality
3. Ensure all tests pass
4. Update documentation if needed
5. Submit pull request with clear description

## 🔗 Related Documentation

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)