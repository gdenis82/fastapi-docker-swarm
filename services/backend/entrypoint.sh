#!/bin/sh

set -e


echo "Starting application..."
exec gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --access-logfile - --error-logfile -
