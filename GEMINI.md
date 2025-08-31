# GEMINI Project Analysis

## Project Overview

This project is a full-stack Reddit scraping application with a web-based management interface. The application allows users to configure and manage multiple Reddit bots for automated content scraping. The backend is built with Python using the FastAPI framework, and the frontend is a React application built with TypeScript. The application uses a PostgreSQL database for data storage, Redis for caching and task queuing, and RabbitMQ as a message broker for background tasks. The entire application is containerized using Docker for easy deployment and development.

### Key Technologies

*   **Backend**: FastAPI, SQLAlchemy, Alembic, Pydantic, TaskIQ
*   **Frontend**: React, TypeScript, Vite, Material-UI, Zustand, Axios
*   **Database**: PostgreSQL, Redis
*   **Messaging**: RabbitMQ
*   **Infrastructure**: Docker, Docker Compose

### Architecture

The application follows a modern, decoupled architecture with a separate frontend and 

*   **Backend**: The FastAPI backend provides a RESTful API for the frontend to consume. It handles user authentication, bot configuration, scraping session management, and data storage. It uses SQLAlchemy as the ORM for interacting with the PostgreSQL database and Alembic for database migrations. Background tasks, such as scraping, are managed using TaskIQ with RabbitMQ as the message broker and Redis as the result 
*   **Frontend**: The React frontend provides a user interface for managing the scraping bots and viewing the scraped data. It uses Vite for the development server and build process. Material-UI is used for the UI components, and Zustand is used for state management. Axios is used for making API requests to the 
*   **Database**: A PostgreSQL database is used to store all the application data, including user information, bot configurations, and scraped Reddit content. Redis is used for caching and as a result backend for TaskIQ.
*   **Messaging**: RabbitMQ is used as a message broker to handle asynchronous tasks, such as starting and stopping scraping sessions.

## Building and Running

The recommended way to build and run the project is by using Docker and Docker Compose.

### Prerequisites

*   Docker
*   Docker Compose

### Running the Application

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd React-FastAPI-Postgres
    ```

2.  **Set up environment variables:**
    Create a `.env` file in the root of the project by copying the `.env.example` file.
    ```bash
    cp .env.example .env
    ```
    Update the `.env` file with your desired configuration.

3.  **Start the application:**
    ```bash
    docker-compose up --build
    ```

This will start all the services, including the frontend, backend, database, and message broker.

*   **Frontend**: http://localhost:3000
*   **Backend API**: http://localhost:8000
*   **API Documentation**: http://localhost:8000/docs

### Development Commands

**Backend**

*   **Run development server**: `cd backend && poetry run uvicorn app.main:app --reload`
*   **Create database migration**: `cd backend && poetry run alembic revision --autogenerate -m "description"`
*   **Apply migrations**: `cd backend && poetry run alembic upgrade head`
*   **Run tests**: `cd backend && poetry run pytest`

**Frontend**

*   **Run development server**: `cd frontend && npm run dev`
*   **Build for production**: `cd frontend && npm run build`
*   **Run linting**: `cd frontend && npm run lint`

## Development Conventions

### Backend

*   **Code Style**: The backend code follows the PEP 8 style guide.
*   **API**: The API is designed following RESTful principles.
*   **Configuration**: Configuration is loaded from environment variables using Pydantic's `BaseSettings`.
*   **Database**: Database migrations are managed using Alembic.
*   **Testing**: Unit and integration tests are written using `pytest`.

### Frontend

*   **Code Style**: The frontend code follows the standard TypeScript and React conventions. ESLint is used for linting.
*   **State Management**: Global state is managed using Zustand.
*   **API Interaction**: API requests are made using a pre-configured Axios instance.
*   **Component Library**: The UI is built using the Material-UI component library.
