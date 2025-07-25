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
│   ├── components/        # React components (Layout, ProtectedRoute)
│   ├── contexts/          # React contexts (AuthContext)
│   ├── hooks/            # Custom hooks (useApi, useAuth)
│   ├── pages/            # Page components
│   ├── services/         # API client (axios)
│   ├── stores/           # Zustand stores (auth-store, api-store)
│   ├── types/            # TypeScript types
│   └── utils/            # Utility functions (errorHandler)
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

### Frontend Architecture (Refactored)
- **React 18** with TypeScript and Vite
- **Material-UI** for components and styling
- **Zustand** for state management (auth-store, api-store)
- **React Context + Hooks Pattern**:
  - `AuthContext` for application-level authentication state
  - `useAuth` hook for unified authentication operations
  - `useApi` hook for API calls with loading/error states
- **Route Protection**: `ProtectedRoute` component for access control
- **Unified Error Handling**: Centralized error processing with friendly messages
- **Axios** with smart interceptors for token management and refresh

### Key Patterns
- **Backend**: Dependency injection for request context and authentication
- **Frontend**: Layered architecture with Context → Hooks → Components
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

### Development Notes
- The backend automatically runs migrations on startup via docker-compose
- Frontend proxy is handled by Vite dev server configuration  
- CORS is configured to allow frontend origin
- All services run in Docker with volume mounts for hot reloading
- Database connection uses asyncpg driver for better performance
- Code has been cleaned and simplified (removed post/article system, unused schemas)

### Authentication Flow (Improved)
- **Login Process**: Returns access token (30min) and refresh token (7 days)
- **Backend Validation**: AuthMiddleware validates JWT tokens on protected routes
- **Frontend Management**: 
  - `AuthContext` provides application-level state initialization
  - `ProtectedRoute` handles route-level access control and redirects
  - Automatic token refresh via axios interceptors
- **Token Storage**: Refresh tokens stored in database with session management
- **Security**: Token rotation strategy with automatic cleanup
- **User Experience**: Seamless authentication with no page flashes

### Recent Optimizations

#### Backend Refactoring (Completed)
- ✅ **Model Exports**: Fixed RefreshToken import/export in models
- ✅ **Error Handling**: Unified error messages and HTTP status codes via constants
- ✅ **Code Cleanup**: Removed unused imports, duplicate code, and Post model references
- ✅ **Status Codes**: Standardized HTTP responses (201 for creation, 409 for conflicts, etc.)
- ✅ **Configuration**: Removed unused email settings and cleaned up config structure

#### Frontend Refactoring (Completed)
- ✅ **Architecture Overhaul**: Implemented layered Context → Hooks → Components pattern
- ✅ **Route Protection**: Added `ProtectedRoute` component with automatic redirects
- ✅ **Authentication Context**: Created `AuthContext` for application-level state management
- ✅ **Unified Error Handling**: Implemented `errorHandler` utility with backend-aligned messages
- ✅ **Smart Interceptors**: Enhanced axios interceptors to exclude auth requests from token refresh
- ✅ **Bug Fixes**: Fixed error message persistence in Login/Register pages
- ✅ **User Experience**: Eliminated page flashes, improved loading states, seamless navigation

#### Key Improvements
- **Security**: Route-level access control with role-based permissions support
- **Maintainability**: Centralized error handling and consistent code patterns
- **Performance**: Optimized re-rendering and eliminated unnecessary API calls
- **Reliability**: Proper error boundaries and graceful failure handling
- **Developer Experience**: Clear separation of concerns and reusable components

## Development Guidelines

### Frontend Development
- **Authentication**: Always use `useAuth()` hook from `AuthContext`, never directly use `useAuthStore()`
- **Route Protection**: Wrap all routes with `ProtectedRoute` component
- **Error Handling**: Use `extractErrorMessage()` or `extractAuthErrorMessage()` from `utils/errorHandler`
- **State Management**: Use Zustand stores for complex state, React Context for application-level state
- **Forms**: Clear errors only when user starts typing, not on component mount

### Backend Development
- **Constants**: Use `StatusCode` and `ErrorMessages` from `app.core.constants` instead of magic numbers/strings
- **Error Handling**: All custom exceptions should extend `ApiError` base class
- **HTTP Status**: Use correct status codes (201 for creation, 409 for conflicts, 403 for permissions)
- **Imports**: Ensure all models are properly exported from `__init__.py` files

### Common Patterns
- **API Calls**: Use axios interceptors for automatic token management
- **Redirects**: Let `ProtectedRoute` handle authentication redirects automatically
- **Loading States**: Managed by stores and propagated through hooks
- **Error Display**: Show errors immediately, clear only on user interaction