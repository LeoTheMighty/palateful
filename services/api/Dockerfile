FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy poetry files
COPY services/api/pyproject.toml services/api/poetry.lock* ./services/api/
COPY libraries/utils/pyproject.toml libraries/utils/poetry.lock* ./libraries/utils/
COPY libraries/utils/src ./libraries/utils/src

# Install dependencies
WORKDIR /app/services/api
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY services/api/src ./src

WORKDIR /app

# Set Python path
ENV PYTHONPATH=/app/services/api:/app/libraries/utils/src

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
