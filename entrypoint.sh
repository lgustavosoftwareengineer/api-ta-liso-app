#!/bin/sh
set -e

echo "Running migrations..."
python3 -m alembic upgrade head

echo "Starting server..."
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
