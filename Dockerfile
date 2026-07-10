# PodFlow Dockerfile
# Multi-stage: build deps first, then slim runtime image.

FROM python:3.12-slim AS builder

WORKDIR /app

# Install system deps for psycopg2 (PostgreSQL driver)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir psycopg2-binary

# ---- Runtime stage ----
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Install the package in editable mode
RUN pip install -e . --no-deps

RUN mkdir -p /app/data /app/downloads

ENV PYTHONUNBUFFERED=1

CMD ["podflow", "pipeline", "${RSS_URL}"]
