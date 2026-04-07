# ============================================================
# track-mcp Celery Worker — Dockerfile
# Build context: repo root (so we can copy api/app for shared adapters)
# ============================================================

FROM python:3.12-slim

ARG DEBIAN_FRONTEND=noninteractive

# System dependencies (same set as API — shared task code may use psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Install Python dependencies (worker requirements)
COPY worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Install api requirements too (adapters + validation share api deps)
COPY api/requirements.txt ./api_requirements.txt
RUN pip install --no-cache-dir -r api_requirements.txt || true

# Copy worker application code
COPY worker/app/ ./worker/app/

# Copy shared api/app source (adapters, services/validation, config, etc.)
COPY api/app/ ./api/app/

# Ensure both packages are importable
RUN echo "" > /app/worker/__init__.py && echo "" > /app/api/__init__.py

RUN chown -R appuser:appgroup /app

USER appuser

# Default command — overridden in docker-compose for flower
CMD ["celery", "-A", "worker.app.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
