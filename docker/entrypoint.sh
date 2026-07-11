#!/bin/sh
set -e

echo "Running migrations..."
alembic upgrade head

echo "Starting bot..."
exec python -m src.main