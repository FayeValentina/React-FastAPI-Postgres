# React-FastAPI-Postgres

Full-stack web application featuring a **FastAPI** backend and a **React** (Vite + TypeScript) frontend.

### Architecture Highlights
- **JWT authentication** secures API endpoints and can be paired with **oauth2-proxy** for single sign-on.
- **Redis caching** accelerates reads and, together with **RabbitMQ**, powers **TaskIQ** background jobs.
- **PostgreSQL** stores persistent data.
- **Nginx** reverse proxy routes requests between services.

Docker Compose files are provided for both development and production environments.

## Project Structure

```
.
├── backend/                # FastAPI application, TaskIQ workers & scheduler
├── frontend/               # React client built with Vite
├── nginx/                  # Nginx templates and startup scripts
├── docker-compose.dev.yml  # Development stack with hot reload
├── docker-compose.prod.yml # Production stack with static build
└── README.md
```

## Development with Docker

1. Copy the example environment file:
   ```bash
   cp .env.example .env.dev
   ```
2. Start the development stack:
   ```bash
   docker compose -f docker-compose.dev.yml up --build
   ```
3. Access the services:
   - Frontend: <http://localhost>
   - API docs: <http://localhost/api/docs>
   - pgAdmin, RedisInsight and Portainer are also available in the dev stack.

## Production Deployment

1. Prepare production variables:
   ```bash
   cp .env.prod.example .env.prod
   ```
2. Build and run:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```
The production compose file builds the frontend, runs the FastAPI application, TaskIQ worker and scheduler,
PostgreSQL, RabbitMQ and Redis behind an Nginx reverse proxy with optional `oauth2-proxy` for web SSO.

## Local Development Without Docker

### Backend
```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Testing
```bash
cd backend && poetry run pytest
cd frontend && npm test
```
