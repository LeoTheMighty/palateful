# OCR Service Dockerfile
# For GPU support, use nvidia/cuda base image

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
COPY services/ocr/pyproject.toml services/ocr/poetry.lock* ./

# Install dependencies (without GPU-specific packages)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY services/ocr/src ./src

# Set environment variables
ENV PYTHONPATH=/app
ENV DEVICE=cpu
ENV TORCH_DTYPE=float32

# Expose port
EXPOSE 8001

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
