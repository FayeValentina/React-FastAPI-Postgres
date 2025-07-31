# Backend Service - Reddit Scraper Bot API

FastAPI backend service for the Reddit Scraper Bot application, providing comprehensive APIs for user management, bot configuration, and Reddit content scraping.

## 🚀 Features

### Core Functionality
- **Authentication System**: JWT-based auth with access/refresh tokens
- **User Management**: Registration, login, profile management, password reset
- **Bot Configuration**: Create and manage Reddit scraping bots
- **Scraping Orchestration**: Automated Reddit content scraping
- **Content Management**: Store and retrieve scraped Reddit posts and comments
- **Background Tasks**: Scheduled operations with APScheduler

### Technical Features
- **Async/Await**: Full asynchronous support with asyncpg and asyncpraw
- **Auto Migrations**: Automatic database schema migrations on startup
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation
- **Structured Logging**: Comprehensive logging with Loguru
- **Security**: CORS, authentication middleware, input validation

## 📁 Project Structure

```
backend/
├── app/
│   ├── api/v1/                 # API routes
│   │   ├── routes/
│   │   │   ├── auth_routes.py          # Authentication endpoints
│   │   │   ├── user_routes.py          # User management
│   │   │   ├── bot_config_routes.py    # Bot configuration
│   │   │   ├── scraping_routes.py      # Scraping control
│   │   │   └── reddit_content_routes.py # Content retrieval
│   │   └── dependencies/       # Route dependencies
│   ├── core/                   # Core functionality
│   │   ├── config.py          # Configuration management
│   │   ├── security.py        # JWT and password handling
│   │   ├── constants.py       # HTTP status codes and messages
│   │   ├── exceptions.py      # Custom exception classes
│   │   └── logging.py         # Logging configuration
│   ├── crud/                   # Database operations
│   │   ├── user.py            # User CRUD operations
│   │   ├── bot_config.py      # Bot configuration CRUD
│   │   ├── scrape_session.py  # Session management
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
│   ├── models/                 # SQLAlchemy models
│   │   ├── user.py            # User model
│   │   ├── token.py           # Refresh token model
│   │   ├── password_reset.py  # Password reset model
│   │   ├── bot_config.py      # Bot configuration model
│   │   ├── scrape_session.py  # Scraping session model
│   │   └── reddit_content.py  # Reddit post/comment models
│   ├── schemas/                # Pydantic models
│   │   ├── auth.py            # Authentication schemas
│   │   ├── user.py            # User schemas
│   │   ├── bot_config.py      # Bot configuration schemas
│   │   ├── scrape_session.py  # Session schemas
│   │   └── reddit_content.py  # Content schemas
│   ├── services/               # Business logic
│   │   ├── email_service.py           # Email notifications
│   │   ├── reddit_scraper_service.py  # Reddit API integration
│   │   └── scraping_orchestrator.py  # Scraping coordination
│   ├── tasks/                  # Background tasks
│   │   └── scheduler.py       # APScheduler configuration
│   ├── tests/                  # Test files
│   ├── utils/                  # Utility functions
│   │   ├── common.py          # Common utilities
│   │   └── permissions.py     # Permission checking
│   └── main.py                # FastAPI application
├── alembic/                    # Database migrations
│   ├── versions/              # Migration files
│   ├── env.py                 # Alembic environment
│   └── alembic.ini           # Alembic configuration
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

### Reddit Integration
- **asyncpraw**: Asynchronous Reddit API wrapper
- **aiohttp**: Async HTTP client

### Background Tasks
- **APScheduler**: Advanced Python scheduler
- **pytz**: Timezone support

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

### Bot Configuration (`/api/v1/bot-configs`)
```
GET    /bot-configs             # List bot configurations
POST   /bot-configs             # Create new bot
GET    /bot-configs/{config_id} # Get specific bot
PATCH  /bot-configs/{config_id} # Update bot configuration
DELETE /bot-configs/{config_id} # Delete bot
```

### Scraping Management (`/api/v1/scraping`)
```
POST   /scraping/start          # Start scraping session
POST   /scraping/stop           # Stop scraping session
GET    /scraping/status         # Get scraping status
GET    /scraping/sessions       # List scraping sessions
GET    /scraping/sessions/{id}  # Get specific session
```

### Reddit Content (`/api/v1/reddit`)
```
GET    /reddit/posts            # Get scraped posts
GET    /reddit/posts/{post_id}  # Get specific post
GET    /reddit/posts/{post_id}/comments # Get post comments
GET    /reddit/comments         # Get scraped comments
```

## 🏗️ Architecture

### Application Structure
- **API Layer**: FastAPI routes with automatic documentation
- **Service Layer**: Business logic and external API integration
- **CRUD Layer**: Database operations and data access
- **Model Layer**: SQLAlchemy models and Pydantic schemas

### Key Patterns
- **Dependency Injection**: Database sessions and user context
- **Middleware Stack**: Authentication, CORS, logging
- **CRUD Pattern**: Consistent database operations
- **Service Pattern**: Business logic separation
- **Exception Handling**: Custom exceptions with proper HTTP status codes

### Database Design
- **Users**: Authentication and profile information
- **Tokens**: JWT refresh token management
- **Bot Configs**: Reddit bot configuration and settings
- **Scrape Sessions**: Session tracking and monitoring
- **Reddit Content**: Posts and comments with relationships

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
- `test_bot_config.py`: Bot configuration tests
- `test_scraping.py`: Scraping functionality tests
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

### Best Practices
- **Async/Await**: Use async operations for I/O
- **Database**: Use CRUD classes for database operations
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