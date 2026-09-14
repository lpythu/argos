#!/bin/bash
set -euo pipefail
cd /app
alembic upgrade head
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}"
