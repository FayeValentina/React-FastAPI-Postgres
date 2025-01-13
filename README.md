# FastAPI + React + PostgreSQL Full Stack Application

A modern full-stack application using FastAPI, React, and PostgreSQL, all containerized with Docker.

## Project Structure

```
.
├── backend/                # FastAPI backend service
├── frontend/              # React frontend application
├── docker-compose.yml     # Docker Compose configuration
├── .env                   # Environment variables (not in git)
├── .env.example          # Environment variables template
└── README.md             # This file
```

## Prerequisites

- Docker and Docker Compose
- Git

## Quick Start

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your desired values
```

3. Start the services:
```bash
docker compose up --build
```

4. Access the applications:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- PgAdmin: http://localhost:5050

## Development

### Frontend Development

The frontend service uses Vite and supports hot reloading. Any changes you make to the frontend code will be reflected immediately.

### Backend Development

The backend service uses FastAPI with automatic reloading enabled. Changes to the Python code will trigger an automatic restart.

### Database

PostgreSQL is accessible:
- From host: localhost:5433
- From containers: postgres:5432

To connect using PgAdmin:
1. Access PgAdmin at http://localhost:5050
2. Login with credentials from .env file
3. Add new server:
   - Host: postgres
   - Port: 5432
   - Database: postgres
   - Username: from POSTGRES_USER
   - Password: from POSTGRES_PASSWORD

## Environment Variables

See `.env.example` for all available configuration options. The following services can be configured:
- PostgreSQL
- PgAdmin
- Backend API
- Frontend Development Server

## Contributing

1. Create a feature branch
2. Make your changes
3. Submit a pull request

## License

[MIT License](LICENSE) 