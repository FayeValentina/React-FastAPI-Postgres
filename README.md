# Reddit Scraper Bot - Full Stack Application

A modern full-stack Reddit scraping application built with **FastAPI**, **React**, and **PostgreSQL**, featuring automated bot management and comprehensive content analysis.

## 🚀 Features

### Reddit Scraping System
- **Bot Configuration Management**: Create and manage multiple Reddit bots with customizable settings
- **Automated Scraping**: Scheduled scraping sessions with real-time monitoring
- **Content Storage**: Comprehensive storage of Reddit posts and comments with metadata
- **Session Tracking**: Detailed logging and analytics for all scraping activities

### Authentication & User Management
- **Complete Auth System**: Registration, login, password reset with email verification
- **JWT Token Management**: Secure access and refresh token rotation
- **Role-based Access Control**: User permissions and admin functionality
- **Password Security**: Bcrypt hashing with secure token generation

### Modern Tech Stack
- **Backend**: FastAPI with async/await, SQLAlchemy 2.0, PostgreSQL
- **Frontend**: React 18, TypeScript, Material-UI, Zustand state management
- **Infrastructure**: Docker containerization with hot reloading
- **Database**: PostgreSQL with automatic migrations via Alembic

## 📁 Project Structure

```
.
├── backend/                # FastAPI backend service
│   ├── app/
│   │   ├── api/v1/        # API routes (auth, users, bot_config, scraping, reddit_content)
│   │   ├── core/          # Configuration, security, logging
│   │   ├── crud/          # Database operations
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Business logic (scraping, email)
│   │   └── tasks/         # Background tasks
│   └── alembic/           # Database migrations
├── frontend/              # React frontend application
│   ├── src/
│   │   ├── components/    # Reusable React components
│   │   ├── pages/         # Page components
│   │   ├── stores/        # Zustand state management
│   │   └── services/      # API client and utilities
├── docker-compose.yml     # Docker services configuration
└── README.md             # This file
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
# Edit .env with your desired values (database credentials, JWT secrets, etc.)
```

3. **Start all services:**
```bash
docker compose up --build
```

4. **Access the applications:**
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **PgAdmin**: http://localhost:5050

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

#### 🤖 Bot Management
- Create and configure multiple Reddit scraping bots
- Set target subreddits, keywords, and scraping parameters
- Schedule automated scraping sessions
- Monitor bot performance and status

#### 📈 Session Monitoring
- Real-time scraping session tracking
- Detailed logs and statistics
- Success/failure metrics
- Content analysis and insights

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
- **SQLAlchemy 2.0**: Advanced ORM with async support
- **PostgreSQL**: Robust relational database
- **Alembic**: Database migration management
- **asyncpraw**: Asynchronous Reddit API wrapper
- **APScheduler**: Background task scheduling
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
- **Docker Compose**: Multi-service orchestration
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

**Architecture:**
- **RESTful API** with automatic OpenAPI documentation
- **Dependency Injection** for database sessions and user context
- **Middleware Stack** for authentication, CORS, and logging
- **CRUD Pattern** for database operations
- **Service Layer** for business logic

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

### Bot Management
- `GET /api/v1/bot-configs` - List bot configurations
- `POST /api/v1/bot-configs` - Create new bot
- `PATCH /api/v1/bot-configs/{id}` - Update bot configuration
- `DELETE /api/v1/bot-configs/{id}` - Delete bot

### Scraping
- `POST /api/v1/scraping/start` - Start scraping session
- `POST /api/v1/scraping/stop` - Stop scraping session
- `GET /api/v1/scraping/sessions` - List sessions
- `GET /api/v1/scraping/status` - Get scraping status

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

# Frontend
VITE_API_URL=http://localhost:8000

# PgAdmin
PGADMIN_DEFAULT_EMAIL=admin@example.com
PGLADMIN_DEFAULT_PASSWORD=admin

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