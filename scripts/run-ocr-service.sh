#!/bin/bash
# Run the OCR service locally

set -e

cd "$(dirname "$0")/../services/ocr"

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "Poetry is not installed. Installing..."
    pip install poetry
fi

# Install dependencies
echo "Installing dependencies..."
poetry install

# Run the service
echo "Starting OCR service on http://localhost:8001"
echo "API docs available at http://localhost:8001/docs"
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload
