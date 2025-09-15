FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry and upgrade pip for reliability
RUN python -m pip install --upgrade pip && pip install poetry

# Copy poetry files first for better caching
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not create a virtual environment and install to system
RUN poetry config virtualenvs.create false && \
    poetry config virtualenvs.in-project false

# Install dependencies using existing lockfile only (no lock inside container)
RUN poetry install --no-interaction --no-ansi

# Verify installation by attempting to import key modules
RUN python -c "import taskiq; import fastapi; import sqlalchemy; print('Dependencies installed successfully')"

# Note: spaCy models are downloaded in a separate init container (spacy_init)
# and mounted at runtime; avoid downloading large models in build.

# Copy application code
COPY . .

# Expose port
EXPOSE 8000
