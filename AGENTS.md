# Repository Guidelines

## Project Structure & Module Organization
- Root: `docker-compose.dev.yml`, `docker-compose.prod.yml`, `.env*`, `scripts/start.sh`.
- Backend (FastAPI): `backend/app/` with `api/`, `core/`, `crud/`, `db/`, `models/`, `schemas/`, `services/`, `tasks/`, `utils/`, and tests in `backend/app/tests/`.
- Frontend (React + Vite + TS): `frontend/src/` with path aliases (`@components/*`, `@stores/*`, etc.). Static assets in `public/`.
- Migrations: `backend/alembic/`, config in `backend/alembic.ini`.

## Build, Test, and Development Commands
- Local backend: `cd backend && poetry install && poetry run uvicorn app.main:app --reload`.
- Local frontend: `cd frontend && npm install && npm run dev` (uses Vite; set `VITE_API_URL`).
- Compose (dev): `docker compose -f docker-compose.dev.yml up --build`.
- Migrations: `cd backend && poetry run alembic upgrade head`.
- Tests (backend): `cd backend && poetry run pytest --cov=app`.
- Lint (frontend): `cd frontend && npm run lint`.

## Coding Style & Naming Conventions
- Python: PEP8, type hints, snake_case for functions/modules, PascalCase for classes. Keep Pydantic schemas under `app/schemas/` and CRUD under `app/crud/`.
- FastAPI: group routes under `app/api/v1/routes/`; use `APIRouter` with `prefix` and `tags`.
- TypeScript/React: PascalCase components; colocate UI by feature in `src/components/*`. Respect path aliases in `tsconfig.json`.
- Logging: use structured logging via backend `app/core/logging.py`.

## Testing Guidelines
- Backend: pytest. Place tests in `backend/app/tests/`, name `test_*.py`. Use `--cov=app` to track coverage. Example: `poetry run pytest -v app/tests/test_auth.py`.
- Frontend: no test runner configured; prefer Vitest + React Testing Library if adding tests. Keep snapshots minimal.

## Commit & Pull Request Guidelines
- Commits: short, imperative subject (≤72 chars), e.g., "Add task schedule summary API". Reference issues: "Refs #123".
- PRs: clear description, linked issues, steps to test, and screenshots/GIFs for UI changes. Note API or schema changes and migration steps.
- CI expectations: backend tests green, `npm run build` succeeds, no new linter errors.

## Security & Configuration Tips
- Environment: copy `.env.example` to `.env`; never commit secrets. Backend settings via Pydantic; frontend uses `VITE_*` vars (e.g., `VITE_API_URL`).
- Data: run Alembic migrations before starting the API. Use Redis/Postgres creds from `.env.dev` in dev; rotate in prod.
- Headers/CORS: keep CORS and auth middleware enabled (`app/middleware/*`).

