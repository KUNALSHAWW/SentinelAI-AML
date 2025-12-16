# ============================================
# SentinelAI - Docker Image
# ============================================
# Multi-stage build for production deployment
# Optimized for Render.com free tier
# ============================================

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (for caching)
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Production
FROM python:3.11-slim as production

WORKDIR /app

# Create non-root user
RUN groupadd -r sentinel && useradd -r -g sentinel sentinel

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=sentinel:sentinel . .

# Create logs directory
RUN mkdir -p logs && chown -R sentinel:sentinel /app

# Switch to non-root user
USER sentinel

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    SENTINEL_ENVIRONMENT=production \
    SENTINEL_API_HOST=0.0.0.0 \
    PORT=10000

# Expose port (Render uses PORT env var, defaults to 10000)
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-10000}/health || exit 1

# Start command - use PORT env variable for Render.com compatibility
CMD ["sh", "-c", "python -m uvicorn sentinelai.api.app:create_app --factory --host 0.0.0.0 --port ${PORT:-10000}"]
