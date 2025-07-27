FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy poetry files first for better caching
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not create a virtual environment
RUN poetry config virtualenvs.create false

# Generate lock file if it doesn't exist or is outdated, then install dependencies
RUN if [ ! -f poetry.lock ] || ! poetry check; then \
        echo "Generating/updating poetry.lock file..." && \
        poetry lock; \
    fi && \
    poetry install --no-interaction --no-ansi

# Copy application code
COPY . .

# Expose port
EXPOSE 8000
