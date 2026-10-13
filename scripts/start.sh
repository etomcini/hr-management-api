#!/bin/sh
set -eu

echo "Running Alembic migrations..."
alembic upgrade head

echo "Synchronizing roles and permissions..."
python -m app.seeds.sync

echo "Bootstrapping administrator..."
python -m app.users.bootstrap_admin

echo "Starting FastAPI..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-127.0.0.1}"