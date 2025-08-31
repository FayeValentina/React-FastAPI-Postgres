# React-FastAPI-Postgres - Full Stack Application (Refactored v2.4)

A modern full-stack application built with **FastAPI**, **React**, and **PostgreSQL**, featuring **refactored TaskIQ task management system** with optimized Redis architecture, user authentication, and comprehensive task scheduling capabilities.

## 🚀 Features

### Task Management System (Refactored v2.4)
- **TaskIQ Integration**: Distributed task processing with Redis/RabbitMQ message brokers
- **25 API Endpoints**: Complete task configuration, scheduling, execution, and monitoring
- **Optimized Redis Architecture**: Eliminated double connections and functional overlap
- **Multiple Scheduler Types**: CRON, Date, Interval, and Manual scheduling with dual format support
- **Real-time Monitoring**: Live task status, queue statistics, and system health
- **Simplified Status Model**: Binary execution results with enhanced scheduling state management

### Reddit Content Management
- **Content Storage**: Comprehensive storage of Reddit posts and comments with metadata
- **Background Processing**: Automated content scraping via TaskIQ background tasks

### Authentication & User Management
- **Complete Auth System**: Registration, login, password reset with email verification
- **JWT Token Management**: Secure access and refresh token rotation
- **Role-based Access Control**: User permissions and admin functionality
- **Password Security**: Bcrypt hashing with secure token generation

### Modern Tech Stack (Updated v2.4)
- **Backend**: FastAPI with async/await, SQLAlchemy 2.0, PostgreSQL, **TaskIQ 0.11.x**
- **Task System**: **Refactored architecture** - unified Redis connection pool, modular schemas
- **Frontend**: React 18, TypeScript, Material-UI, Zustand state management
- **Infrastructure**: Docker containerization with hot reloading, Redis, RabbitMQ
- **Database**: PostgreSQL with automatic migrations via Alembic

## 📁 Project Structure

```
.                              # React-FastAPI-Postgres (Refactored v2.4)
├── backend/                   # FastAPI backend service
│   ├── app/
│   │   ├── api/v1/            # API routes (auth, users, tasks, reddit_content)
│   │   │   └── routes/        # task_routes.py (25 endpoints, completely rewritten)
│   │   ├── constant/          # Application constants
│   │   ├── core/              # Core functionality
│   │   │   ├── redis/         # Redis connection management
│   │   │   └── tasks/         # Task system (registry, decorators)
│   │   ├── crud/              # Database operations (simplified)
│   │   ├── models/            # SQLAlchemy models (simplified status)
│   │   ├── schemas/           # Modular Pydantic schemas (4 task schema files)
│   │   ├── services/          # Business logic services
│   │   │   ├── email_service.py           # Email service
│   │   │   ├── reddit_scraper_service.py  # Reddit integration
│   │   │   └── redis/         # Optimized Redis services (unified architecture)
│   │   │       ├── history.py     # Enhanced: state + history + metadata
│   │   │       ├── scheduler_core.py      # Core TaskIQ scheduling
│   │   │       └── scheduler.py           # Unified scheduler service
│   │   └── tasks/             # TaskIQ background tasks
│   ├── alembic/               # Database migrations
│   ├── broker.py              # TaskIQ broker configuration
│   └── scheduler.py           # TaskIQ scheduler configuration
├── frontend/                  # React frontend application
│   └── src/
│       ├── components/        # Reusable React components
│       ├── pages/             # Page components
│       ├── stores/            # Zustand state management
│       └── services/          # API client and utilities
├── docker-compose.yml         # Multi-service orchestration (backend, frontend, postgres, redis, rabbitmq, taskiq)
└── README.md                 # This file
```

## 🛠️ Prerequisites

- **Docker** and **Docker Compose** (recommended)
- **Git**
- **Node.js 20+** and **Python 3.11+** (for local development)

## 🚀 Quick Start

### Option 1: Docker (Recommended)

1. **Clone the repository:**
```bash
git clone <repository-url>
cd React-FastAPI-Postgres
```

2. **Set up environment variables:**
```bash
cp .env.example .env
# Edit .env with your desired values (database credentials, JWT secrets, Redis/TaskIQ config, etc.)
```

3. **Start all services:**
```bash
docker compose up --build
```

4. **Access the applications:**
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (25 task endpoints)
- **PgAdmin**: http://localhost:5050
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Redis**: localhost:6379

### Option 2: Local Development

**Backend:**
```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Database:**
```bash
# Run PostgreSQL locally or use Docker:
docker run --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres:17
```

## 📊 Application Overview

### Main Features

#### ⚙️ Task Management System (Refactored v2.4)
- **25 API Endpoints**: Complete task configuration, scheduling, execution, and monitoring
- **Multiple Scheduler Types**: CRON (dual format), Date, Interval, and Manual scheduling
- **Real-time Monitoring**: Live task status, queue statistics, and system health
- **Background Processing**: Distributed task execution with TaskIQ workers
- **Optimized Architecture**: Unified Redis connection pool, eliminated functional overlap

#### 📈 System Monitoring
- Real-time task execution tracking
- Detailed execution logs and statistics  
- Success/failure metrics with simplified boolean status
- Schedule history and event tracking
- System health monitoring and dashboard

#### 👥 User Management
- User registration and authentication
- Profile management
- Admin panel for user oversight
- Role-based permissions

#### 🔐 Security
- JWT-based authentication with token rotation
- Password reset via email verification
- Secure API endpoints with middleware protection
- Environment-based configuration

### Technology Stack

**Backend Technologies:**
- **FastAPI**: Modern Python web framework with automatic API documentation
- **TaskIQ 0.11.x**: **Refactored** - Distributed task processing and scheduling system
- **Redis**: **Optimized** - Unified connection pool, message broker, result backend  
- **RabbitMQ**: Alternative message broker support
- **SQLAlchemy 2.0**: Advanced ORM with async support
- **PostgreSQL**: Robust relational database
- **Alembic**: Database migration management
- **asyncpraw**: Asynchronous Reddit API wrapper
- **Loguru**: Structured logging

**Frontend Technologies:**
- **React 18**: Modern React with hooks and concurrent features
- **TypeScript**: Type-safe JavaScript development
- **Material-UI**: Professional React component library
- **Zustand**: Lightweight state management
- **Vite**: Fast build tool and development server
- **Axios**: HTTP client with interceptors

**Infrastructure:**
- **Docker**: Containerization for consistent deployment
- **Docker Compose**: Multi-service orchestration (backend, frontend, postgres, redis, rabbitmq, taskiq)
- **TaskIQ Workers**: Distributed task processing containers
- **TaskIQ Scheduler**: Scheduled task management container
- **Nginx**: Reverse proxy and static file serving (production)

## 🔧 Development

### Backend Development

**Key Commands:**
```bash
# Start development server
cd backend && poetry run uvicorn app.main:app --reload

# Create database migration
cd backend && poetry run alembic revision --autogenerate -m "description"

# Apply migrations
cd backend && poetry run alembic upgrade head

# Run tests
cd backend && poetry run pytest
```

**Architecture (Refactored v2.4):**
- **RESTful API** with automatic OpenAPI documentation (25 task endpoints)
- **Direct Service Calls**: API → CRUD + Redis services (eliminated over-abstracted layers)
- **Optimized Connection Management**: Unified Redis connection pool
- **Modular Schemas**: Type-safe responses organized by functionality
- **Simplified Status Model**: Binary execution results with enhanced scheduling state
- **Data Composition**: PostgreSQL configuration + Redis scheduling state combined
- **Dependency Injection** for database sessions and user context
- **Middleware Stack** for authentication, CORS, and logging

### Frontend Development

**Key Commands:**
```bash
# Start development server
cd frontend && npm run dev

# Build for production
cd frontend && npm run build

# Run linting
cd frontend && npm run lint
```

**Architecture:**
- **Component-based** React architecture
- **Zustand Stores** for state management
- **Protected Routes** with automatic redirects
- **Unified Error Handling** across the application
- **Responsive Design** with Material-UI

### Database

**PostgreSQL Access:**
- **From host**: `localhost:5433`
- **From containers**: `postgres:5432`
- **PgAdmin**: http://localhost:5050 (credentials from .env)

**Automatic Migrations:**
- Database migrations run automatically on Docker startup
- Model changes are detected and migration files generated
- No manual intervention required for schema updates

## 🌐 API Endpoints

### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user
- `POST /api/v1/auth/forgot-password` - Password reset request
- `POST /api/v1/auth/reset-password` - Reset password with token

### Task Management (Refactored v2.4) - 25 Endpoints
**Configuration Management:**
- `GET /api/v1/tasks/configs` - List task configurations
- `POST /api/v1/tasks/configs` - Create task configuration
- `GET /api/v1/tasks/configs/{id}` - Get specific configuration
- `PUT /api/v1/tasks/configs/{id}` - Update configuration
- `DELETE /api/v1/tasks/configs/{id}` - Delete configuration

**Schedule Management:**
- `POST /api/v1/tasks/schedules/{id}/{action}` - Start/stop/pause/resume tasks
- `GET /api/v1/tasks/schedules` - Get all scheduled jobs
- `GET /api/v1/tasks/schedules/{id}/history` - Get schedule history
- `GET /api/v1/tasks/schedules/summary` - Get scheduler summary

**Execution Management:**
- `GET /api/v1/tasks/executions/by-config/{id}` - Get executions for config
- `GET /api/v1/tasks/executions/recent` - Get recent executions
- `GET /api/v1/tasks/executions/failed` - Get failed executions
- `POST /api/v1/tasks/execute/{id}` - Execute task immediately

**System Monitoring:**
- `GET /api/v1/tasks/system/status` - Get system status
- `GET /api/v1/tasks/system/health` - Get health check
- `GET /api/v1/tasks/system/dashboard` - Get dashboard data

### Content
- `GET /api/v1/reddit/posts` - Get scraped Reddit posts
- `GET /api/v1/reddit/comments` - Get scraped comments
- `GET /api/v1/reddit/posts/{id}/comments` - Get post comments

## 📝 Environment Configuration

Create a `.env` file with the following variables:

```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=reddit_scraper
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# JWT Security
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# TaskIQ Configuration (Refactored v2.4)
REDIS_URL=redis://redis:6379
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
TASKIQ_BROKER_TYPE=redis

# Frontend
VITE_API_URL=http://localhost:8000

# PgAdmin
PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=admin

# RabbitMQ
RABBITMQ_DEFAULT_USER=guest
RABBITMQ_DEFAULT_PASS=guest

# Reddit API (optional)
REDDIT_CLIENT_ID=your-reddit-client-id
REDDIT_CLIENT_SECRET=your-reddit-client-secret
REDDIT_USER_AGENT=your-app-name
```

## 🚀 Deployment

### Production Deployment

1. **Build and deploy with Docker:**
```bash
docker compose -f docker-compose.prod.yml up --build -d
```

2. **Environment Setup:**
- Use production environment variables
- Configure proper domain and SSL certificates
- Set up reverse proxy (Nginx/Traefik)
- Configure backup strategies for PostgreSQL

### Security Considerations

- Change default passwords and secrets
- Use environment variables for sensitive data
- Implement rate limiting
- Regular security updates
- Monitor logs and metrics

## 🧪 Testing

```bash
# Backend tests
cd backend && poetry run pytest

# Frontend tests (if configured)
cd frontend && npm test

# Integration tests
docker compose -f docker-compose.test.yml up --build
```

## 📚 Documentation

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Alternative API Docs**: http://localhost:8000/redoc (ReDoc)
- **Database Schema**: Check `/backend/alembic/versions/` for migration files

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Material-UI](https://mui.com/)
- [PostgreSQL](https://www.postgresql.org/)
- [Docker](https://www.docker.com/)