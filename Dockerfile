# ============================================================
# SentinelAI - multi-stage image
# ============================================================
FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY sentinelai ./sentinelai
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim AS production
RUN groupadd -r sentinel && useradd -r -g sentinel -d /app sentinel \
    && apt-get update && apt-get install -y --no-install-recommends curl libpq5 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=sentinel:sentinel frontend ./frontend
COPY --chown=sentinel:sentinel migrations ./migrations
COPY --chown=sentinel:sentinel alembic.ini ./alembic.ini
COPY --chown=sentinel:sentinel scripts/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh && mkdir -p data logs && chown -R sentinel:sentinel /app
USER sentinel

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    SENTINEL_ENVIRONMENT=production SENTINEL_API_HOST=0.0.0.0 PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8000}/health || exit 1
ENTRYPOINT ["./entrypoint.sh"]
