# Multi-stage build for HeimDall Observability Platform

# ==============================================================================
# Stage 1: Build Frontend Assets
# ==============================================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /build/frontend

COPY frontend/package.json ./
RUN npm install

COPY backend/collector/static/theme.* /build/backend/collector/static/
COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Python Backend & Unified Runtime
# ==============================================================================
FROM python:3.11-slim
WORKDIR /app

# Install minimal system tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies directly into system python
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy backend application source, scripts, and documentation
COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY docs/ ./docs/
COPY README.md ./

# Copy compiled frontend distribution from Stage 1
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# Copy container entrypoint script
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Ports:
# 8443: Central SaaS API & HTTPS Dashboard
# 9001: Local Collector & Scenario Verification Loopback
EXPOSE 8443 9001

# Default persistent volume for runtime credentials, SQLite DBs, and certificates
VOLUME ["/app/.heimdal"]

ENTRYPOINT ["./docker-entrypoint.sh"]
