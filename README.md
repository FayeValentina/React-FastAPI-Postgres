# Full-Stack RAG Application

This project is a sophisticated, full-stack Retrieval-Augmented Generation (RAG) application. It integrates multiple AI models to provide a powerful, language-aware chat experience backed by a dynamic knowledge base. The backend is built with Python (FastAPI) and the frontend with React (TypeScript).

The application can ingest documents, process them into a vector knowledge base, and leverage both local and remote Large Language Models (LLMs) to answer questions based on the stored information.

## Core Features

- **Retrieval-Augmented Generation (RAG)**: The core of the application. It retrieves relevant information from a knowledge base to provide context-aware answers from LLMs.
- **Multi-Model AI Integration**:
    - **Embedding Models**: Uses `sentence-transformers` to generate vector embeddings for text.
    - **LLMs**: Supports both local GGUF models (via a LlamaEdge-like API) and remote APIs like OpenAI.
    - **NLP Pre-processing**: Utilizes `spaCy` for text processing tasks.
- **Vector Database**: Leverages PostgreSQL with the `pgvector` extension for efficient similarity search.
- **Multi-Lingual Support**: Automatically detects user language (English, Chinese, Japanese) and adapts prompts for a localized experience.
- **Asynchronous Task Processing**: Uses `TaskIQ` with RabbitMQ and Redis for handling background jobs like document ingestion and embedding generation.
- **Web-Based Management UI**: A modern React interface (built with Material-UI) providing comprehensive control over the application:
    - **Interactive Chat**: A WebSocket-powered chat interface for real-time interaction with the RAG system, featuring streaming, Markdown rendering, and parameter adjustment.
    - **Knowledge Base Management**: A full CRUD interface to create, manage, and "ingest" text into documents that form the knowledge base. Includes a semantic search feature to test retrieval.
    - **Task Management Center**: A powerful dashboard for managing the `TaskIQ` backend. Users can create, schedule, and monitor asynchronous jobs (e.g., document ingestion) directly from the UI.

## Architecture Overview

The application follows a decoupled, service-oriented architecture:

1.  **Data Ingestion**: Documents or text are ingested into the system.
2.  **Knowledge Base Pipeline**:
    - An asynchronous task is triggered.
    - The text is processed and chunked using `spaCy`.
    - Each chunk is converted into a vector embedding using a `sentence-transformers` model.
    - The original text and its corresponding vector are stored in the `pgvector` database.
3.  **RAG Chat Flow**:
    - A user submits a question through the React UI.
    - The backend API receives the question, vectorizes it, and performs a similarity search in `pgvector` to find relevant document chunks.
    - The `llm.service` constructs a detailed prompt containing the user's question and the retrieved context, localized to the user's language.
    - The prompt is sent via the `llm.client` to the configured LLM (local or remote).
    - The LLM generates an answer based on the provided context, which is then streamed back to the user.

### Key Technologies

- **Backend**: FastAPI, SQLAlchemy, Alembic, Pydantic, TaskIQ, `pgvector`
- **Frontend**: React, TypeScript, Vite, Material-UI, Zustand, Axios
- **AI**: `sentence-transformers`, `spacy`, `openai`, `google-genai`, `torch` (CPU)
- **Database**: PostgreSQL, Redis
- **Messaging**: RabbitMQ
- **Infrastructure**: Docker, Docker Compose, Nginx

## Building and Running

The project is fully containerized and managed via Docker Compose.

### Prerequisites

- Docker
- Docker Compose

### Running the Application

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd React-FastAPI-Postgres
    ```

2.  **Set up environment variables:**
    Create a `.env.dev` file by copying the example. This file controls which AI models are downloaded and used.
    ```bash
    cp .env.example .env.dev
    ```
    Update `.env.dev` with your desired model configurations (e.g., `EMBEDDING_MODEL`, `CHAT_REPO_ID`, `CHAT_FILENAME`).

3.  **Start the application:**
    ```bash
    docker-compose -f docker-compose.dev.yml up --build
    ```
    On the first run, the `*-init` services will download the specified AI models into a shared Docker volume (`/models`). This may take some time.

- **Frontend & API**: http://localhost/
- **API Documentation**: http://localhost/docs

### Model Initialization

The AI models are downloaded by initialization scripts in the `scripts/` directory:
- `llm_init.sh`: Downloads a GGUF-formatted LLM from a Hugging Face repository.
- `embeddings_init.sh`: Downloads a `sentence-transformers` model for embeddings.
- `spacy_init.sh`: Downloads `spaCy` model wheels.

These scripts are run automatically by Docker Compose on startup.

### Development Commands

**Backend**

- **Run development server**: `cd backend && poetry run uvicorn app.main:app --reload`
- **Create database migration**: `cd backend && poetry run alembic revision --autogenerate -m "description"`
- **Apply migrations**: `cd backend && poetry run alembic upgrade head`
- **Run tests**: `cd backend && poetry run pytest`

**Frontend**

- **Run development server**: `cd frontend && npm run dev`
- **Build for production**: `cd frontend && npm run build`
- **Run linting**: `cd frontend && npm run lint`
