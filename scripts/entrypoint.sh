#!/bin/sh
# Optionally apply migrations, then start the API on $PORT (Render/Heroku-style) or 8000.
set -e
if [ "${SENTINEL_RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "Applying database migrations..."
  alembic upgrade head
fi
exec uvicorn sentinelai.api.app:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-1}" --proxy-headers
