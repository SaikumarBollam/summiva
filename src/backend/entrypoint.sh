#!/bin/bash
set -e

if [ -z "$SERVICE_NAME" ]; then
    echo "Error: SERVICE_NAME environment variable is not set"
    exit 1
fi

# Set PYTHONPATH to include the src directory as the base path
export PYTHONPATH="/app/src:$PYTHONPATH"
echo "Starting Summiva service: $SERVICE_NAME"

if [ ! -f /app/src/$SERVICE_NAME/main.py ]; then
    echo "Error: main.py not found in /app/src/$SERVICE_NAME"
    exit 1
fi

# In development mode, use uvicorn with hot reload but exclude problematic directories
if [ "$ENVIRONMENT" = "development" ]; then
    # Change to src directory first so relative paths work
    cd /app/src
    exec uvicorn --app-dir $SERVICE_NAME --host 0.0.0.0 --port 8000 --reload main:app \
        --reload-exclude "./postgresql/data/*" \
        --reload-exclude "./data/*" \
        --reload-exclude "*.pyc" \
        --reload-exclude "./__pycache__"
else
    # In production mode, use gunicorn
    exec gunicorn /app/src/$SERVICE_NAME/main:app --config /app/src/gunicorn_config.py
fi
