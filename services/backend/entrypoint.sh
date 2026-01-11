#!/bin/sh

set -e

# Если переданы аргументы, выполняем их (например, alembic upgrade head)
if [ $# -gt 0 ]; then
    echo "Executing command: $@"
    exec "$@"
fi

echo "Starting application..."
exec gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --access-logfile - --error-logfile -
