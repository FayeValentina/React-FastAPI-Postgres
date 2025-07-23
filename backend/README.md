# Backend Service

This is the backend service for the FastAPI + React + PostgreSQL application.

## Structure

```
backend/
├── app/                    # Application package
│   ├── api/               # API endpoints
│   │   └── v1/           # API version 1
│   ├── core/             # Core functionality
│   ├── db/               # Database related code
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic models
│   ├── tests/            # Test files
│   └── utils/            # Utility functions
├── alembic/              # Database migrations
├── Dockerfile           # Docker configuration
├── pyproject.toml       # Python dependencies
└── README.md           # This file
```

## Development

This service is part of a Docker Compose setup. Please refer to the root directory's README.md for setup instructions.

### Dependencies

- Python 3.11+
- Poetry for dependency management
- PostgreSQL 17
- FastAPI

### Environment Variables

All environment variables are managed in the root directory's `.env` file. See `.env.example` for available options.

### Database Migrations

To create a new migration:

```bash
docker compose exec backend poetry run alembic revision --autogenerate -m "description"
```

To apply migrations:

```bash
docker compose exec backend poetry run alembic upgrade head
```

### API Documentation

When the service is running, you can access:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc