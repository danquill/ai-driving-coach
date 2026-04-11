# ============================================================
# track-mcp API — Dockerfile
# Python 3.12 slim, single-stage build
# ============================================================

FROM python:3.12-slim

# Build args
ARG DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gcc \
        libpq-dev \
        gdal-bin \
        libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy Alembic configuration
COPY alembic.ini ./
COPY migrations/ ./migrations/

# Copy application code
COPY app/ ./app/
COPY tests/ ./tests/

# Change ownership to non-root user
RUN chown -R appuser:appgroup /app

USER appuser

# Expose application port
EXPOSE 8000

# Default command (overridden in docker-compose for migrate service)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
