# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Docker Development (Primary)
- `docker compose up --build` - Start all services (frontend, backend, postgres, pgadmin)
- `docker compose up` - Start all services (uses cache, faster startup)
- `docker compose down` - Stop all services
- `docker compose logs backend` - View backend logs
- `docker compose logs frontend` - View frontend logs

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

## Architecture Overview

### Project Structure
```
backend/                    # FastAPI backend
├── app/
│   ├── api/v1/            # API routes (user, auth only)
│   ├── core/              # Configuration, security, logging
│   ├── crud/              # Database operations (user, token)
│   ├── db/                # Database connection and base classes
│   ├── middleware/        # Auth and logging middleware
│   ├── models/            # SQLAlchemy models (user, token)
│   ├── schemas/           # Pydantic schemas (simplified)
│   └── utils/             # Common utilities
├── alembic/               # Database migrations
└── pyproject.toml         # Poetry dependencies

frontend/                  # React frontend
├── src/
│   ├── components/        # React components
│   ├── hooks/            # Custom hooks (useApi)
│   ├── pages/            # Page components
│   ├── services/         # API client (axios)
│   └── types/            # TypeScript types
└── package.json          # npm dependencies
```

### Backend Architecture (Simplified)
- **FastAPI** with async/await support using asyncpg for PostgreSQL
- **JWT Authentication** with access and refresh tokens (dual-token system)
- **Middleware Stack** (order matters):
  1. AuthMiddleware - JWT validation (excludes auth endpoints)
  2. CORSMiddleware - Cross-origin requests
  3. RequestResponseLoggingMiddleware - Request/response logging
- **Configuration** using Pydantic Settings with nested configs (postgres, security, cors, etc.)
- **Database**: SQLAlchemy 2.0 with automatic Alembic migrations
- **Logging**: Loguru for structured logging

### API Endpoints (Simplified)
**Authentication** (`/api/v1/auth`)
- `POST /auth/login` - User login (username/email + password)
- `POST /auth/refresh` - Refresh access token
- `POST /auth/revoke` - Revoke refresh token
- `POST /auth/logout` - Logout (revoke all tokens)
- `POST /auth/register` - User registration
- `GET /auth/me` - Get current user info

**User Management** (`/api/v1/users`)
- `POST /users` - Create user (admin only)
- `GET /users` - Get user list (with filtering/sorting)
- `GET /users/{user_id}` - Get specific user
- `PATCH /users/{user_id}` - Update user (unified endpoint for partial updates)
- `DELETE /users/{user_id}` - Delete user (admin only)

### Core Models
- **User**: Basic user information (id, email, username, full_name, age, is_active, is_superuser)
- **RefreshToken**: JWT refresh token management with rotation

### Schema Models (Cleaned)
- **UserCreate**: User registration data
- **UserUpdate**: Unified user update model (supports partial updates)
- **UserResponse**: User data response
- **LoginRequest**: Login credentials
- **Token**: JWT token response

### Frontend Architecture
- **React 18** with TypeScript and Vite
- **Material-UI** for components and styling
- **Custom useApi Hook** for API calls with loading/error states
- **Axios** for HTTP client with interceptors
- **React Router** for navigation

### Key Patterns
- Backend uses dependency injection for request context and authentication
- Frontend follows hooks-based state management
- API communication through centralized axios instance
- Database operations through CRUD pattern with SQLAlchemy models
- Environment-based configuration with .env files

### Automatic Database Migration
- **On Docker Startup**: Automatically detects model changes and generates migrations
- **Migration Flow**:
  1. Check for database model changes
  2. Auto-generate migration files if changes detected
  3. Apply all pending migrations
  4. Start FastAPI server
- **No Manual Steps Required**: Just run `docker compose up`

### Development Notes
- The backend automatically runs migrations on startup via docker-compose
- Frontend proxy is handled by Vite dev server configuration  
- CORS is configured to allow frontend origin
- All services run in Docker with volume mounts for hot reloading
- Database connection uses asyncpg driver for better performance
- Code has been cleaned and simplified (removed post/article system, unused schemas)

### Authentication Flow
- Login returns access token (30min) and refresh token (7 days)
- AuthMiddleware validates JWT tokens on protected routes
- Tokens stored and managed by frontend API service
- Refresh token stored in RefreshToken model with session management
- Token rotation strategy for enhanced security

### Recent Optimizations
- Removed unused schemas and models (posts, complex address, payment info, etc.)
- Simplified user update endpoints (merged PUT/PATCH into single PATCH)
- Cleaned up utility functions (removed pagination helpers, duplicate error handlers)
- Streamlined API to focus on core user authentication and management
- Improved Docker configuration for reliable startup and automatic migrations